import sys
from pathlib import Path

import yaml
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import PipelineConfig
from llmex.pipeline import export, preflight, recovery_drill, run


def test_pipeline_preflight_resume_external_gate_drill_and_export(tmp_path: Path) -> None:
    output = tmp_path / "완료.txt"
    evidence = tmp_path / "승인.json"
    config = PipelineConfig.model_validate(
        {
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
                        f"from pathlib import Path; Path({str(output)!r}).write_text('통과')",
                    ],
                    "outputs": [str(output)],
                },
                {"name": "external", "command": [sys.executable, "-c", "pass"], "external": True},
            ],
        }
    )
    assert preflight(config)["판정"] == "통과"
    first = run(config)
    assert first["상태"] == "외부 게이트 대기"
    evidence.write_text("{}", encoding="utf-8")
    second = run(config, allow_external=True)
    assert second["상태"] == "완료"
    assert recovery_drill(config)["판정"] == "통과"
    assert export(config)["metrics_count"] == 0
    assert (config.run_dir / "run-manifest.json").is_file()
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    runner = CliRunner()
    assert runner.invoke(app, ["pipeline", "status", "--config", str(config_path)]).exit_code == 0


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
    try:
        PipelineConfig.model_validate(payload)
    except ValueError as error:
        assert "승인 예산" in str(error)
    else:
        raise AssertionError("예산 초과 설정이 승인됨")
