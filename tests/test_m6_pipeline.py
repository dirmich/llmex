# pyright: reportArgumentType=false
import base64
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import PipelineConfig, PipelineStageConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.pipeline import export, preflight, recovery_drill, run


def _public(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def _sign(value: dict[str, object], key: Ed25519PrivateKey) -> dict[str, object]:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**value, "signature": base64.b64encode(key.sign(canonical.encode())).decode()}


def _repository(tmp_path: Path) -> tuple[Path, Ed25519PrivateKey, str]:
    root_key, issuer_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    repository = tmp_path / "subject"
    repository.mkdir()
    (repository / ".llmex").mkdir()
    policy = {
        "schema_version": 2,
        "issuers": {
            "baseline-ci": {
                "public_key": _public(issuer_key),
                "roles": ["baseline"],
                "kinds": ["baseline-evidence", "resource-usage"],
            }
        },
    }
    policy_path = repository / ".llmex/trust-policy.json"
    policy_path.write_text(json.dumps(_sign(policy, root_key)))
    policy_path.chmod(0o600)
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
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
    return repository, issuer_key, _public(root_key)


def _telemetry_command(key: Ed25519PrivateKey) -> list[str]:
    private = base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    script = """
import base64,json,os,pathlib
from datetime import UTC,datetime,timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
subject={
    'nonce':os.environ['LLMEX_STAGE_NONCE'],
    'run_id':os.environ['LLMEX_RUN_ID'],
    'stage':os.environ['LLMEX_STAGE_NAME'],
    'budget':json.loads(os.environ['LLMEX_BUDGET_JSON']),
    'git_commit':os.environ['LLMEX_GIT_COMMIT'],
    'config_fingerprint':os.environ['LLMEX_CONFIG_FINGERPRINT'],
}
now=datetime.now(UTC)
value={'schema_version':1,'kind':'resource-usage','issuer':'baseline-ci','role':'baseline','issued_at':now.isoformat(),'expires_at':(now+timedelta(hours=1)).isoformat(),'subject':subject,'final':True,'tokens':10,'energy_kwh':0.1}
canonical=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
key=Ed25519PrivateKey.from_private_bytes(base64.b64decode(PRIVATE_KEY))
value['signature']=base64.b64encode(key.sign(canonical)).decode()
pathlib.Path(os.environ['LLMEX_TELEMETRY_PATH']).write_text(json.dumps(value))
"""
    return [sys.executable, "-c", f"PRIVATE_KEY={private!r}\n{script}"]


def _config(
    tmp_path: Path,
    evidence: Path,
    output: Path,
    repository: Path,
    issuer_key: Ed25519PrivateKey,
) -> PipelineConfig:
    payload = {
        "name": "m6-test",
        "run_dir": str(tmp_path / "run"),
        "subject_repository": str(repository),
        "budget": {
            "minimum_free_disk_gib": 0.001,
            "minimum_available_memory_gib": 0.001,
            "maximum_hours": 1.0,
            "maximum_energy_kwh": 1.0,
            "maximum_parameters": 120_000_000,
            "token_budget": 1000,
        },
        "selected_tokenizer": 16000,
        "baseline_parameters": 100_000_000,
        "required_evidence": [str(evidence)],
        "stages": [
            {
                "name": "local",
                "command": [
                    sys.executable,
                    "-c",
                    f"import json,pathlib; pathlib.Path({str(output)!r}).write_text(json.dumps({{'schema_version':1,'result':'통과'}}))",  # noqa: E501
                ],
                "outputs": [str(output)],
            },
            {
                "name": "external",
                "command": _telemetry_command(issuer_key),
                "external": True,
            },
        ],
    }
    return PipelineConfig.model_validate(payload)


def _write_evidence(
    path: Path, config: PipelineConfig, repository: Path, key: Ed25519PrivateKey
) -> None:
    artifact = path.parent / "근거.txt"
    artifact.write_text("검토 완료")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True, text=True, capture_output=True
    ).stdout.strip()
    now = datetime.now(UTC)
    value: dict[str, object] = {
        "schema_version": 1,
        "kind": "baseline-evidence",
        "issuer": "baseline-ci",
        "role": "baseline",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "subject": {
            "git_commit": commit,
            "config_fingerprint": fingerprint(config.model_dump(mode="json")),
        },
        "artifact": {"path": artifact.name, "sha256": sha256_file(artifact)},
    }
    path.write_text(json.dumps(_sign(value, key)))


