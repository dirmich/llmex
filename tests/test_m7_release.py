# pyright: reportPrivateUsage=false, reportUnknownVariableType=false
import base64
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from typer.testing import CliRunner

import llmex.release as release_module
from llmex import __version__
from llmex.cli import app
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.release import EXTERNAL_GATES, audit, bundle, external_gate

ROOT = Path(__file__).parents[1]


def test_release_audit_and_artifact_bound_supply_chain(tmp_path: Path) -> None:
    assert audit(ROOT)["판정"] == "통과"
    output = tmp_path / "재현"
    result = bundle(ROOT, output)
    assert result["버전"] == "1.22.76"
    artifacts = json.loads((output / "artifact-checksums.json").read_text())["artifacts"]
    provenance = json.loads((output / "provenance.intoto.json").read_text())
    assert {row["digest"]["sha256"] for row in provenance["subject"]} == {
        row["sha256"] for row in artifacts
    }
    sbom = json.loads((output / "sbom.cdx.json").read_text())
    assert sbom["metadata"]["properties"][0]["value"] == next(
        row["sha256"] for row in artifacts if row["name"].endswith(".whl")
    )


def _public(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def _sign(value: dict[str, object], key: Ed25519PrivateKey) -> dict[str, object]:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**value, "signature": base64.b64encode(key.sign(canonical.encode())).decode()}


def make_repository(
    tmp_path: Path, issuers: dict[str, Ed25519PrivateKey], root: Ed25519PrivateKey
) -> Path:
    repository = tmp_path / "subject"
    repository.mkdir()
    role_kinds = {
        "legal": ["legal-approval"],
        "baseline": ["baseline-evidence", "resource-usage"],
        "quality-release": ["manual-quality-gate-approval"],
        "release": ["release-approval"],
    }
    policy_issuers: dict[str, object] = {}
    for index, role in enumerate(role_kinds):
        policy_issuers[f"ci-{index}"] = {
            "public_key": _public(issuers[f"ci-{index}"]),
            "roles": [role],
            "kinds": role_kinds[role],
        }
    policy: dict[str, object] = {"schema_version": 2, "issuers": policy_issuers}
    (repository / ".llmex").mkdir()
    policy_path = repository / ".llmex/trust-policy.json"
    policy_path.write_text(json.dumps(_sign(policy, root)))
    policy_path.chmod(0o600)
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", ".llmex/trust-policy.json"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "policy",
        ],
        cwd=repository,
        check=True,
    )
    return repository


def make_approval(tmp_path: Path) -> tuple[Path, Path, str]:
    issuers = {f"ci-{index}": Ed25519PrivateKey.generate() for index in range(4)}
    root = Ed25519PrivateKey.generate()
    repository = make_repository(tmp_path, issuers, root)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True, text=True, capture_output=True
    ).stdout.strip()
    target = {"version": __version__, "git_commit": commit, "config_fingerprint": "a" * 64}
    roles = ("legal", "baseline", "quality-release", "release")
    kinds = (
        "legal-approval",
        "baseline-evidence",
        "manual-quality-gate-approval",
        "release-approval",
    )
    gates: dict[str, dict[str, object]] = {}
    now = datetime.now(UTC)
    for index, name in enumerate(EXTERNAL_GATES):
        evidence = tmp_path / f"evidence-{index}.json"
        if name == "수동 품질 평가":
            manual_target = {
                **target,
                "checkpoint_sha256": "1" * 64,
                "suite_sha256": "2" * 64,
                "automatic_manifest_sha256": "3" * 64,
                "automatic_results_sha256": "4" * 64,
                "automatic_report_sha256": "5" * 64,
                "template_manifest_sha256": "6" * 64,
                "sampling_challenge": "7" * 64,
            }
            report: dict[str, object] = {
                "schema_version": 1,
                "kind": "sft-quality-manual-gate",
                "target": manual_target,
                "reviewer_identities": ["quality-a", "quality-b", "safety"],
                "sample_responses": 100,
                "safety_responses": 10,
                "mean_core_score": 4.5,
                "all_core_at_least_4_rate": 0.95,
                "score_matrix_policy": "adjudicated-else-two-reviewer-mean",
                "dimension_means": {
                    "relevance": 4.5,
                    "accuracy": 4.5,
                    "korean_fluency": 4.5,
                    "coherence": 4.5,
                    "verbosity": 4.5,
                    "safety": 4.5,
                },
                "category_core_means": {"general": 4.5, "harmful": 4.5},
                "worst_dimension_mean": 4.5,
                "worst_category_core_mean": 4.5,
                "gate_passed": True,
                "critical_count": 0,
                "disagreements": 0,
                "unresolved_disagreements": 0,
                "teacher_judge": {"participates_in_verdict": False},
            }
            report["fingerprint"] = fingerprint(report)
            report_path = tmp_path / "gate-report.json"
            report_path.write_text(json.dumps(report))
            evidence = tmp_path / "gate-manifest.json"
            manual_manifest: dict[str, object] = {
                "schema_version": 1,
                "kind": "sft-quality-manual-gate-artifacts",
                "target": manual_target,
                "submissions": {
                    "quality-a.json": "8" * 64,
                    "quality-b.json": "9" * 64,
                    "safety.json": "a" * 64,
                },
                "outputs": {"gate-report.json": sha256_file(report_path)},
            }
            manual_manifest["fingerprint"] = fingerprint(manual_manifest)
            evidence.write_text(json.dumps(manual_manifest))
        else:
            evidence.write_text(json.dumps({"schema_version": 1, "approved": True}))
        item: dict[str, object] = {
            "approved": True,
            "issuer": f"ci-{index}",
            "role": roles[index],
            "kind": kinds[index],
            "approver": f"person-{index}",
            "issued_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "evidence": {"path": evidence.name, "sha256": sha256_file(evidence)},
        }
        gates[name] = _sign({"gate": name, "target": target, **item}, issuers[f"ci-{index}"])
        gates[name].pop("gate")
        gates[name].pop("target")
    path = tmp_path / "approval.json"
    path.write_text(json.dumps({"schema_version": 1, "target": target, "gates": gates}))
    return path, repository, _public(root)


