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
from llmex.chat.runtime import preflight_sft
from llmex.cli import app
from llmex.config import ModelConfig, OptimizerConfig, SFTConfig, SFTCurriculumConfig
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


def test_runtime은_curriculum_manifest를_SFT_원천에_SHA로_결속한다(tmp_path: Path) -> None:
    config = _fixture(tmp_path)
    prepare_curriculum(config)
    tokenizer_manifest = json.loads(
        (config.tokenizer_dir / "tokenizer-manifest.json").read_text(encoding="utf-8")
    )
    source_manifest = config.output_dir / "manifest.json"
    sft = SFTConfig(
        name="curriculum-runtime-test",
        model=ModelConfig(
            name="tiny",
            vocab_size=tokenizer_manifest["vocab_size_actual"],
            max_seq_len=config.max_seq_len,
            n_layers=1,
            d_model=16,
            n_heads=2,
            n_kv_heads=1,
            ffn_hidden_size=32,
            dropout=0.0,
        ),
        tokenizer_dir=config.tokenizer_dir,
        train_data=config.output_dir / "train.jsonl",
        heldout_data=config.output_dir / "heldout.jsonl",
        source_manifest=source_manifest,
        expected_source_manifest_sha256=sha256_file(source_manifest),
        run_dir=tmp_path / "sft-run",
        allowed_licenses=["Apache-2.0", config.curriculum_license],
        device="cpu",
        sequence_length=config.max_seq_len,
        micro_batch_size=1,
        max_steps=1,
        validation_interval=1,
        validation_batches=1,
        checkpoint_interval=1,
        optimizer=OptimizerConfig(learning_rate=0.01, min_learning_rate=0.001),
        max_new_tokens=config.generation_reserve_tokens,
    )
    preflight = preflight_sft(sft)
    assert preflight["release_gate"] == "blocked"
    assert preflight["redistribution_allowed"] is False

    forged_path = tmp_path / "forged-curriculum-manifest.json"
    forged = json.loads(source_manifest.read_text(encoding="utf-8"))
    forged["kind"] = "unknown-curriculum"
    forged["fingerprint"] = fingerprint(
        {key: value for key, value in forged.items() if key != "fingerprint"}
    )
    forged_path.write_text(json.dumps(forged), encoding="utf-8")
    forged_sft = sft.model_copy(
        update={
            "source_manifest": forged_path,
            "expected_source_manifest_sha256": sha256_file(forged_path),
        }
    )
    with pytest.raises(IntegrityError, match="source manifest"):
        preflight_sft(forged_sft)


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


def test_focused_v4는_보존_replay와_네_가지_일반화_범주만_사용한다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v3 = config.model_copy(update={"generator_profile": "focused-v3"})
    previous = preflight_curriculum(focused_v3)
    focused_v4 = config.model_copy(
        update={
            "name": "curriculum-focused-v4-test",
            "generator_profile": "focused-v4",
            "output_dir": tmp_path / "focused-v4",
        }
    )
    result = preflight_curriculum(focused_v4)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {
        "context",
        "eos",
        "harmful-pii-secret",
        "korean",
        "replay",
    }
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert preflight_curriculum(focused_v3) == previous


def test_focused_v5는_접미_counterexample도_suite_전체_문장과_겹치지_않는다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v4 = config.model_copy(update={"generator_profile": "focused-v4"})
    previous = preflight_curriculum(focused_v4)
    focused_v5 = config.model_copy(
        update={
            "name": "curriculum-focused-v5-test",
            "generator_profile": "focused-v5",
            "output_dir": tmp_path / "focused-v5",
        }
    )
    result = preflight_curriculum(focused_v5)
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert result["source_overlap"] == 0
    assert preflight_curriculum(focused_v4) == previous


def test_focused_v6는_suite_핵심_앞부분을_보존하고_전체_prompt는_비누출이다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v5 = config.model_copy(update={"generator_profile": "focused-v5"})
    previous = preflight_curriculum(focused_v5)
    focused_v6 = config.model_copy(
        update={
            "name": "curriculum-focused-v6-test",
            "generator_profile": "focused-v6",
            "output_dir": tmp_path / "focused-v6",
        }
    )
    result = preflight_curriculum(focused_v6)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {"context", "eos", "korean", "replay", "uncertainty"}
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert result["source_overlap"] == 0
    assert preflight_curriculum(focused_v5) == previous


def test_focused_v7은_exact_문맥과_PII_거절만_가중하고_v6를_보존한다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v6 = config.model_copy(update={"generator_profile": "focused-v6"})
    previous = preflight_curriculum(focused_v6)
    focused_v7 = config.model_copy(
        update={
            "name": "curriculum-focused-v7-test",
            "generator_profile": "focused-v7",
            "output_dir": tmp_path / "focused-v7",
        }
    )
    result = preflight_curriculum(focused_v7)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {"context-exact", "harmful-pii-secret", "replay"}
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert result["source_overlap"] == 0
    assert preflight_curriculum(focused_v6) == previous