def _write_telemetry(
    config: PipelineConfig,
    repository: Path,
    key: Ed25519PrivateKey,
    *,
    nonce: str = "past-valid-nonce",
    **updates: object,
) -> Path:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True, text=True, capture_output=True
    ).stdout.strip()
    now = datetime.now(UTC)
    value: dict[str, object] = {
        "schema_version": 1,
        "kind": "resource-usage",
        "issuer": "baseline-ci",
        "role": "baseline",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "subject": {
            "git_commit": commit,
            "config_fingerprint": fingerprint(config.model_dump(mode="json")),
            "stage": "external",
            "run_id": fingerprint(
                {
                    "commit": commit,
                    "config_fingerprint": fingerprint(config.model_dump(mode="json")),
                    "run_dir": str(config.run_dir.resolve()),
                }
            ),
            "nonce": nonce,
            "budget": {"token_budget": 1000, "maximum_energy_kwh": 1.0},
        },
        "final": True,
        "tokens": 10,
        "energy_kwh": 0.1,
    }
    value.update(updates)
    path = config.run_dir.parent / "telemetry-template.json"
    path.write_text(json.dumps(_sign(value, key)))
    return path


def test_pipeline_signed_evidence_telemetry_resume_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, secret, root = _repository(tmp_path)
    output, evidence = tmp_path / "완료.json", tmp_path / "승인.json"
    config = _config(tmp_path, evidence, output, repository, secret)
    assert preflight(config)["판정"] == "통과"
    assert run(config, trust_root_public_key=root)["상태"] == "외부 게이트 대기"
    evidence.write_text(json.dumps({"schema_version": 1, "kind": "anything", "issuer": "self"}))
    assert (
        run(config, allow_external=True, trust_root_public_key=root)["상태"] == "외부 게이트 대기"
    )
    _write_evidence(evidence, config, repository, secret)
    assert run(config, allow_external=True, trust_root_public_key=root)["상태"] == "완료"
    output.write_text('{"schema_version":1,"result":"변조"}')
    assert run(config, allow_external=True, trust_root_public_key=root)["단계"]["local"]["outputs"][
        0
    ]["sha256"] == sha256_file(output)
    assert recovery_drill(config)["판정"] == "통과"
    assert export(config)["metrics_count"] == 0
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True))
    assert (
        CliRunner().invoke(app, ["pipeline", "status", "--config", str(config_path)]).exit_code == 0
    )


def test_pipeline_rejects_architect_self_attestation_and_mutations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, secret, root = _repository(tmp_path)
    evidence, output = tmp_path / "e.json", tmp_path / "o.json"
    config = _config(tmp_path, evidence, output, repository, secret)
    _write_evidence(evidence, config, repository, secret)
    original = json.loads(evidence.read_text())
    for field, bad in (("kind", "anything"), ("role", "release"), ("issued_at", "not-a-time")):
        value = json.loads(json.dumps(original))
        value[field] = bad
        evidence.write_text(json.dumps(value))
        assert (
            run(config, allow_external=True, trust_root_public_key=root)["상태"]
            == "외부 게이트 대기"
        )
    value = json.loads(json.dumps(original))
    value["subject"]["git_commit"] = "0" * 40
    evidence.write_text(json.dumps(value))
    assert (
        run(config, allow_external=True, trust_root_public_key=root)["상태"] == "외부 게이트 대기"
    )
    value = json.loads(json.dumps(original))
    value["signature"] = base64.b64encode(b"0" * 64).decode()
    evidence.write_text(json.dumps(value))
    assert (
        run(config, allow_external=True, trust_root_public_key=root)["상태"] == "외부 게이트 대기"
    )


@pytest.mark.parametrize("attack", ["unsigned", "not-final", "tampered", "over-budget"])
def test_external_final_telemetry_is_authoritative_post_execution_gate(
    tmp_path: Path, attack: str
) -> None:
    repository, issuer, root = _repository(tmp_path)
    evidence, output = tmp_path / "e.json", tmp_path / "o.json"
    config = _config(tmp_path, evidence, output, repository, issuer)
    command = _telemetry_command(issuer)
    script = command[2]
    if attack == "unsigned":
        script += (
            "\nvalue.pop('signature'); "
            "pathlib.Path(os.environ['LLMEX_TELEMETRY_PATH']).write_text(json.dumps(value))"
        )
    elif attack == "not-final":
        script = script.replace("'final':True", "'final':False")
    elif attack == "tampered":
        script += (
            "\nvalue['tokens']=11; "
            "pathlib.Path(os.environ['LLMEX_TELEMETRY_PATH']).write_text(json.dumps(value))"
        )
    elif attack == "over-budget":
        script = script.replace("'tokens':10", "'tokens':1001")
    config.stages[1].command = [sys.executable, "-c", script]
    _write_evidence(evidence, config, repository, issuer)
    with pytest.raises(IntegrityError, match="pipeline 단계가 실패했습니다"):
        run(config, allow_external=True, trust_root_public_key=root)
    state = json.loads((config.run_dir / "pipeline-status.json").read_text())
    assert state["상태"] == "실패"
    assert state["단계"]["external"]["상태"] == "실패"


