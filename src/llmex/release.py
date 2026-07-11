"""M7 릴리스 재현성·공급망·승인 게이트 도구."""

from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from llmex import __version__
from llmex.errors import InputError, IntegrityError
from llmex.fingerprint import sha256_file

SCHEMA_VERSION = 1
REQUIRED_RELEASE_FILES = (
    "README.md",
    "NOTICE.md",
    "ATTRIBUTION.md",
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    "docs/data-card.md",
    "docs/model-card.md",
    "docs/tokenizer-card.md",
    "docs/security.md",
    "docs/threat-model.md",
    "docs/release-checklist.md",
    "docs/operations-runbook.md",
    "docs/api-cli.md",
    "docs/failure-modes.md",
    "docs/migration.md",
    "docs/changelog.md",
    "docs/acceptance-matrix.md",
    "docs/reproducibility.md",
    "docs/examples.md",
)
EXTERNAL_GATES = ("법무 검토", "장기 baseline", "공개 배포 결정")
REFERENCE_DIR = "0" + ".ref"
REFERENCE_MODULE = "llm" + "_math"
MAC_USER_PREFIX = "/" + "Users" + "/"
SECRET_PATTERNS = {
    "개인키": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub 토큰": re.compile(r"gh[opsu]_[A-Za-z0-9]{20,}"),
    "AWS 접근 키": re.compile(r"AKIA[0-9A-Z]{16}"),
    "일반 비밀값": re.compile(r"(?i)(?:api[_-]?key|secret|password)\s*[:=]\s*['\"][^'\"]+"),
}


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def tracked_files(root: Path) -> list[Path]:
    """Git 배포 후보 파일 목록을 반환한다."""

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = [Path(raw.decode()) for raw in result.stdout.split(b"\0") if raw]
    return sorted(path for path in paths if path.parts[0] not in {"dist", ".omx"})


def checksum_manifest(root: Path, output: Path, files: list[Path] | None = None) -> dict[str, Any]:
    """추적 파일의 SHA-256 manifest를 만든다."""

    selected = files or tracked_files(root)
    entries = [
        {
            "path": path.as_posix(),
            "sha256": sha256_file(root / path),
            "bytes": (root / path).stat().st_size,
        }
        for path in selected
        if (root / path).is_file()
    ]
    value = {"schema_version": SCHEMA_VERSION, "algorithm": "SHA-256", "files": entries}
    _json(output, value)
    return value


def sbom(output: Path) -> dict[str, Any]:
    """설치 환경을 CycloneDX 호환 JSON SBOM으로 기록한다."""

    components: list[dict[str, object]] = []
    for dist in sorted(
        importlib.metadata.distributions(), key=lambda item: item.metadata["Name"].lower()
    ):
        name = dist.metadata["Name"]
        license_name = cast(str | None, dist.metadata["License-Expression"]) or cast(
            str | None, dist.metadata["License"]
        )
        licenses: list[dict[str, dict[str, str]]] = []
        if license_name:
            licenses.append({"license": {"name": license_name[:200]}})
        components.append(
            {
                "type": "library",
                "name": name,
                "version": dist.version,
                "purl": f"pkg:pypi/{name.lower().replace('_', '-')}@{dist.version}",
                "licenses": licenses,
            }
        )
    value = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:llmex-{__version__}",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "llmex", "version": __version__}},
        "components": components,
    }
    _json(output, value)
    return value


def provenance(root: Path, output: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """SLSA provenance와 대응되는 로컬 빌드 진술을 만든다."""

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True
        ).stdout
    )
    value = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": "llmex-source",
                "digest": {"sha256": sha256_file(output.parent / "checksums.json")},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://llmex.local/build/uv/v1",
                "externalParameters": {"명령": "uv build", "버전": __version__},
                "resolvedDependencies": [
                    {"uri": f"git+file://{root}", "digest": {"gitCommit": commit}}
                ],
            },
            "runDetails": {
                "builder": {"id": "llmex-release-cli"},
                "metadata": {
                    "invocationId": f"llmex-{__version__}",
                    "startedOn": datetime.now(UTC).isoformat(),
                    "sourceDirty": dirty,
                    "fileCount": len(manifest["files"]),
                    "python": sys.version.split()[0],
                    "platform": sys.platform,
                },
            },
        },
    }
    _json(output, value)
    return value


