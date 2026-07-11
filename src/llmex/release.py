"""M7 릴리스 재현성·공급망·승인 게이트 도구."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path
from typing import Any

from llmex import __version__
from llmex.data.io import write_json
from llmex.errors import InputError, IntegrityError
from llmex.fingerprint import sha256_file
from llmex.trust import repository_commit, verify_statement

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
GATE_POLICY = {
    "법무 검토": ("legal", "legal-approval"),
    "장기 baseline": ("baseline", "baseline-evidence"),
    "공개 배포 결정": ("release", "release-approval"),
}
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
    if not isinstance(value, dict):
        raise TypeError("JSON artifact root는 object여야 합니다")
    write_json(path, value)


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


def _build_artifacts(root: Path, output: Path) -> list[Path]:
    package_dir = output / "packages"
    package_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["uv", "build", "--out-dir", str(package_dir)], cwd=root, text=True, capture_output=True
    )
    if completed.returncode != 0:
        raise IntegrityError(f"배포 artifact build 실패: {completed.stderr[-2000:]}")
    artifacts = sorted([*package_dir.glob("*.whl"), *package_dir.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise IntegrityError("wheel/sdist가 정확히 하나씩 생성되지 않았습니다")
    return artifacts


def sbom(wheel: Path, output: Path) -> dict[str, Any]:
    """실제 wheel METADATA에 포함된 runtime dependency 기반 SBOM을 만든다."""
    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise IntegrityError("wheel METADATA를 유일하게 찾을 수 없습니다")
        metadata = Parser().parsestr(archive.read(names[0]).decode())
    components = [
        {"type": "library", "name": req.split(" ", 1)[0].split(";", 1)[0]}
        for req in sorted(metadata.get_all("Requires-Dist", []))
    ]
    value: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:llmex-{__version__}-{sha256_file(wheel)[:16]}",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "llmex", "version": __version__},
            "properties": [{"name": "llmex:wheel:sha256", "value": sha256_file(wheel)}],
        },
        "components": components,
    }
    _json(output, value)
    return value


def provenance(root: Path, output: Path, artifacts: list[Path]) -> dict[str, Any]:
    """wheel/sdist digest를 subject로 결속한 SLSA 호환 진술을 만든다."""
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True
        ).stdout
    )
    value: dict[str, Any] = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": path.name, "digest": {"sha256": sha256_file(path)}} for path in artifacts
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://llmex.local/build/uv/v1",
                "externalParameters": {"command": "uv build", "version": __version__},
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
                    "releaseEligible": not dirty,
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


def external_gate(approvals: Path, repository: Path) -> dict[str, Any]:
    """보호 CI trust store와 evidence digest에 결속된 외부 승인을 검증한다."""
    try:
        payload = json.loads(approvals.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"외부 승인 파일을 읽을 수 없습니다: {approvals}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise IntegrityError("외부 승인 schema가 없거나 지원되지 않습니다")
    repository, expected_commit = repository_commit(repository)
    target = payload.get("target")
    if (
        not isinstance(target, dict)
        or target.get("version") != __version__
        or target.get("git_commit") != expected_commit
    ):
        raise IntegrityError("승인 대상 version/git commit이 현재 대상과 다릅니다")
    config_fp = target.get("config_fingerprint")
    if not isinstance(config_fp, str) or not re.fullmatch(r"[0-9a-f]{64}", config_fp):
        raise IntegrityError("승인 대상 config fingerprint가 유효하지 않습니다")
    gates = payload.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(EXTERNAL_GATES):
        raise IntegrityError("필수 외부 gate 집합이 정확하지 않습니다")
    approvers: set[str] = set()
    for name in EXTERNAL_GATES:
        item = gates[name]
        if not isinstance(item, dict) or item.get("approved") is not True:
            raise IntegrityError(f"{name}: 명시 승인이 없습니다")
        issuer, role, approver = (item.get(key) for key in ("issuer", "role", "approver"))
        if (
            not isinstance(issuer, str)
            or not isinstance(role, str)
            or not isinstance(approver, str)
        ):
            raise IntegrityError(f"{name}: issuer/role/approver 누락")
        expected_role, expected_kind = GATE_POLICY[name]
        if approver in approvers:
            raise IntegrityError("서로 다른 gate에 동일 승인자를 사용할 수 없습니다")
        approvers.add(approver)
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            raise IntegrityError(f"{name}: evidence 누락")
        evidence_path = approvals.parent / str(evidence.get("path", ""))
        if not evidence_path.is_file() or evidence.get("sha256") != sha256_file(evidence_path):
            raise IntegrityError(f"{name}: evidence 파일/checksum 불일치")
        signed = {
            "gate": name,
            "target": target,
            **{key: value for key, value in item.items() if key != "signature"},
        }
        verify_statement(
            item,
            repository=repository,
            expected_role=expected_role,
            expected_kind=expected_kind,
            signed_payload=signed,
        )
    return {
        "판정": "승인",
        "권위": "protected-ci",
        "게이트": list(EXTERNAL_GATES),
        "target": target,
    }


def bundle(root: Path, output: Path) -> dict[str, Any]:
    """실제 wheel/sdist와 내용 기반 공급망 문서를 생성한다."""
    audit_result = audit(root)
    output.mkdir(parents=True, exist_ok=True)
    artifacts = _build_artifacts(root, output)
    manifest = checksum_manifest(root, output / "checksums.json")
    artifact_manifest = {
        "schema_version": 1,
        "artifacts": [
            {"name": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in artifacts
        ],
    }
    _json(output / "artifact-checksums.json", artifact_manifest)
    wheel = next(path for path in artifacts if path.suffix == ".whl")
    sbom_value = sbom(wheel, output / "sbom.cdx.json")
    provenance(root, output / "provenance.intoto.json", artifacts)
    _json(
        output / "reproduce.json",
        {
            "버전": __version__,
            "재현 명령": ["uv sync --frozen", "make release-check", "uv build"],
            "외부 게이트": list(EXTERNAL_GATES),
            "주의": "외부 승인 전 공개 배포 금지",
        },
    )
    result = {
        "판정": "로컬 번들 생성 완료",
        "버전": __version__,
        "파일 수": len(manifest["files"]),
        "배포 artifact 수": len(artifacts),
        "SBOM 구성요소 수": len(sbom_value["components"]),
        "감사": audit_result,
        "외부 게이트": "미승인 상태 유지",
    }
    _json(output / "bundle-summary.json", result)
    return result
