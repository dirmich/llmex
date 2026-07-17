# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import pytest
import yaml
from tokenizers.trainers import BpeTrainer
from typer.testing import CliRunner

from llmex.chat.data import ChatRow, final_user_prompt_sha256
from llmex.chat.mixer import preflight_mix, prepare_mix, status_mix, validate_mix
from llmex.chat.runtime import SFTTrainer, _datasets, evaluate_chat, preflight_sft
from llmex.cli import app
from llmex.config import ModelConfig, OptimizerConfig, SFTConfig, SFTMixConfig
from llmex.errors import ConflictError, IntegrityError, LlmexError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.tokenizer.core import SPECIAL_TOKENS, build_tokenizer
from llmex.train.checkpoint import load_checkpoint


def _source(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _row(
    identifier: str,
    split: str,
    prompt: str,
    answer: str,
    license_name: str,
    source: str,
    *,
    source_sha256: bool = True,
) -> dict[str, object]:
    messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}]
    provenance = {
        "dataset": "teacher" if license_name.startswith("LicenseRef") else "public",
        "source": "synthetic",
        "license": license_name,
        "collected_at": "2026-07-17",
        "source_id": source,
    }
    if source_sha256:
        provenance["source_sha256"] = _source(source)
    basis = {"id": identifier, "messages": messages, "provenance": provenance, "split": split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _tokenizer(path: Path) -> int:
    path.mkdir()
    tokenizer = build_tokenizer()
    tokenizer.train_from_iterator(
        [
            "<|user|>\n고유 질문과 공유 질문",
            "<|assistant|>\n간결하고 안전한 답변",
            "계절별 하천 관찰 자료를 비교합니다",
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
    return tokenizer.get_vocab_size()


def _fixture(tmp_path: Path) -> tuple[SFTMixConfig, int]:
    public_train = tmp_path / "public-train.jsonl"
    public_heldout = tmp_path / "public-heldout.jsonl"
    teacher_train = tmp_path / "teacher-train.jsonl"
    teacher_heldout = tmp_path / "teacher-heldout.jsonl"
    public = "Apache-2.0"
    internal = "LicenseRef-LLMEX-Internal-Distillation"
    _write(
        public_train,
        [
            _row("pt-1", "train", "고유 공개 질문", "공개 답변", public, "source-a"),
            _row("pt-2", "train", "공유 질문", "누출 후보", public, "source-b"),
            _row("pt-3", "train", "다른 질문", "source 누출 후보", public, "source-c"),
            _row("pt-4", "train", "중복 질문", "첫 답변", public, "source-d"),
            _row("pt-5", "train", "중복 질문", "둘째 답변", public, "source-d"),
            _row("pt-6", "train", "매우 긴 질문 " * 100, "긴 답변", public, "source-e"),
            _row(
                "pt-7",
                "train",
                "fallback train 질문",
                "fallback train 답변",
                public,
                "source-fallback",
                source_sha256=False,
            ),
            _row(
                "pt-8",
                "train",
                "길이 탈락 heldout와 같은 source의 train 질문",
                "source 예약으로 제외할 답변",
                public,
                "source-long-heldout",
            ),
        ],
    )
    _write(
        public_heldout,
        [
            _row("ph-1", "heldout", "공유   질문", "검증 답변", public, "source-c"),
            _row(
                "ph-2",
                "heldout",
                "fallback heldout 질문",
                "fallback heldout 답변",
                public,
                "source-fallback",
                source_sha256=False,
            ),
            _row(
                "ph-3",
                "heldout",
                "매우 긴 heldout 질문 " * 100,
                "길이 탈락 답변",
                public,
                "source-long-heldout",
            ),
        ],
    )
    _write(
        teacher_train,
        [
            _row("tt-1", "train", "teacher 고유 질문", "teacher 답변", internal, "source-f"),
            _row("tt-2", "train", "공유 질문", "teacher 누출 후보", internal, "source-g"),
        ],
    )
    _write(
        teacher_heldout,
        [_row("th-1", "heldout", "공유\n질문", "teacher 검증", internal, "source-c")],
    )
    tokenizer_dir = tmp_path / "tokenizer"
    vocab = _tokenizer(tokenizer_dir)
    teacher_manifest = tmp_path / "teacher-manifest.json"
    teacher_manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "config_fingerprint": "1" * 64,
                "inventory_fingerprint": "2" * 64,
                "accepted_spool_set_fingerprint": "3" * 64,
                "teacher_output_license": internal,
                "redistribution_allowed": False,
                "release_gate": "blocked",
                "counts": {"train": 2, "heldout": 1},
                "sha256": {
                    "train": sha256_file(teacher_train),
                    "heldout": sha256_file(teacher_heldout),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return (
        SFTMixConfig(
            name="synthetic-mix",
            tokenizer_dir=tokenizer_dir,
            public_train_data=public_train,
            public_heldout_data=public_heldout,
            teacher_train_data=teacher_train,
            teacher_heldout_data=teacher_heldout,
            teacher_manifest=teacher_manifest,
            expected_teacher_manifest_sha256=sha256_file(teacher_manifest),
            output_dir=tmp_path / "mixed",
            allowed_licenses=[public, internal],
            max_seq_len=128,
            generation_reserve_tokens=16,
        ),
        vocab,
    )


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _refresh_teacher_binding(config: SFTMixConfig) -> SFTMixConfig:
    teacher = json.loads(config.teacher_manifest.read_text(encoding="utf-8"))
    teacher["counts"] = {
        "train": len(_rows(config.teacher_train_data)),
        "heldout": len(_rows(config.teacher_heldout_data)),
    }
    teacher["sha256"] = {
        "train": sha256_file(config.teacher_train_data),
        "heldout": sha256_file(config.teacher_heldout_data),
    }
    config.teacher_manifest.write_text(json.dumps(teacher, sort_keys=True), encoding="utf-8")
    return config.model_copy(
        update={"expected_teacher_manifest_sha256": sha256_file(config.teacher_manifest)}
    )


def test_mix는_assistant_민감_출력만_선필터하고_집계만_공개한다(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    public = "Apache-2.0"
    internal = "LicenseRef-LLMEX-Internal-Distillation"
    prompt_only_value = "문의 본문 user@example.com, 010-1234-5678, 900101-1234567"
    leaked_email = "private.person@example.com입니다"
    leaked_phone = "010-9876-5432입니다"
    leaked_id = "900101-1234567입니다"
    leaked_credential = "api_key=TopSecretValue123입니다"
    leaked_extra = "계좌 123-456-123456"

    public_train = _rows(config.public_train_data)
    prompt_only = _row(
        "pt-safe-prompt",
        "train",
        prompt_only_value,
        "민감 문자열을 반복하지 않는 안전한 답변",
        public,
        "source-prompt-only",
    )
    multi_turn = _row(
        "pt-email",
        "train",
        "첫 질문",
        "최종 안전 답변",
        public,
        "source-email",
    )
    multi_turn["messages"] = [
        {"role": "system", "content": "system@example.com을 반복하지 마세요"},
        {"role": "user", "content": "첫 질문"},
        {"role": "assistant", "content": f"이전 답변 {leaked_email}"},
        {"role": "user", "content": "두 번째 질문"},
        {"role": "assistant", "content": "최종 안전 답변"},
    ]
    multi_basis = {key: multi_turn[key] for key in ("id", "messages", "provenance", "split")}
    multi_turn["sha256"] = fingerprint(multi_basis)
    public_train.extend(
        [
            prompt_only,
            multi_turn,
            _row(
                "pt-extra",
                "train",
                "추가 규칙 질문",
                leaked_extra,
                public,
                "source-extra",
            ),
            _row(
                "pt-filter-order",
                "train",
                "아주 긴 민감 질문 " * 100,
                leaked_credential,
                public,
                "source-filter-order",
            ),
            _row(
                "pt-safe-reserved",
                "train",
                "민감 heldout와 source만 같은 안전한 질문",
                "안전한 train 답변",
                public,
                "source-sensitive-heldout",
            ),
            _row(
                "pt-safe-length-reserved",
                "train",
                "길이 제한 heldout와 source만 같은 안전한 질문",
                "안전한 길이 제한 train 답변",
                public,
                "source-length-heldout",
            ),
            _row(
                "pt-secret-boundary",
                "train",
                "secret 경계 오탐 질문",
                "notsecret=abcdefgh 및 xapi_key=abcdefgh는 일반 문자열입니다",
                public,
                "source-secret-boundary",
            ),
        ]
    )
    _write(config.public_train_data, public_train)
    public_heldout = _rows(config.public_heldout_data)
    public_heldout.append(
        _row(
            "ph-phone",
            "heldout",
            "전화 출력 질문",
            leaked_phone,
            public,
            "source-sensitive-heldout",
        )
    )
    public_heldout.append(
        _row(
            "ph-scan-limit",
            "heldout",
            "assistant 검색 길이 제한 질문",
            "가" * 65_537,
            public,
            "source-length-heldout",
        )
    )
    _write(config.public_heldout_data, public_heldout)

    teacher_train = _rows(config.teacher_train_data)
    teacher_train.append(
        _row(
            "tt-id",
            "train",
            "식별자 출력 질문",
            leaked_id,
            internal,
            "source-id",
        )
    )
    _write(config.teacher_train_data, teacher_train)
    teacher_heldout = _rows(config.teacher_heldout_data)
    teacher_heldout.append(
        _row(
            "th-secret",
            "heldout",
            "비밀 출력 질문",
            leaked_credential,
            internal,
            "source-secret",
        )
    )
    _write(config.teacher_heldout_data, teacher_heldout)
    raw_config = _refresh_teacher_binding(config).model_dump(mode="json")
    raw_config["extra_sensitive_output_patterns"] = [
        {"name": "bank-account", "pattern": r"\b\d\d\d-\d\d\d-\d\d\d\d\d\d\b"}
    ]
    config = SFTMixConfig.model_validate(raw_config)

    preflight = preflight_mix(config)
    counts = preflight["sensitive_output_filter"]
    assert counts == {
        "total": 7,
        "by_source": {"public": 5, "teacher": 2},
        "by_split": {"heldout": 3, "train": 4},
        "by_rule": {
            "api-key-secret-assignment": 2,
            "assistant-content-length-limit": 1,
            "bank-account": 1,
            "email-address": 1,
            "korean-mobile-phone": 1,
            "korean-resident-registration-number": 1,
        },
    }
    selection = cast(dict[str, object], preflight["selection"])
    excluded = cast(dict[str, int], selection["excluded"])
    assert excluded["sensitive_assistant_output"] == 7
    assert excluded["prompt_too_long"] == 2

    result = prepare_mix(config)
    assert result["reused"] is False
    manifest_text = (config.output_dir / "manifest.json").read_text(encoding="utf-8")
    public_result = (config.output_dir / "train.jsonl").read_text(encoding="utf-8")
    assert prompt_only_value in public_result
    assert "민감 heldout와 source만 같은 안전한 질문" in public_result
    assert "길이 제한 heldout와 source만 같은 안전한 질문" in public_result
    assert "notsecret=abcdefgh 및 xapi_key=abcdefgh" in public_result
    for leaked in (leaked_email, leaked_phone, leaked_id, leaked_credential, leaked_extra):
        assert leaked not in manifest_text
        assert leaked not in json.dumps(preflight, ensure_ascii=False)

    yaml_path = tmp_path / "sensitive-mix.yaml"
    yaml_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    cli = CliRunner().invoke(app, ["sft", "preflight-mix", "--config", str(yaml_path)])
    assert cli.exit_code == 0
    assert '"total": 7' in cli.stdout
    for leaked in (leaked_email, leaked_phone, leaked_id, leaked_credential, leaked_extra):
        assert leaked not in cli.stdout


@pytest.mark.parametrize(
    "rules",
    [
        [{"name": "invalid-regex", "pattern": "["}],
        [{"name": "catastrophic-backtracking", "pattern": "(a+)+$"}],
        [{"name": "too-long", "pattern": "a" * 257}],
        [
            {"name": "same-name", "pattern": "foo"},
            {"name": "same-name", "pattern": "bar"},
        ],
        [
            {"name": "first-rule", "pattern": "foo"},
            {"name": "second-rule", "pattern": "foo"},
        ],
        [{"name": "email-address", "pattern": "foo"}],
        [{"name": "assistant-content-length-limit", "pattern": "foo"}],
        [
            {
                "name": "builtin-copy",
                "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            }
        ],
        [{"name": "valid-name", "pattern": "foo", "unknown": True}],
    ],
)
def test_mix_추가_민감_정규식은_strict하고_중복될_수_없다(
    tmp_path: Path, rules: list[dict[str, object]]
) -> None:
    config, _ = _fixture(tmp_path)
    raw = config.model_dump(mode="json")
    raw["extra_sensitive_output_patterns"] = rules
    with pytest.raises(ValueError):
        SFTMixConfig.model_validate(raw)


def test_mix는_split_누출_중복_길이를_제외하고_release를_계승한다(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    preflight = preflight_mix(config)
    assert preflight["release_gate"] == "blocked"
    result = prepare_mix(config)
    assert result["reused"] is False
    assert prepare_mix(config)["reused"] is True
    assert status_mix(config)["status"] == "ready"
    assert validate_mix(config)["status"] == "ok"
    manifest = json.loads((config.output_dir / "manifest.json").read_text())
    excluded = manifest["selection"]["excluded"]
    assert excluded["heldout_prompt_from_train"] == 2
    assert excluded["heldout_source_from_train"] == 3
    assert excluded["duplicate_source_prompt"] == 1
    assert excluded["heldout_prompt_duplicate"] == 1
    assert excluded["prompt_too_long"] + excluded.get("sequence_too_long", 0) == 2
    assert manifest["redistribution_allowed"] is False
    assert manifest["release_gate"] == "blocked"
    assert manifest["distribution"]["licenses"]["LicenseRef-LLMEX-Internal-Distillation"]["count"]

    train = [
        ChatRow.model_validate(json.loads(line))
        for line in (config.output_dir / "train.jsonl").read_text().splitlines()
    ]
    heldout = [
        ChatRow.model_validate(json.loads(line))
        for line in (config.output_dir / "heldout.jsonl").read_text().splitlines()
    ]
    assert not (
        {final_user_prompt_sha256(row.messages) for row in train}
        & {final_user_prompt_sha256(row.messages) for row in heldout}
    )
    assert not (
        {row.provenance.source_sha256 for row in train}
        & {row.provenance.source_sha256 for row in heldout}
    )


def test_mix_manifest_tamper와_cli를_실패_폐쇄한다(tmp_path: Path) -> None:
    config, _ = _fixture(tmp_path)
    yaml_path = tmp_path / "mix.yaml"
    yaml_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    runner = CliRunner()
    for command in ("preflight-mix", "prepare-mix", "status-mix", "validate-mix"):
        assert runner.invoke(app, ["sft", command, "--config", str(yaml_path)]).exit_code == 0
    output_manifest = config.output_dir / "manifest.json"
    original_output = output_manifest.read_text()
    damaged_output = json.loads(original_output)
    damaged_output["fingerprint"] = "0" * 64
    output_manifest.write_text(json.dumps(damaged_output), encoding="utf-8")
    with pytest.raises(IntegrityError, match="현재 입력/config"):
        validate_mix(config)
    output_manifest.write_text(original_output, encoding="utf-8")
    teacher_rows = [json.loads(line) for line in config.teacher_train_data.read_text().splitlines()]
    teacher_rows[0]["messages"][-1]["content"] = "공모된 변조 답변"
    basis = {key: teacher_rows[0][key] for key in ("id", "messages", "provenance", "split")}
    teacher_rows[0]["sha256"] = fingerprint(basis)
    _write(config.teacher_train_data, teacher_rows)
    teacher = json.loads(config.teacher_manifest.read_text())
    teacher["sha256"]["train"] = sha256_file(config.teacher_train_data)
    config.teacher_manifest.write_text(json.dumps(teacher), encoding="utf-8")
    with pytest.raises(IntegrityError, match="teacher export manifest"):
        preflight_mix(config)

    teacher["inventory_fingerprint"] = "Z" * 64
    config.teacher_manifest.write_text(json.dumps(teacher), encoding="utf-8")
    nonhex = config.model_copy(
        update={"expected_teacher_manifest_sha256": sha256_file(config.teacher_manifest)}
    )
    with pytest.raises(IntegrityError, match="teacher export manifest"):
        preflight_mix(nonhex)


def test_prepare_mix는_동시_실행과_부분_publish를_실패_폐쇄한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _ = _fixture(tmp_path)
    import llmex.chat.mixer as mixer

    entered = threading.Event()
    release = threading.Event()
    original = mixer._material

    def blocked_material(
        value: SFTMixConfig,
    ) -> tuple[bytes, bytes, dict[str, object]]:
        entered.set()
        assert release.wait(timeout=5)
        return original(value)

    monkeypatch.setattr(mixer, "_material", blocked_material)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(prepare_mix, config)
        assert entered.wait(timeout=5)
        lock_name, staging_prefix = mixer._publish_names(config)
        assert (config.output_dir.parent / lock_name).is_file()
        assert not config.output_dir.exists()
        second = pool.submit(prepare_mix, config)
        try:
            second_result: dict[str, object] | None = second.result(timeout=5)
            second_error: BaseException | None = None
        except BaseException as exc:
            second_result = None
            second_error = exc
        release.set()
        first_result = first.result(timeout=5)

    assert first_result["reused"] is False
    assert second_result is None
    assert isinstance(second_error, ConflictError)
    assert isinstance(second_error, LlmexError)
    assert validate_mix(config)["status"] == "ok"
    assert not list(config.output_dir.parent.glob(f"{staging_prefix}*"))
    assert not (config.output_dir / ".sft-mix.lock").exists()

    for name in ("train.jsonl", "heldout.jsonl", "manifest.json"):
        (config.output_dir / name).unlink()
    config.output_dir.rmdir()
    original_replace = mixer.os.replace

    def fail_directory_publish(source: str | Path, destination: str | Path) -> None:
        if Path(destination) == config.output_dir:
            raise FileNotFoundError("의도한 directory publish 중단")
        original_replace(source, destination)

    monkeypatch.setattr(mixer.os, "replace", fail_directory_publish)
    with pytest.raises(IntegrityError, match="publish"):
        prepare_mix(config)
    assert not config.output_dir.exists()
    assert not list(config.output_dir.parent.glob(f"{staging_prefix}*"))

    monkeypatch.setattr(mixer.os, "replace", original_replace)
    stale = config.output_dir.parent / f"{staging_prefix}stale"
    stale.mkdir()
    with pytest.raises(ConflictError, match="staging"):
        prepare_mix(config)
    stale.rmdir()
    assert prepare_mix(config)["reused"] is False
    assert prepare_mix(config)["reused"] is True


def test_runtime은_prompt와_source_cross_split을_차단한다(tmp_path: Path) -> None:
    config, vocab = _fixture(tmp_path)
    prepare_mix(config)
    sft = SFTConfig(
        name="mix-runtime",
        model=ModelConfig(
            name="tiny",
            vocab_size=vocab,
            max_seq_len=128,
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
        source_manifest=config.output_dir / "manifest.json",
        expected_source_manifest_sha256=sha256_file(config.output_dir / "manifest.json"),
        run_dir=tmp_path / "run",
        allowed_licenses=config.allowed_licenses,
        device="cpu",
        sequence_length=128,
        micro_batch_size=1,
        max_steps=1,
        validation_interval=1,
        validation_batches=1,
        checkpoint_interval=1,
        optimizer=OptimizerConfig(learning_rate=0.01, min_learning_rate=0.001),
        max_new_tokens=2,
    )
    missing_pin = sft.model_dump(mode="json")
    missing_pin.pop("expected_source_manifest_sha256")
    with pytest.raises(ValueError, match="expected_source_manifest_sha256"):
        SFTConfig.model_validate(missing_pin)
    trainer = SFTTrainer(sft)
    assert preflight_sft(sft)["release_gate"] == "blocked"
    with pytest.raises(IntegrityError, match="sequence 길이"):
        SFTTrainer(sft.model_copy(update={"sequence_length": 4}))
    tampered_manifest = tmp_path / "tokenizer-tampered-manifest.json"
    tampered = json.loads((config.output_dir / "manifest.json").read_text())
    tampered["tokenizer_manifest_sha256"] = "0" * 64
    tampered_manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(IntegrityError, match="source manifest"):
        preflight_sft(sft.model_copy(update={"source_manifest": tampered_manifest}))

    forged_manifest = tmp_path / "forged-lower-length-manifest.json"
    forged = json.loads((config.output_dir / "manifest.json").read_text())
    forged["length_gate"]["max_seq_len"] = 4
    forged["fingerprint"] = fingerprint(
        {key: value for key, value in forged.items() if key != "fingerprint"}
    )
    forged_manifest.write_text(
        json.dumps(forged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(IntegrityError, match="source manifest"):
        SFTTrainer(sft.model_copy(update={"source_manifest": forged_manifest}))
    stale_fingerprint = dict(forged)
    stale_fingerprint["length_gate"] = dict(forged["length_gate"])
    stale_fingerprint["length_gate"]["max_seq_len"] = 5
    forged_manifest.write_text(
        json.dumps(stale_fingerprint, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(IntegrityError, match="source manifest"):
        SFTTrainer(
            sft.model_copy(
                update={
                    "source_manifest": forged_manifest,
                    "expected_source_manifest_sha256": sha256_file(forged_manifest),
                }
            )
        )
    forged_manifest.write_text(
        json.dumps(forged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    forged_config = sft.model_copy(
        update={
            "source_manifest": forged_manifest,
            "expected_source_manifest_sha256": sha256_file(forged_manifest),
            "sequence_length": 4,
        }
    )
    with pytest.raises(IntegrityError, match="sequence 길이"):
        SFTTrainer(forged_config)
    result = trainer.run()
    checkpoint = Path(str(result["checkpoint"]))
    payload = load_checkpoint(checkpoint, trainer.fingerprints, supported_schema_versions={2})
    assert payload["redistribution_allowed"] is False
    assert payload["release_gate"] == "blocked"
    data_manifest = json.loads((sft.run_dir / "data-manifest.json").read_text())
    assert data_manifest["release_gate"] == "blocked"
    evaluation = evaluate_chat(sft, checkpoint)
    assert evaluation["redistribution_allowed"] is False
    assert evaluation["release_gate"] == "blocked"

    heldout_rows = (config.output_dir / "heldout.jsonl").read_text().splitlines()
    leaked = next(
        json.loads(line)
        for line in heldout_rows
        if "source_sha256" in json.loads(line)["provenance"]
    )
    leaked["split"] = "train"
    basis = {key: leaked[key] for key in ("id", "messages", "provenance", "split")}
    leaked["sha256"] = fingerprint(basis)
    _write(tmp_path / "leaked-train.jsonl", [leaked])
    with pytest.raises(IntegrityError, match="prompt 누출"):
        _datasets(
            sft.model_copy(
                update={"train_data": tmp_path / "leaked-train.jsonl", "source_manifest": None}
            )
        )

    safe_train = json.loads((config.output_dir / "train.jsonl").read_text().splitlines()[0])
    safe_train["provenance"]["source_sha256"] = leaked["provenance"]["source_sha256"]
    basis = {key: safe_train[key] for key in ("id", "messages", "provenance", "split")}
    safe_train["sha256"] = fingerprint(basis)
    _write(tmp_path / "source-leaked-train.jsonl", [safe_train])
    with pytest.raises(IntegrityError, match="source identity 누출"):
        _datasets(
            sft.model_copy(
                update={
                    "train_data": tmp_path / "source-leaked-train.jsonl",
                    "source_manifest": None,
                }
            )
        )

    fallback_train = json.loads((config.output_dir / "train.jsonl").read_text().splitlines()[0])
    fallback_heldout = json.loads(heldout_rows[0])
    for row in (fallback_train, fallback_heldout):
        row["provenance"].pop("source_sha256", None)
        row["provenance"].update(
            {"dataset": "same-dataset", "source": "same-source", "source_id": "same-id"}
        )
        basis = {key: row[key] for key in ("id", "messages", "provenance", "split")}
        row["sha256"] = fingerprint(basis)
    _write(tmp_path / "fallback-train.jsonl", [fallback_train])
    _write(tmp_path / "fallback-heldout.jsonl", [fallback_heldout])
    with pytest.raises(IntegrityError, match="source identity 누출"):
        _datasets(
            sft.model_copy(
                update={
                    "train_data": tmp_path / "fallback-train.jsonl",
                    "heldout_data": tmp_path / "fallback-heldout.jsonl",
                    "source_manifest": None,
                }
            )
        )
