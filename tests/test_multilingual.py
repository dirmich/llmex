import json
from pathlib import Path
from typing import cast

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


def test_expanded_v2는_대규모_자유대화와_번역_prompt를_비누출로_생성한다(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "expanded"
    result = prepare_multilingual_prompts(
        inventory,
        train_rows_per_task=40,
        heldout_rows_per_task=10,
        profile="expanded-v2",
    )
    assert result["profile"] == "expanded-v2"
    assert result["rows_per_teacher"] == 300
    rows = [row for teacher in ("qwen", "gemma") for row in _rows(inventory / f"{teacher}.jsonl")]
    prompts = [row.messages[0].content for row in rows]
    assert len(prompts) == len(set(prompts)) == 600
    assert {row.provenance.dataset for row in rows} == {
        "llmex-multilingual-teacher-prompts-expanded-v2"
    }
    metadata = [cast(dict[str, str | int], row.provenance.source_metadata) for row in rows]
    assert all(item["profile"] == "expanded-v2" for item in metadata)

    scenarios = [
        QualityScenario.model_validate(json.loads(line))
        for line in Path("data/evaluation/multilingual-conversation-translation-v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    suite_prompts = {turn.user for scenario in scenarios for turn in scenario.turns}
    assert not suite_prompts.intersection(prompts)


def test_natural_v3는_일련번호_없이_teacher별_6천_prompt를_분리한다(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "natural"
    result = prepare_multilingual_prompts(
        inventory,
        train_rows_per_task=800,
        heldout_rows_per_task=200,
        profile="natural-v3",
    )
    assert result["profile"] == "natural-v3"
    assert result["rows_per_teacher"] == 6000
    assert result["outputs"] == {
        "qwen": {
            "path": str(inventory / "qwen.jsonl"),
            "sha256": "6568b13802613221084a4d3a7f8f80b0ee51f38238928941adb727becdcceca8",
        },
        "gemma": {
            "path": str(inventory / "gemma.jsonl"),
            "sha256": "2648e1de7cf29b2238849f70a8afe52e4c1c539604d261e07a2d8d17586c8d18",
        },
    }
    rows = [row for teacher in ("qwen", "gemma") for row in _rows(inventory / f"{teacher}.jsonl")]
    prompts = [row.messages[0].content for row in rows]
    assert len(prompts) == len(set(prompts)) == 12000
    assert all("Reference " not in prompt and "整理番号" not in prompt for prompt in prompts)
    assert not any(
        "현우은" in prompt or "지호은" in prompt or "수아은" in prompt for prompt in prompts
    )
    assert not any("책 " in prompt and "개를" in prompt for prompt in prompts)
    assert not any("사진 " in prompt and "개를" in prompt for prompt in prompts)
    assert not any("보고서 " in prompt and "개를" in prompt for prompt in prompts)
    assert not any("개을" in prompt or "부을" in prompt for prompt in prompts)
    assert not any("今日は葵です" in prompt or "今週は葵です" in prompt for prompt in prompts)
    assert not any("\u30ceートを2個" in prompt or "写真を2個" in prompt for prompt in prompts)
    assert {row.provenance.dataset for row in rows} == {
        "llmex-multilingual-teacher-prompts-natural-v3"
    }
    qwen_rows = _rows(inventory / "qwen.jsonl")
    gemma_rows = _rows(inventory / "gemma.jsonl")
    qwen_indexes = {
        cast(dict[str, str | int], row.provenance.source_metadata)["prompt_index"]
        for row in qwen_rows
    }
    gemma_indexes = {
        cast(dict[str, str | int], row.provenance.source_metadata)["prompt_index"]
        for row in gemma_rows
    }
    assert qwen_indexes == set(range(1000))
    assert gemma_indexes == set(range(1024, 2024))
    assert not qwen_indexes.intersection(gemma_indexes)
    for teacher_rows in (qwen_rows, gemma_rows):
        train_c = {
            cast(
                int,
                cast(dict[str, str | int], row.provenance.source_metadata)["combination_index"],
            )
            // 256
            % 8
            for row in teacher_rows
            if row.split == "train"
        }
        heldout_c = {
            cast(
                int,
                cast(dict[str, str | int], row.provenance.source_metadata)["combination_index"],
            )
            // 256
            % 8
            for row in teacher_rows
            if row.split == "heldout"
        }
        assert train_c == heldout_c == set(range(8))


def test_natural_v4는_검증가능한_conversation_act를_metadata에_결속한다(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "natural-v4"
    result = prepare_multilingual_prompts(
        inventory,
        train_rows_per_task=800,
        heldout_rows_per_task=200,
        profile="natural-v4",
    )

    assert result["profile"] == "natural-v4"
    assert result["rows_per_teacher"] == 6000
    assert result["outputs"] == {
        "qwen": {
            "path": str(inventory / "qwen.jsonl"),
            "sha256": "c0e9db62b67890e9482184ca6a6ad4413774f594bdf13355a358875651bae719",
        },
        "gemma": {
            "path": str(inventory / "gemma.jsonl"),
            "sha256": "7959e749fa508a67fb3603e7567341ffeede8368f503db5ba1c25da10ef657dc",
        },
    }
    rows = [row for teacher in ("qwen", "gemma") for row in _rows(inventory / f"{teacher}.jsonl")]
    all_prompts = [row.messages[0].content for row in rows]
    assert len(all_prompts) == len(set(all_prompts)) == 12000
    conversation_rows = [
        row
        for row in rows
        if str(cast(dict[str, str | int], row.provenance.source_metadata)["task"]).startswith(
            "conversation-"
        )
    ]
    metadata = [
        cast(dict[str, str | int], row.provenance.source_metadata) for row in conversation_rows
    ]
    assert {item["conversation_act"] for item in metadata} == {"question", "suggestion"}
    prompts = [row.messages[0].content for row in conversation_rows]
    assert not any("without echoing" in prompt or "繰り返さず" in prompt for prompt in prompts)
    assert all(
        ("exactly one brief question" in prompt or "one practical, safe suggestion" in prompt)
        if metadata[index]["task"] == "conversation-en"
        else ("短い質問を一つだけ" in prompt or "具体的な提案を一つ" in prompt)
        for index, prompt in enumerate(prompts)
    )
    assert all(row.provenance.response_quality is not None for row in rows)
    assert all(
        row.provenance.response_quality is not None
        and row.provenance.response_quality.mode
        == "conversation-"
        + str(cast(dict[str, str | int], row.provenance.source_metadata)["conversation_act"])
        for row in conversation_rows
    )
    assert {
        (
            row.split,
            cast(dict[str, str | int], row.provenance.source_metadata)["task"],
            cast(dict[str, str | int], row.provenance.source_metadata)["conversation_act"],
        )
        for row in conversation_rows
    } == {
        (split, task, act)
        for split in ("train", "heldout")
        for task in ("conversation-en", "conversation-ja")
        for act in ("question", "suggestion")
    }