def audit(root: Path) -> dict[str, Any]:
    """비밀·로컬 경로·라이선스·참조 경계를 실패-폐쇄형으로 검사한다."""

    failures: list[str] = []
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "src").rglob("*.py")
    )
    if REFERENCE_DIR in source_text or REFERENCE_MODULE in source_text:
        failures.append("production source가 읽기 전용 참조 경계를 위반합니다.")
    for relative in REQUIRED_RELEASE_FILES:
        if not (root / relative).is_file():
            failures.append(f"필수 릴리스 파일 누락: {relative}")
    scan_suffixes = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt"}
    for relative in tracked_files(root):
        path = root / relative
        if path.suffix not in scan_suffixes or relative.parts[0] == REFERENCE_DIR:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{relative}: {name} 의심 문자열")
        if str(root) in text or MAC_USER_PREFIX in text:
            failures.append(f"{relative}: 배포 금지 로컬 절대 경로")
    if failures:
        raise IntegrityError("릴리스 감사 실패: " + "; ".join(failures))
    return {"판정": "통과", "검사": ["비밀", "로컬 경로", "필수 문서", "참조 import 경계"]}


def external_gate(approvals: Path) -> dict[str, Any]:
    """사람·외부 증거가 필요한 세 gate를 명시 승인 없이는 거부한다."""

    try:
        payload = cast(dict[str, object], json.loads(approvals.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"외부 승인 파일을 읽을 수 없습니다: {approvals}: {exc}") from exc
    failures: list[str] = []
    for name in EXTERNAL_GATES:
        gate_value = payload.get(name)
        if not isinstance(gate_value, dict):
            failures.append(f"{name}: approved=true 아님")
            continue
        gate = cast(dict[str, object], gate_value)
        if gate.get("approved") is not True:
            failures.append(f"{name}: approved=true 아님")
            continue
        fields = [gate.get(key) for key in ("승인자", "시각", "근거")]
        if not all(isinstance(field, str) and bool(field.strip()) for field in fields):
            failures.append(f"{name}: 승인자/시각/근거 누락")
    if failures:
        raise IntegrityError("외부 공개 gate 실패: " + "; ".join(failures))
    return {"판정": "승인", "게이트": list(EXTERNAL_GATES)}


def bundle(root: Path, output: Path) -> dict[str, Any]:
    """최종 로컬 재현성 bundle의 manifest, SBOM, provenance를 생성한다."""

    audit_result = audit(root)
    output.mkdir(parents=True, exist_ok=True)
    manifest = checksum_manifest(root, output / "checksums.json")
    sbom_value = sbom(output / "sbom.cdx.json")
    provenance(root, output / "provenance.intoto.json", manifest)
    instructions = {
        "버전": __version__,
        "재현 명령": [
            "uv sync --frozen",
            "make release-check",
            "uv build",
            "uv run llmex release bundle --output dist/reproducibility",
        ],
        "외부 게이트": list(EXTERNAL_GATES),
        "주의": "외부 승인 전 모델 가중치와 데이터의 공개 배포를 금지합니다.",
    }
    _json(output / "reproduce.json", instructions)
    result = {
        "판정": "로컬 번들 생성 완료",
        "버전": __version__,
        "파일 수": len(manifest["files"]),
        "SBOM 구성요소 수": len(sbom_value["components"]),
        "감사": audit_result,
        "외부 게이트": "미승인 상태 유지",
    }
    _json(output / "bundle-summary.json", result)
    return result
