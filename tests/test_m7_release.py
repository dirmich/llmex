import hashlib
import hmac
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
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
    assert result["버전"] == "1.1.1"
    artifacts = json.loads((output / "artifact-checksums.json").read_text())["artifacts"]
    provenance = json.loads((output / "provenance.intoto.json").read_text())
    assert {row["digest"]["sha256"] for row in provenance["subject"]} == {
        row["sha256"] for row in artifacts
    }
    sbom = json.loads((output / "sbom.cdx.json").read_text())
    assert sbom["metadata"]["properties"][0]["value"] == next(
        row["sha256"] for row in artifacts if row["name"].endswith(".whl")
    )


def _approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    issuers = {f"ci-{index}": f"secret-{index}" for index in range(3)}
    roles = {f"ci-{index}": [role] for index, role in enumerate(("legal", "baseline", "release"))}
    monkeypatch.setenv("LLMEX_APPROVAL_KEYS", json.dumps(issuers))
    monkeypatch.setenv("LLMEX_APPROVAL_ROLES", json.dumps(roles))
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True, capture_output=True
    ).stdout.strip()
    target = {"version": __version__, "git_commit": commit, "config_fingerprint": "a" * 64}
    gates = {}
    now = datetime.now(UTC)
    for index, name in enumerate(EXTERNAL_GATES):
        evidence = tmp_path / f"evidence-{index}.json"
        evidence.write_text(json.dumps({"schema_version": 1, "approved": True}))
        item = {
            "approved": True,
            "issuer": f"ci-{index}",
            "role": roles[f"ci-{index}"][0],
            "approver": f"person-{index}",
            "issued_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "evidence": {"path": evidence.name, "sha256": sha256_file(evidence)},
        }
        canonical = json.dumps(
            {"gate": name, "target": target, **item},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        item["signature"] = hmac.new(
            issuers[f"ci-{index}"].encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()
        gates[name] = item
    path = tmp_path / "approval.json"
    path.write_text(
        json.dumps({"schema_version": 1, "target": target, "gates": gates}, ensure_ascii=False)
    )
    return path


def test_external_gate_signature_expiry_identity_digest_and_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _approval(tmp_path, monkeypatch)
    assert external_gate(path)["판정"] == "승인"
    original = json.loads(path.read_text())
    for mutation in ("signature", "approver", "digest", "commit"):
        value = json.loads(json.dumps(original))
        if mutation == "signature":
            value["gates"][EXTERNAL_GATES[0]]["signature"] = "0" * 64
        elif mutation == "approver":
            value["gates"][EXTERNAL_GATES[1]]["approver"] = "person-0"
        elif mutation == "digest":
            value["gates"][EXTERNAL_GATES[0]]["evidence"]["sha256"] = "0" * 64
        else:
            value["target"]["git_commit"] = "0" * 40
        path.write_text(json.dumps(value))
        with pytest.raises(IntegrityError):
            external_gate(path)
    path.write_text("{}")
    with pytest.raises(IntegrityError):
        external_gate(path)


def test_release_cli_gate_missing_file_is_input_error(tmp_path: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["release", "audit"]).exit_code == 0
    assert (
        runner.invoke(
            app, ["release", "gate", "--approvals", str(tmp_path / "없음.json")]
        ).exit_code
        == 3
    )
