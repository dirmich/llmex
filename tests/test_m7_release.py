# pyright: reportUnknownVariableType=false
import base64
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from typer.testing import CliRunner

from llmex import __version__
from llmex.cli import app
from llmex.errors import IntegrityError
from llmex.fingerprint import sha256_file
from llmex.release import EXTERNAL_GATES, audit, bundle, external_gate

ROOT = Path(__file__).parents[1]


def test_release_audit_and_artifact_bound_supply_chain(tmp_path: Path) -> None:
    assert audit(ROOT)["판정"] == "통과"
    output = tmp_path / "재현"
    result = bundle(ROOT, output)
    assert result["버전"] == "1.5.1"
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
    (repository / ".llmex/trust-policy.json").write_text(json.dumps(_sign(policy, root)))
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
    issuers = {f"ci-{index}": Ed25519PrivateKey.generate() for index in range(3)}
    root = Ed25519PrivateKey.generate()
    repository = make_repository(tmp_path, issuers, root)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True, text=True, capture_output=True
    ).stdout.strip()
    target = {"version": __version__, "git_commit": commit, "config_fingerprint": "a" * 64}
    roles = ("legal", "baseline", "release")
    kinds = ("legal-approval", "baseline-evidence", "release-approval")
    gates: dict[str, dict[str, object]] = {}
    now = datetime.now(UTC)
    for index, name in enumerate(EXTERNAL_GATES):
        evidence = tmp_path / f"evidence-{index}.json"
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
    assert external_gate(path, repository, trust_root_public_key=root)["권위"] == "protected-ci"
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
