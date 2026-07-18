import json
from pathlib import Path

from typer.testing import CliRunner

from llmex.chat.data import ChatRow
from llmex.chat.multilingual import prepare_multilingual_prompts
from llmex.chat.quality import QualityScenario
from llmex.cli import app


def _rows(path: Path) -> list[ChatRow]:
    return [
        ChatRow.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_다국어_prompt_inventory는_두_teacher와_split을_결정적으로_분리한다(
    tmp_path: Path,
) -> None:
    output = tmp_path / "multilingual"
    first = prepare_multilingual_prompts(output, train_rows_per_task=3, heldout_rows_per_task=1)
    assert first["reused"] is False
    assert first["rows_per_teacher"] == 24
    assert first["split_rows_per_teacher"] == {"train": 18, "heldout": 6}
    assert (
        prepare_multilingual_prompts(output, train_rows_per_task=3, heldout_rows_per_task=1)[
            "reused"
        ]
        is True
    )

    qwen = _rows(output / "qwen.jsonl")
    gemma = _rows(output / "gemma.jsonl")
    assert len(qwen) == len(gemma) == 24
    assert {row.provenance.license for row in [*qwen, *gemma]} == {"MIT"}
    assert sum(row.split == "heldout" for row in qwen) == 6
    prompts = [row.messages[0].content for row in [*qwen, *gemma]]
    assert len(set(prompts)) == len(prompts)
    tasks = {
        str(row.provenance.source_metadata["task"])
        for row in qwen
        if row.provenance.source_metadata is not None
    }
    assert tasks == {"conversation-en", "conversation-ja", "ko-en", "en-ko", "ko-ja", "ja-ko"}


def test_다국어_prompt_CLI는_재현_manifest를_출력한다(tmp_path: Path) -> None:
    output = tmp_path / "cli-multilingual"
    result = CliRunner().invoke(
        app,
        [
            "data",
            "multilingual-prompts",
            "--output",
            str(output),
            "--train-rows-per-task",
            "2",
            "--heldout-rows-per-task",
            "1",
        ],
    )
    assert result.exit_code == 0
    value = json.loads(result.stdout)
    assert value["rows_per_teacher"] == 18
    assert value["prompt_overlap"] == 0
    assert (output / "manifest.json").is_file()


def test_다국어_품질_suite는_6개_task와_108응답을_비누출로_계획한다(
    tmp_path: Path,
) -> None:
    suite_path = Path("data/evaluation/multilingual-conversation-translation-v1.jsonl")
    scenarios = [
        QualityScenario.model_validate(json.loads(line))
        for line in suite_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(scenarios) == 18
    assert len({scenario.id for scenario in scenarios}) == 18
    assert {scenario.category for scenario in scenarios} == {
        "conversation-en",
        "conversation-ja",
        "translation-ko-en",
        "translation-en-ko",
        "translation-ko-ja",
        "translation-ja-ko",
    }
    suite_prompts = {turn.user for scenario in scenarios for turn in scenario.turns}
    assert len(suite_prompts) == 18
    assert sum(len(scenario.turns) for scenario in scenarios) * 6 == 108

    inventory = tmp_path / "inventory"
    prepare_multilingual_prompts(inventory, train_rows_per_task=4, heldout_rows_per_task=2)
    inventory_prompts = {
        row.messages[0].content
        for teacher in ("qwen", "gemma")
        for row in _rows(inventory / f"{teacher}.jsonl")
    }
    assert not suite_prompts.intersection(inventory_prompts)
