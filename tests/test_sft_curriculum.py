# pyright: reportUnknownMemberType=false
import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from tokenizers.trainers import BpeTrainer
from typer.testing import CliRunner

from llmex.chat.curriculum import (
    preflight_curriculum,
    prepare_curriculum,
    status_curriculum,
    validate_curriculum,
)
from llmex.cli import app
from llmex.config import SFTCurriculumConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.tokenizer.core import SPECIAL_TOKENS, build_tokenizer


def _tokenizer(path: Path) -> None:
    path.mkdir()
    tokenizer = build_tokenizer()
    tokenizer.train_from_iterator(
        [
            "<|user|>\n숫자만 답하세요",
            "<|assistant|>\n안전하고 간결한 답변",
            "암호를 기억하고 갱신했습니다",
        ],
        trainer=BpeTrainer(
            vocab_size=400, special_tokens=list(SPECIAL_TOKENS), show_progress=False
        ),
    )
    tokenizer.save(str(path / "tokenizer.json"))
    manifest = {
        "schema_version": 1,
        "vocab_size_actual": tokenizer.get_vocab_size(),
        "special_token_ids": {token: index for index, token in enumerate(SPECIAL_TOKENS)},
        "artifacts": {"tokenizer.json": {"sha256": sha256_file(path / "tokenizer.json")}},
    }
    (path / "tokenizer-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _row(identifier: str, split: str, user: str) -> dict[str, object]:
    messages = [
        {"role": "user", "content": user},
        {"role": "assistant", "content": f"{identifier}의 간결한 답변"},
    ]
    provenance = {
        "dataset": "curriculum-replay-test",
        "source": "local-test",
        "license": "Apache-2.0",
        "collected_at": "2026-07-18",
        "source_id": identifier,
        "source_sha256": fingerprint({"source": identifier}),
    }
    basis = {"id": identifier, "messages": messages, "provenance": provenance, "split": split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _suite(path: Path, prompt: str = "평가 전용 문장입니다") -> None:
    row = {
        "schema_version": 1,
        "id": "curriculum-test",
        "category": "test",
        "provenance": {
            "dataset": "quality-test",
            "source": "local-test",
            "license": "MIT",
            "collected_at": "2026-07-18",
        },
        "turns": [{"user": prompt}],
    }
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> SFTCurriculumConfig:
    tokenizer = tmp_path / "tokenizer"
    _tokenizer(tokenizer)
    train = tmp_path / "replay-train.jsonl"
    heldout = tmp_path / "replay-heldout.jsonl"
    _write_rows(
        train,
        [
            _row("train-suite-overlap", "train", "평가 전용 문장입니다"),
            _row("train-safe", "train", "replay 학습 전용 질문"),
        ],
    )
    _write_rows(heldout, [_row("heldout-safe", "heldout", "replay 검증 전용 질문")])
    suite = tmp_path / "suite.jsonl"
    _suite(suite)
    return SFTCurriculumConfig(
        name="curriculum-test",
        seed=7,
        tokenizer_dir=tokenizer,
        replay_train_data=train,
        replay_heldout_data=heldout,
        suite=suite,
        expected_suite_sha256=sha256_file(suite),
        output_dir=tmp_path / "curriculum",
        allowed_replay_licenses=["Apache-2.0"],
        train_rows_per_category=8,
        heldout_rows_per_category=2,
        replay_train_rows=1,
        replay_heldout_rows=1,
        max_seq_len=2_048,
        generation_reserve_tokens=64,
    )


def test_curriculum은_결정적_생성_replay와_모든_user_turn_비누출을_검증한다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    first = preflight_curriculum(config)
    second = preflight_curriculum(config)
    assert first == second
    assert first["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    selection = cast(dict[str, int], first["selection"])
    assert selection == {
        "generated_train": 72,
        "generated_heldout": 18,
        "replay_train": 1,
        "replay_heldout": 1,
    }
    materialized = prepare_curriculum(config)
    assert materialized["reused"] is False
    assert prepare_curriculum(config)["reused"] is True
    assert status_curriculum(config)["status"] == "ready"
    assert validate_curriculum(config)["fingerprint"] == materialized["fingerprint"]
    train_text = (config.output_dir / "train.jsonl").read_text(encoding="utf-8")
    assert "평가 전용 문장입니다" not in train_text
    assert "replay 학습 전용 질문" in train_text
    manifest = json.loads((config.output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["inputs"]["replay_train"]["excluded_suite_overlap"] == 1
    assert manifest["release_gate"] == "blocked"


def test_curriculum은_suite_pin과_출력_변조를_거부한다(tmp_path: Path) -> None:
    config = _fixture(tmp_path)
    with pytest.raises(IntegrityError, match="suite SHA"):
        preflight_curriculum(config.model_copy(update={"expected_suite_sha256": "0" * 64}))
    prepare_curriculum(config)
    with (config.output_dir / "train.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{}\n")
    with pytest.raises(IntegrityError, match="현재 입력/config"):
        validate_curriculum(config)


def test_focused_v2는_실패_범주를_분리하고_v1_bytes를_바꾸지_않는다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    v1 = preflight_curriculum(config)
    focused = config.model_copy(
        update={
            "name": "curriculum-focused-v2-test",
            "generator_profile": "focused-v2",
            "output_dir": tmp_path / "focused",
        }
    )
    result = preflight_curriculum(focused)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert {
        "fact",
        "arithmetic",
        "context",
        "harmful-self",
        "harmful-explosive",
        "harmful-jailbreak",
        "harmful-pii-secret",
        "eos",
    } <= set(mass)
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert preflight_curriculum(config) == v1


def test_focused_v3는_잔여_실패만_분리하고_이전_profile을_바꾸지_않는다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v2 = config.model_copy(update={"generator_profile": "focused-v2"})
    previous = preflight_curriculum(focused_v2)
    focused_v3 = config.model_copy(
        update={
            "name": "curriculum-focused-v3-test",
            "generator_profile": "focused-v3",
            "output_dir": tmp_path / "focused-v3",
        }
    )
    result = preflight_curriculum(focused_v3)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {
        "context",
        "eos",
        "harmful-explosive",
        "harmful-pii-secret",
        "instruction",
        "korean",
        "replay",
        "uncertainty",
    }
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert preflight_curriculum(focused_v2) == previous


def test_curriculum_config와_CLI가_엄격한_종류를_지원한다(tmp_path: Path) -> None:
    config = _fixture(tmp_path)
    config_path = tmp_path / "curriculum.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app, ["config", "validate", "--kind", "sft-curriculum", str(config_path)]
    )
    assert result.exit_code == 0
    result = CliRunner().invoke(app, ["sft", "curriculum-preflight", "--config", str(config_path)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "ok"
