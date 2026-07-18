import bz2
import json
from pathlib import Path

from typer.testing import CliRunner

from llmex.cli import app
from llmex.fingerprint import fingerprint, sha256_file
from llmex.logging import JsonFormatter
from llmex.paths import project_root, resolve_from_root

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/kowiki-sample.xml.bz2"


def test_fixture_is_offline_bz2_mediawiki_xml() -> None:
    content = bz2.decompress(FIXTURE.read_bytes()).decode("utf-8")
    assert '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"' in content
    assert "대한민국" in content
    assert "<redirect title=" in content


def test_fingerprints_are_deterministic() -> None:
    assert fingerprint({"나": 2, "가": 1}) == fingerprint({"가": 1, "나": 2})
    assert len(sha256_file(FIXTURE)) == 64


def test_paths_resolve_from_repository() -> None:
    assert project_root(ROOT / "src/llmex") == ROOT
    assert resolve_from_root(Path("configs"), ROOT) == ROOT / "configs"


def test_json_formatter_has_stable_fields() -> None:
    import logging

    record = logging.LogRecord("test", logging.INFO, __file__, 1, "완료", (), None)
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "완료"


def test_cli_help_and_config_validation() -> None:
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "Wikipedia" in help_result.stdout
    result = runner.invoke(
        app,
        ["config", "validate", str(ROOT / "configs/model/smoke.yaml"), "--kind", "model"],
    )
    assert result.exit_code == 0
    assert '"name": "smoke"' in result.stdout


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "1.22.58"


def test_cli_returns_config_error_code(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("name: invalid\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["config", "validate", str(invalid), "--kind", "model"])
    assert result.exit_code == 2


def test_source_does_not_import_reference_tree() -> None:
    sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py"))
    assert "0.ref" not in sources
    assert "llm_math" not in sources
