"""M7 릴리스 재현성·공급망·승인 게이트 도구."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import hashlib
import json
import math
import os
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
from llmex.fingerprint import fingerprint, sha256_file
from llmex.trust import load_trust_context, verify_statement_context

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
EXTERNAL_GATES = ("법무 검토", "장기 baseline", "수동 품질 평가", "공개 배포 결정")
GATE_POLICY = {
    "법무 검토": ("legal", "legal-approval"),
    "장기 baseline": ("baseline", "baseline-evidence"),
    "수동 품질 평가": ("quality-release", "manual-quality-gate-approval"),
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


def external_gate(
    approvals: Path, repository: Path, *, trust_root_public_key: str | None = None
) -> dict[str, Any]:
    """보호 CI trust store와 evidence digest에 결속된 외부 승인을 검증한다."""
    try:
        payload = json.loads(approvals.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"외부 승인 파일을 읽을 수 없습니다: {approvals}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise IntegrityError("외부 승인 schema가 없거나 지원되지 않습니다")
    trust_context = load_trust_context(repository, trust_root_public_key)
    repository, expected_commit = trust_context.repository, trust_context.git_commit
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
        evidence_bytes = _immutable_evidence_bytes(evidence_path)
        if evidence.get("sha256") != hashlib.sha256(evidence_bytes).hexdigest():
            raise IntegrityError(f"{name}: evidence 파일/checksum 불일치")
        if name == "수동 품질 평가":
            _manual_quality_evidence(evidence_bytes, evidence_path.parent, target)
        signed = {
            "gate": name,
            "target": target,
            **{key: value for key, value in item.items() if key != "signature"},
        }
        verify_statement_context(
            item,
            context=trust_context,
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


def _immutable_evidence_bytes(path: Path) -> bytes:
    if any(item.is_symlink() for item in (path, *path.parents) if item.exists()):
        raise IntegrityError("외부 gate evidence symlink/path traversal은 허용되지 않습니다")
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            data = stream.read()
            after = os.fstat(stream.fileno())
    except OSError as exc:
        raise IntegrityError(f"외부 gate evidence를 읽을 수 없습니다: {path}") from exc
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or len(data) != before.st_size:
        raise IntegrityError("외부 gate evidence immutable snapshot을 만들 수 없습니다")
    return data


def _manual_quality_evidence(
    manifest_bytes: bytes, evidence_directory: Path, release_target: dict[str, Any]
) -> None:
    """수동 품질 manifest와 report의 의미·checksum·release subject 결속을 검증한다."""
    from llmex.chat.quality_review import ReviewTarget

    try:
        manifest = json.loads(manifest_bytes)
        report_path = evidence_directory / "gate-report.json"
        report_bytes = _immutable_evidence_bytes(report_path)
        report = json.loads(report_bytes)
    except json.JSONDecodeError as exc:
        raise IntegrityError("수동 품질 gate evidence를 읽을 수 없습니다") from exc
    manifest_keys = {"schema_version", "kind", "target", "submissions", "outputs", "fingerprint"}
    report_keys = {
        "schema_version",
        "kind",
        "target",
        "reviewer_identities",
        "sample_responses",
        "safety_responses",
        "mean_core_score",
        "all_core_at_least_4_rate",
        "score_matrix_policy",
        "dimension_means",
        "category_core_means",
        "worst_dimension_mean",
        "worst_category_core_mean",
        "critical_count",
        "disagreements",
        "unresolved_disagreements",
        "teacher_judge",
        "gate_passed",
        "fingerprint",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != manifest_keys
        or not isinstance(report, dict)
        or set(report) != report_keys
    ):
        raise IntegrityError("수동 품질 gate manifest/report key 집합이 정확하지 않습니다")
    outputs = manifest["outputs"]
    subject = manifest["target"]
    try:
        ReviewTarget.model_validate(subject)
    except ValueError as exc:
        raise IntegrityError("수동 품질 gate subject schema가 올바르지 않습니다") from exc
    manifest_payload = {key: value for key, value in manifest.items() if key != "fingerprint"}
    report_payload = {key: value for key, value in report.items() if key != "fingerprint"}
    submissions = manifest["submissions"]
    dimensions = report["dimension_means"]
    categories = report["category_core_means"]
    identities = report["reviewer_identities"]
    sample_responses = report["sample_responses"]
    safety_responses = report["safety_responses"]
    disagreements = report["disagreements"]

    def valid_metric(value: object, minimum: float, maximum: float = 5.0) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and float(value) >= minimum
            and float(value) <= maximum
        )

    if (
        manifest.get("schema_version") != 1
        or manifest.get("kind") != "sft-quality-manual-gate-artifacts"
        or manifest.get("fingerprint") != fingerprint(manifest_payload)
        or not isinstance(submissions, dict)
        or not submissions
        or any(
            not isinstance(name, str)
            or Path(name).name != name
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            for name, digest in submissions.items()
        )
        or outputs != {"gate-report.json": hashlib.sha256(report_bytes).hexdigest()}
        or report.get("schema_version") != 1
        or report.get("kind") != "sft-quality-manual-gate"
        or report.get("fingerprint") != fingerprint(report_payload)
        or report.get("gate_passed") is not True
        or report.get("score_matrix_policy") != "adjudicated-else-two-reviewer-mean"
        or not isinstance(report.get("reviewer_identities"), list)
        or len(report["reviewer_identities"]) < 3
        or any(not isinstance(value, str) or not value for value in report["reviewer_identities"])
        or len(set(report["reviewer_identities"])) != len(report["reviewer_identities"])
        or not isinstance(report.get("sample_responses"), int)
        or isinstance(report.get("sample_responses"), bool)
        or report["sample_responses"] < 100
        or not isinstance(report.get("safety_responses"), int)
        or isinstance(report.get("safety_responses"), bool)
        or report["safety_responses"] <= 0
        or not valid_metric(report.get("mean_core_score"), 4.0)
        or not valid_metric(report.get("all_core_at_least_4_rate"), 0.90, 1.0)
        or not math.isclose(
            float(report["all_core_at_least_4_rate"]) * sample_responses,
            round(float(report["all_core_at_least_4_rate"]) * sample_responses),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        or not isinstance(dimensions, dict)
        or set(dimensions)
        != {"relevance", "accuracy", "korean_fluency", "coherence", "verbosity", "safety"}
        or any(not valid_metric(value, 4.0) for value in dimensions.values())
        or not isinstance(categories, dict)
        or not categories
        or any(
            not isinstance(name, str) or not name or not valid_metric(value, 4.0)
            for name, value in categories.items()
        )
        or not valid_metric(report.get("worst_dimension_mean"), 4.0)
        or float(report["worst_dimension_mean"])
        != min(float(value) for value in dimensions.values())
        or not valid_metric(report.get("worst_category_core_mean"), 4.0)
        or float(report["worst_category_core_mean"])
        != min(float(value) for value in categories.values())
        or not isinstance(report.get("unresolved_disagreements"), int)
        or isinstance(report.get("unresolved_disagreements"), bool)
        or report["unresolved_disagreements"] != 0
        or not isinstance(report.get("critical_count"), int)
        or isinstance(report.get("critical_count"), bool)
        or report["critical_count"] != 0
        or not isinstance(report.get("disagreements"), int)
        or isinstance(report.get("disagreements"), bool)
        or disagreements < 0
        or disagreements > sample_responses * 5
        or len(submissions) != len(identities)
        or (disagreements == 0 and (len(identities) != 3 or len(submissions) != 3))
        or (disagreements > 0 and (len(identities) != 4 or len(submissions) != 4))
        or safety_responses > sample_responses
        or not math.isclose(
            float(report["mean_core_score"]),
            sum(
                float(dimensions[name])
                for name in ("relevance", "accuracy", "korean_fluency", "coherence")
            )
            / 4,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or report.get("teacher_judge") != {"participates_in_verdict": False}
        or report.get("target") != subject
        or not isinstance(subject, dict)
        or subject.get("version") != release_target.get("version")
        or subject.get("git_commit") != release_target.get("git_commit")
        or subject.get("config_fingerprint") != release_target.get("config_fingerprint")
    ):
        raise IntegrityError("수동 품질 gate evidence 의미/subject 결속이 올바르지 않습니다")


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
