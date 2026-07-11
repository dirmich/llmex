import json
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import PipelineConfig, PipelineStageConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.pipeline import export, preflight, recovery_drill, run


def _config(tmp_path: Path, evidence: Path, output: Path) -> PipelineConfig:
    payload = {
        "name": "m6-test",
        "run_dir": str(tmp_path / "run"),
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
            {"name": "external", "command": [sys.executable, "-c", "pass"], "external": True},
        ],
    }
    return PipelineConfig.model_validate(payload)


def test_pipeline_structured_evidence_resume_checksum_drill_and_export(tmp_path: Path) -> None:
    output, evidence, artifact = (
        tmp_path / "완료.json",
        tmp_path / "승인.json",
        tmp_path / "근거.txt",
    )
    config = _config(tmp_path, evidence, output)
    assert preflight(config)["판정"] == "통과"
    assert run(config)["상태"] == "외부 게이트 대기"
    evidence.write_text("{}")
    assert run(config, allow_external=True)["상태"] == "외부 게이트 대기"
    artifact.write_text("검토 완료")
    config_fp = fingerprint(config.model_dump(mode="json"))
    evidence.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "human-audit",
                "issuer": "protected-ci",
                "issued_at": "2026-07-11T00:00:00Z",
                "subject": {"config_fingerprint": config_fp},
                "artifact": {"path": artifact.name, "sha256": sha256_file(artifact)},
            }
        )
    )
    assert run(config, allow_external=True)["상태"] == "완료"
    output.write_text('{"schema_version":1,"result":"변조"}')
    assert run(config, allow_external=True)["단계"]["local"]["outputs"][0]["sha256"] == sha256_file(
        output
    )
    assert recovery_drill(config)["판정"] == "통과"
    assert export(config)["metrics_count"] == 0
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True))
    assert (
        CliRunner().invoke(app, ["pipeline", "status", "--config", str(config_path)]).exit_code == 0
    )


def test_pipeline_budget_enforced_during_stage(tmp_path: Path) -> None:
    evidence = tmp_path / "e.json"
    output = tmp_path / "o.json"
    config = _config(tmp_path, evidence, output).model_copy(
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
