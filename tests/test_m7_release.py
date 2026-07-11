import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llmex.cli import app
from llmex.errors import IntegrityError
from llmex.release import audit, bundle, external_gate

ROOT = Path(__file__).parents[1]


def test_release_audit_and_bundle(tmp_path: Path) -> None:
    assert audit(ROOT)["판정"] == "통과"
    output = tmp_path / "재현"
    result = bundle(ROOT, output)
    assert result["버전"] == "1.0.0"
    checksums = json.loads((output / "checksums.json").read_text(encoding="utf-8"))
    assert any(item["path"] == "NOTICE.md" for item in checksums["files"])
    sbom = json.loads((output / "sbom.cdx.json").read_text(encoding="utf-8"))
    assert sbom["bomFormat"] == "CycloneDX"
    provenance = json.loads((output / "provenance.intoto.json").read_text(encoding="utf-8"))
    assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"


def test_external_gate_fails_closed_and_accepts_complete_approval(tmp_path: Path) -> None:
    path = tmp_path / "승인.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(IntegrityError):
        external_gate(path)
    gate = {
        "approved": True,
        "승인자": "독립 검토자",
        "시각": "2026-07-11T00:00:00Z",
        "근거": "검토 기록 SHA-256",
    }
    path.write_text(
        json.dumps(
            {"법무 검토": gate, "장기 baseline": gate, "공개 배포 결정": gate}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    assert external_gate(path)["판정"] == "승인"


def test_release_cli_gate_missing_file_is_input_error(tmp_path: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["release", "audit"]).exit_code == 0
    result = runner.invoke(app, ["release", "gate", "--approvals", str(tmp_path / "없음.json")])
    assert result.exit_code == 3