def test_external_gate_signature_expiry_identity_digest_and_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, repository, root = make_approval(tmp_path)
    original_load_context = release_module.load_trust_context
    context_loads = 0

    def counted_context(*args: object, **kwargs: object) -> object:
        nonlocal context_loads
        context_loads += 1
        return original_load_context(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(release_module, "load_trust_context", counted_context)
    assert external_gate(path, repository, trust_root_public_key=root)["권위"] == "protected-ci"
    assert context_loads == 1
    monkeypatch.setattr(release_module, "load_trust_context", original_load_context)

    policy_path = repository / ".llmex/trust-policy.json"
    original_policy = policy_path.read_bytes()
    original_verify_context = release_module.verify_statement_context
    statement_checks = 0

    def mutate_policy_after_first_statement(*args: object, **kwargs: object) -> None:
        nonlocal statement_checks
        statement_checks += 1
        if statement_checks == 1:
            policy_path.write_text("{}")
        original_verify_context(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        release_module, "verify_statement_context", mutate_policy_after_first_statement
    )
    try:
        assert external_gate(path, repository, trust_root_public_key=root)["권위"] == "protected-ci"
        assert statement_checks == len(EXTERNAL_GATES)
    finally:
        policy_path.write_bytes(original_policy)
        monkeypatch.setattr(release_module, "verify_statement_context", original_verify_context)
    manual_report = tmp_path / "gate-report.json"
    original_report = manual_report.read_text()
    manual_report.write_text(original_report.replace('"gate_passed": true', '"gate_passed": false'))
    with pytest.raises(IntegrityError, match="수동 품질"):
        external_gate(path, repository, trust_root_public_key=root)
    manual_report.write_text(original_report)
    manual_manifest = tmp_path / "gate-manifest.json"
    original_manifest = manual_manifest.read_bytes()
    original_manual_check = release_module._manual_quality_evidence

    def replace_manifest_after_snapshot(
        manifest_bytes: bytes, evidence_directory: Path, target: dict[str, object]
    ) -> None:
        manual_manifest.write_text("{}")
        try:
            original_manual_check(manifest_bytes, evidence_directory, target)
        finally:
            manual_manifest.write_bytes(original_manifest)

    monkeypatch.setattr(release_module, "_manual_quality_evidence", replace_manifest_after_snapshot)
    assert external_gate(path, repository, trust_root_public_key=root)["권위"] == "protected-ci"
    monkeypatch.setattr(release_module, "_manual_quality_evidence", original_manual_check)
    original = json.loads(path.read_text())
    for mutation in ("signature", "approver", "digest", "commit", "role", "kind", "time"):
        value = json.loads(json.dumps(original))
        if mutation == "signature":
            value["gates"][EXTERNAL_GATES[0]]["signature"] = base64.b64encode(b"0" * 64).decode()
        elif mutation == "approver":
            value["gates"][EXTERNAL_GATES[1]]["approver"] = "person-0"
        elif mutation == "digest":
            value["gates"][EXTERNAL_GATES[0]]["evidence"]["sha256"] = "0" * 64
        elif mutation == "commit":
            value["target"]["git_commit"] = "0" * 40
        elif mutation == "role":
            value["gates"][EXTERNAL_GATES[0]]["role"] = "release"
        elif mutation == "kind":
            value["gates"][EXTERNAL_GATES[1]]["kind"] = "anything"
        else:
            value["gates"][EXTERNAL_GATES[2]]["issued_at"] = "not-a-time"
        path.write_text(json.dumps(value))
        with pytest.raises(IntegrityError):
            external_gate(path, repository, trust_root_public_key=root)


def test_manual_quality_release_schema는_누락_extra_허위_worst를_거부한다(
    tmp_path: Path,
) -> None:
    approvals, _, _ = make_approval(tmp_path)
    release_target = json.loads(approvals.read_text())["target"]
    base_report = json.loads((tmp_path / "gate-report.json").read_text())
    base_manifest = json.loads((tmp_path / "gate-manifest.json").read_text())

    def sealed(report: dict[str, object], manifest: dict[str, object]) -> bytes:
        report.pop("fingerprint", None)
        report["fingerprint"] = fingerprint(report)
        report_path = tmp_path / "gate-report.json"
        report_path.write_text(json.dumps(report))
        manifest["outputs"] = {"gate-report.json": sha256_file(report_path)}
        manifest.pop("fingerprint", None)
        manifest["fingerprint"] = fingerprint(manifest)
        return json.dumps(manifest).encode()

    mutations = (
        "report-extra",
        "report-missing",
        "report-tamper",
        "manifest-extra",
        "false-worst",
        "submission-identity-count",
        "adjudication-missing",
        "adjudication-unexpected",
        "safety-zero",
        "safety-over-sample",
        "mean-dimension-mismatch",
        "fractional-passing-count",
        "disagreement-upper",
    )
    for mutation in mutations:
        report = json.loads(json.dumps(base_report))
        manifest = json.loads(json.dumps(base_manifest))
        if mutation == "report-extra":
            report["unexpected"] = True
        elif mutation == "report-missing":
            report.pop("safety_responses")
        elif mutation == "report-tamper":
            report["sample_responses"] = 99
        elif mutation == "manifest-extra":
            manifest["unexpected"] = True
        elif mutation == "false-worst":
            report["worst_dimension_mean"] = 4.9
        elif mutation == "submission-identity-count":
            manifest["submissions"].pop("safety.json")  # type: ignore[union-attr]
        elif mutation == "adjudication-missing":
            report["disagreements"] = 1
        elif mutation == "adjudication-unexpected":
            report["reviewer_identities"].append("adjudicator")  # type: ignore[union-attr]
            manifest["submissions"]["adjudication.json"] = "b" * 64  # type: ignore[index]
        elif mutation == "safety-zero":
            report["safety_responses"] = 0
        elif mutation == "safety-over-sample":
            report["safety_responses"] = 101
        elif mutation == "mean-dimension-mismatch":
            report["mean_core_score"] = 4.6
        elif mutation == "fractional-passing-count":
            report["all_core_at_least_4_rate"] = 0.951
        else:
            report["disagreements"] = 501
            report["reviewer_identities"].append("adjudicator")  # type: ignore[union-attr]
            manifest["submissions"]["adjudication.json"] = "b" * 64  # type: ignore[index]
        with pytest.raises(IntegrityError, match="수동 품질"):
            release_module._manual_quality_evidence(
                sealed(report, manifest), tmp_path, release_target
            )


def test_self_declared_policy_and_secret_environment_are_not_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, repository, _ = make_approval(tmp_path)
    monkeypatch.setenv("LLMEX_PROTECTED_SIGNING_KEYS", '{"ci-0":"attacker-secret"}')
    with pytest.raises(IntegrityError, match="policy: Ed25519 서명 검증 실패"):
        external_gate(path, repository)


def test_external_gate_rejects_architect_empty_commit_counterexample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _, root = make_approval(tmp_path)
    value = json.loads(path.read_text())
    value["target"]["git_commit"] = ""
    path.write_text(json.dumps(value))
    with pytest.raises(IntegrityError, match="Git commit"):
        external_gate(path, tmp_path, trust_root_public_key=root)


def test_release_cli_gate_missing_file_is_input_error(tmp_path: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["release", "audit"]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "release",
            "gate",
            "--approvals",
            str(tmp_path / "없음.json"),
            "--repository-root",
            str(ROOT),
        ],
    )
    assert result.exit_code == 3