def test_external_rejects_different_valid_past_telemetry_replay(tmp_path: Path) -> None:
    repository, issuer, root = _repository(tmp_path)
    evidence, output = tmp_path / "e.json", tmp_path / "o.json"
    config = _config(tmp_path, evidence, output, repository, issuer)
    replay = config.run_dir.parent / "telemetry-template.json"
    config.stages[1].command = [
        sys.executable,
        "-c",
        (
            "import shutil; "
            f"shutil.copyfile({str(replay)!r}, "
            f"{str(config.run_dir / 'resource-usage.json')!r})"
        ),
    ]
    _write_evidence(evidence, config, repository, issuer)
    first = _write_telemetry(config, repository, issuer, nonce="past-valid-nonce-a")
    config.run_dir.mkdir()
    (config.run_dir / "resource-usage.json").write_bytes(first.read_bytes())
    _write_telemetry(
        config,
        repository,
        issuer,
        nonce="past-valid-nonce-b",
        tokens=11,
    )
    assert sha256_file(config.run_dir / "resource-usage.json") != sha256_file(replay)
    with pytest.raises(IntegrityError, match="pipeline 단계가 실패했습니다"):
        run(config, allow_external=True, trust_root_public_key=root)


def test_pipeline_revalidates_authoritative_telemetry_before_success(tmp_path: Path) -> None:
    repository, issuer, root = _repository(tmp_path)
    evidence, output = tmp_path / "e.json", tmp_path / "o.json"
    config = _config(tmp_path, evidence, output, repository, issuer)
    external, local = config.stages[1], config.stages[0]
    local.command = [
        sys.executable,
        "-c",
        (
            "import json,pathlib; "
            f"pathlib.Path({str(config.run_dir / 'resource-usage.json')!r}).write_text("
            "json.dumps({'schema_version':1,'tokens':0,'energy_kwh':0})); "
            f"pathlib.Path({str(output)!r}).write_text(json.dumps({{'schema_version':1}}))"
        ),
    ]
    config.stages = [external, local]
    _write_evidence(evidence, config, repository, issuer)
    with pytest.raises(IntegrityError, match="최종 telemetry 재검증"):
        run(config, allow_external=True, trust_root_public_key=root)
    state = json.loads((config.run_dir / "pipeline-status.json").read_text())
    assert state["상태"] == "실패"


def test_pipeline_budget_enforced_during_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, _, _ = _repository(tmp_path)
    evidence, output = tmp_path / "e.json", tmp_path / "o.json"
    config = _config(
        tmp_path, evidence, output, repository, Ed25519PrivateKey.generate()
    ).model_copy(
        update={
            "required_evidence": [],
            "stages": [
                PipelineStageConfig.model_validate(
                    {
                        "name": "budget",
                        "command": [
                            sys.executable,
                            "-c",
                            f"import json,pathlib,time; pathlib.Path({str(tmp_path / 'run/resource-usage.json')!r}).write_text(json.dumps({{'tokens':1001,'energy_kwh':0}})); time.sleep(2)",  # noqa: E501
                        ],
                        "outputs": [],
                    }
                )
            ],
        }
    )
    with pytest.raises(IntegrityError, match="예산"):
        run(config)


def test_pipeline_rejects_over_baseline() -> None:
    payload = {
        "name": "invalid",
        "run_dir": "runs/x",
        "subject_repository": ".",
        "budget": {
            "minimum_free_disk_gib": 1.0,
            "minimum_available_memory_gib": 1.0,
            "maximum_hours": 1.0,
            "maximum_energy_kwh": 1.0,
            "maximum_parameters": 100_000_000,
            "token_budget": 1,
        },
        "selected_tokenizer": 16000,
        "baseline_parameters": 110_000_000,
        "stages": [{"name": "x", "command": ["true"]}],
    }
    with pytest.raises(ValueError, match="승인 예산"):
        PipelineConfig.model_validate(payload)