def test_focused_v8은_자연스러운_값만_형식과_suite_비누출을_보장한다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v7 = config.model_copy(update={"generator_profile": "focused-v7"})
    previous = preflight_curriculum(focused_v7)

    _suite(config.suite, "최종 마감일만 다시 알려 주세요.")
    focused_v8 = config.model_copy(
        update={
            "name": "curriculum-focused-v8-test",
            "generator_profile": "focused-v8",
            "expected_suite_sha256": sha256_file(config.suite),
            "output_dir": tmp_path / "focused-v8",
        }
    )
    result = preflight_curriculum(focused_v8)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {"format-exact", "replay"}
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert result["source_overlap"] == 0

    prepare_curriculum(focused_v8)
    generated: list[dict[str, object]] = []
    with (focused_v8.output_dir / "train.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = cast(dict[str, object], json.loads(line))
            if str(row["id"]).startswith("curriculum-train-format-exact-"):
                generated.append(row)
    assert len(generated) == focused_v8.train_rows_per_category
    date_rows: list[dict[str, object]] = [
        row
        for row in generated
        if any(
            message["content"] == "최종 마감일만 다시 알려 주세요"
            for message in cast(list[dict[str, str]], row["messages"])
        )
    ]
    assert date_rows
    for row in date_rows:
        messages = cast(list[dict[str, str]], row["messages"])
        assert messages[-1]["role"] == "assistant"
        assert messages[-1]["content"].startswith("9월 ")
        assert messages[-1]["content"].endswith("일")
        assert "갱신" not in messages[-1]["content"]

    _suite(config.suite)
    assert preflight_curriculum(focused_v7) == previous


def test_focused_v9는_PII_거절과_정상_안전_응답만_보정하고_v8을_보존한다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v8 = config.model_copy(update={"generator_profile": "focused-v8"})
    previous = preflight_curriculum(focused_v8)
    focused_v9 = config.model_copy(
        update={
            "name": "curriculum-focused-v9-test",
            "generator_profile": "focused-v9",
            "output_dir": tmp_path / "focused-v9",
        }
    )
    result = preflight_curriculum(focused_v9)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {"benign-safety", "harmful-pii-secret", "replay"}
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert result["source_overlap"] == 0
    assert preflight_curriculum(focused_v8) == previous


def test_focused_v10은_일상_대화와_근거_유무를_대조하고_v9을_보존한다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v9 = config.model_copy(update={"generator_profile": "focused-v9"})
    previous = preflight_curriculum(focused_v9)
    focused_v10 = config.model_copy(
        update={
            "name": "curriculum-focused-v10-test",
            "generator_profile": "focused-v10",
            "output_dir": tmp_path / "focused-v10",
        }
    )
    result = preflight_curriculum(focused_v10)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {
        "korean-everyday",
        "korean-greeting",
        "replay",
        "uncertainty-evidence",
        "uncertainty-live",
    }
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert result["source_overlap"] == 0

    prepare_curriculum(focused_v10)
    rows = [
        cast(dict[str, object], json.loads(line))
        for line in (focused_v10.output_dir / "train.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    generated = {
        str(row["id"]): cast(list[dict[str, str]], row["messages"])
        for row in rows
        if str(row["id"]).startswith("curriculum-train-")
    }
    greeting_answers = [
        messages[-1]["content"]
        for identifier, messages in generated.items()
        if "korean-greeting" in identifier
    ]
    assert greeting_answers
    assert all(answer and not answer.strip().isdigit() for answer in greeting_answers)

    live_missing = [
        messages[-1]["content"]
        for identifier, messages in generated.items()
        if "uncertainty-live" in identifier and int(identifier.rsplit("-", 1)[1]) % 8 < 6
    ]
    live_provided = [
        messages[-1]["content"]
        for identifier, messages in generated.items()
        if "uncertainty-live" in identifier and int(identifier.rsplit("-", 1)[1]) % 8 >= 6
    ]
    assert all("수 없" in answer for answer in live_missing)
    assert all("수 없" not in answer for answer in live_provided)
    assert preflight_curriculum(focused_v9) == previous


def test_focused_v11은_일상_대화와_안전을_같이_보정하고_v10을_보존한다(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path)
    focused_v10 = config.model_copy(update={"generator_profile": "focused-v10"})
    previous = preflight_curriculum(focused_v10)
    focused_v11 = config.model_copy(
        update={
            "name": "curriculum-focused-v11-test",
            "generator_profile": "focused-v11",
            "output_dir": tmp_path / "focused-v11",
        }
    )
    result = preflight_curriculum(focused_v11)
    mass = cast(dict[str, object], result["target_token_mass"])
    assert set(mass) == {
        "benign-safety",
        "harmful-pii-secret",
        "korean-everyday",
        "korean-greeting",
        "replay",
        "uncertainty-evidence",
        "uncertainty-live",
    }
    assert result["all_user_prompt_overlap"] == {"train_heldout": 0, "suite": 0}
    assert result["source_overlap"] == 0
    assert preflight_curriculum(focused_v10) == previous


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
