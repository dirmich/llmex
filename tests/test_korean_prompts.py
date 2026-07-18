import json
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from llmex.chat.data import ChatRow
from llmex.chat.korean_prompts import prepare_korean_conversation_prompts
from llmex.chat.quality import QualityScenario
from llmex.cli import app


def _rows(path: Path) -> list[ChatRow]:
    return [ChatRow.model_validate(json.loads(line)) for line in path.read_text().splitlines()]


def test_한국어_자연대화_inventory는_10개_범주와_split을_결정적으로_분리한다(
    tmp_path: Path,
) -> None:
    output = tmp_path / "korean"
    first = prepare_korean_conversation_prompts(
        output, train_rows_per_category=4, heldout_rows_per_category=2
    )
    assert first["rows"] == 60
    assert first["split_rows"] == {"train": 40, "heldout": 20}
    assert len(cast(list[str], first["categories"])) == 10
    assert (
        prepare_korean_conversation_prompts(
            output, train_rows_per_category=4, heldout_rows_per_category=2
        )["reused"]
        is True
    )
    rows = _rows(output / "prompts.jsonl")
    prompts = [row.messages[0].content for row in rows]
    assert len(prompts) == len(set(prompts)) == 60
    assert {row.provenance.license for row in rows} == {"MIT"}

    suite = Path("data/evaluation/ko-multilingual-chat-quality-v1.jsonl")
    scenarios = [
        QualityScenario.model_validate(json.loads(line))
        for line in suite.read_text(encoding="utf-8").splitlines()
    ]
    suite_prompts = {turn.user for scenario in scenarios for turn in scenario.turns}
    assert not suite_prompts.intersection(prompts)


def test_한국어_자연대화_prompt_CLI는_manifest를_출력한다(tmp_path: Path) -> None:
    output = tmp_path / "cli"
    result = CliRunner().invoke(
        app,
        [
            "data",
            "korean-conversation-prompts",
            "--output",
            str(output),
            "--train-rows-per-category",
            "2",
            "--heldout-rows-per-category",
            "1",
        ],
    )
    assert result.exit_code == 0
    value = json.loads(result.stdout)
    assert value["rows"] == 30
    assert value["prompt_overlap"] == 0


def test_natural_v2는_조사_오류와_큰_일련번호_없이_1만_prompt를_만든다(
    tmp_path: Path,
) -> None:
    output = tmp_path / "natural"
    result = prepare_korean_conversation_prompts(
        output,
        train_rows_per_category=800,
        heldout_rows_per_category=200,
        profile="natural-v2",
    )
    assert result["profile"] == "natural-v2"
    assert result["rows"] == 10000
    rows = _rows(output / "prompts.jsonl")
    prompts = [row.messages[0].content for row in rows]
    assert len(prompts) == len(set(prompts)) == 10000
    assert not any("독서을" in prompt or "산책를" in prompt for prompt in prompts)
    assert not any("Reference " in prompt or "번 작업" in prompt for prompt in prompts)
    assert not any(
        "해요 자연스럽게" in prompt or "해요 이 이야기에" in prompt for prompt in prompts
    )
    assert not any(
        "민준와" in prompt or "하린와" in prompt or "나은와" in prompt for prompt in prompts
    )
    assert not any("천 원" in prompt or "집의" in prompt for prompt in prompts)
    metadata = [cast(dict[str, str | int], row.provenance.source_metadata) for row in rows]
    train_indexes = {
        item["prompt_index"]
        for row, item in zip(rows, metadata, strict=True)
        if row.split == "train"
    }
    heldout_indexes = {
        item["prompt_index"]
        for row, item in zip(rows, metadata, strict=True)
        if row.split == "heldout"
    }
    assert train_indexes == set(range(800))
    assert heldout_indexes == set(range(800, 1000))
    assert not train_indexes.intersection(heldout_indexes)
    train_c = {
        cast(int, item["combination_index"]) // 256 % 8
        for row, item in zip(rows, metadata, strict=True)
        if row.split == "train"
    }
    heldout_c = {
        cast(int, item["combination_index"]) // 256 % 8
        for row, item in zip(rows, metadata, strict=True)
        if row.split == "heldout"
    }
    assert train_c == heldout_c == set(range(8))
