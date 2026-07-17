# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
import json
import random
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import torch
import yaml
from tokenizers.trainers import BpeTrainer
from typer.testing import CliRunner

from llmex.chat.data import ChatDataset, Message, load_chat_jsonl
from llmex.chat.runtime import SFTTrainer, evaluate_chat, generate_chat, preflight_sft
from llmex.chat.template import tokenize_chat
from llmex.cli import app
from llmex.config import ModelConfig, OptimizerConfig, SFTConfig
from llmex.errors import ConfigError, ConflictError, InputError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.tokenizer.core import SPECIAL_TOKENS, build_tokenizer
from llmex.train.checkpoint import load_checkpoint, save_checkpoint
from llmex.train.data import DeterministicBatchSampler


def _tokenizer(path: Path) -> int:
    path.mkdir()
    tokenizer = build_tokenizer()
    tokenizer.train_from_iterator(
        ["<|system|>\n도움말", "<|user|>\n안녕", "<|assistant|>\n반가워요"],
        trainer=BpeTrainer(
            vocab_size=300, special_tokens=list(SPECIAL_TOKENS), show_progress=False
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


def _row(
    identifier: str, split: str, user: str, assistant: str, license_name: str = "CC-BY-4.0"
) -> dict[str, object]:
    messages = [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
    provenance = {
        "dataset": "synthetic-g003",
        "source": "local-test",
        "license": license_name,
        "collected_at": "2026-07-11",
        "source_id": identifier,
    }
    basis = {"id": identifier, "messages": messages, "provenance": provenance, "split": split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _config(tmp_path: Path, *, max_steps: int = 1) -> SFTConfig:
    tmp_path.mkdir(parents=True, exist_ok=True)
    vocab = (
        _tokenizer(tmp_path / "tokenizer")
        if not (tmp_path / "tokenizer").exists()
        else json.loads((tmp_path / "tokenizer/tokenizer-manifest.json").read_text())[
            "vocab_size_actual"
        ]
    )
    train, heldout = tmp_path / "train.jsonl", tmp_path / "heldout.jsonl"
    if not train.exists():
        _write(
            train,
            [
                _row("train-1", "train", "안녕하세요", "반갑습니다"),
                _row("train-2", "train", "이름은?", "LLMEX입니다"),
            ],
        )
        _write(heldout, [_row("heldout-1", "heldout", "인사해 주세요", "안녕하세요")])
    return SFTConfig(
        name="g003-test",
        seed=7,
        model=ModelConfig(
            name="chat-tiny",
            vocab_size=vocab,
            max_seq_len=72,
            n_layers=1,
            d_model=16,
            n_heads=2,
            n_kv_heads=1,
            ffn_hidden_size=32,
            dropout=0.0,
        ),
        tokenizer_dir=tmp_path / "tokenizer",
        train_data=train,
        heldout_data=heldout,
        run_dir=tmp_path / "run",
        allowed_licenses=["CC-BY-4.0"],
        device="cpu",
        sequence_length=56,
        micro_batch_size=1,
        max_steps=max_steps,
        validation_interval=1,
        validation_batches=1,
        checkpoint_interval=1,
        log_interval=1,
        optimizer=OptimizerConfig(learning_rate=0.02, min_learning_rate=0.002),
    )


def test_jsonl_provenance_license_hash_and_split_validation(tmp_path: Path) -> None:
    path = tmp_path / "chat.jsonl"
    _write(path, [_row("one", "train", "질문", "답변")])
    loaded = load_chat_jsonl(path, split="train", allowed_licenses={"CC-BY-4.0"})
    assert loaded.file_sha256 == sha256_file(path) and loaded.licenses == ("CC-BY-4.0",)
    with pytest.raises(IntegrityError, match="라이선스"):
        load_chat_jsonl(path, split="train", allowed_licenses={"MIT"})
    damaged = _row("bad", "train", "질문", "답변")
    damaged["sha256"] = "0" * 64
    _write(path, [damaged])
    with pytest.raises(IntegrityError, match="schema"):
        load_chat_jsonl(path, split="train", allowed_licenses={"CC-BY-4.0"})


def test_chat_template_masks_everything_except_assistant(tmp_path: Path) -> None:
    config = _config(tmp_path)
    from llmex.tokenizer.core import load_tokenizer

    tokenizer = load_tokenizer(config.tokenizer_dir)
    encoded = tokenize_chat(
        tokenizer,
        (
            Message(role="system", content="안전하게 답하세요"),
            Message(role="user", content="안녕"),
            Message(role="assistant", content="반가워요"),
            Message(role="user", content="이름은?"),
            Message(role="assistant", content="LLMEX입니다"),
        ),
        max_length=256,
    )
    expected_labels = [
        -100,
        *([-100] * len(tokenizer.encode("<|system|>\n").ids)),
        *([-100] * len(tokenizer.encode("안전하게 답하세요\n").ids)),
        *([-100] * len(tokenizer.encode("<|user|>\n").ids)),
        *([-100] * len(tokenizer.encode("안녕\n").ids)),
        *([-100] * len(tokenizer.encode("<|assistant|>\n").ids)),
        *tokenizer.encode("반가워요\n").ids,
        2,
        *([-100] * len(tokenizer.encode("<|user|>\n").ids)),
        *([-100] * len(tokenizer.encode("이름은?\n").ids)),
        *([-100] * len(tokenizer.encode("<|assistant|>\n").ids)),
        *tokenizer.encode("LLMEX입니다\n").ids,
        2,
    ]
    assert encoded.labels == tuple(expected_labels)


def test_sft_preflight_baseline은_결정적이고_상태와_파일을_남기지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    random.seed(991)
    np.random.seed(992)
    torch.manual_seed(993)
    python_before = random.getstate()
    numpy_before = np.random.get_state()
    numpy_expected = float(np.random.random())
    np.random.set_state(numpy_before)
    torch_before = torch.get_rng_state().clone()

    first = preflight_sft(config, measure_baseline=True)
    second = preflight_sft(config, measure_baseline=True)

    assert first == second
    assert first["schema_version"] == 1
    assert first["status"] == "ok"
    assert first["device"] == "cpu"
    assert first["precision"] == "fp32"
    parameter_count = first["unique_parameter_count"]
    assert isinstance(parameter_count, int) and parameter_count > 0
    train = cast(dict[str, object], first["train"])
    heldout = cast(dict[str, object], first["heldout"])
    assert train["rows"] == 2
    assert heldout["rows"] == 1
    assert first["expected_effective_batch_size"] == 1
    assert first["baseline_measured"] is True
    baseline = cast(dict[str, float | int], first["baseline"])
    assert baseline["target_tokens"] > 0
    assert baseline["loss"] > 0
    assert baseline["perplexity"] > 1
    assert not config.run_dir.exists()
    assert random.getstate() == python_before
    assert float(np.random.random()) == numpy_expected
    assert torch.equal(torch.get_rng_state(), torch_before)

    trainer = SFTTrainer(config)
    sampler_before = trainer.validation_sampler.state_dict()
    batches_before = trainer.validation_batches_seen
    trainer.validation_metrics(mutate_state=False)
    assert trainer.validation_sampler.state_dict() == sampler_before
    assert trainer.validation_batches_seen == batches_before

    original_next_batch = trainer._next_batch

    def empty_target_batch(
        dataset: ChatDataset, sampler: DeterministicBatchSampler
    ) -> tuple[torch.Tensor, torch.Tensor]:
        inputs, labels = original_next_batch(dataset, sampler)
        return inputs, torch.full_like(labels, -100)

    monkeypatch.setattr(trainer, "_next_batch", empty_target_batch)
    with pytest.raises(IntegrityError, match="assistant 검증 token"):
        trainer.validation_metrics(mutate_state=False)


def test_sft_preflight는_base_data_device_precision_length를_차단한다(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    with pytest.raises(ConfigError, match="fp16"):
        preflight_sft(config.model_copy(update={"precision": "fp16"}))
    if not torch.cuda.is_available():
        with pytest.raises(ConfigError, match="CUDA"):
            preflight_sft(config.model_copy(update={"device": "cuda"}))
    with pytest.raises(IntegrityError, match="sequence 길이"):
        preflight_sft(config.model_copy(update={"sequence_length": 4}))

    invalid_base = tmp_path / "invalid-base.pt"
    torch.save(
        {
            "schema_version": 1,
            "model": {"invalid.weight": torch.ones(1)},
            "fingerprints": {},
            "step": 0,
        },
        invalid_base,
    )
    with pytest.raises(IntegrityError, match="base checkpoint"):
        preflight_sft(config.model_copy(update={"base_checkpoint": invalid_base}))

    damaged = json.loads(config.train_data.read_text().splitlines()[0])
    damaged["sha256"] = "0" * 64
    _write(config.train_data, [damaged])
    with pytest.raises(IntegrityError, match="schema"):
        preflight_sft(config)


def test_sft_preflight는_deterministic_warn_only를_성공과_실패에서_복원한다(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    previous_enabled = torch.are_deterministic_algorithms_enabled()
    previous_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
        assert preflight_sft(config)["status"] == "ok"
        assert torch.are_deterministic_algorithms_enabled() is True
        assert torch.is_deterministic_algorithms_warn_only_enabled() is True

        missing = config.model_copy(update={"train_data": tmp_path / "missing.jsonl"})
        with pytest.raises(InputError, match="chat JSONL"):
            preflight_sft(missing)
        assert torch.are_deterministic_algorithms_enabled() is True
        assert torch.is_deterministic_algorithms_warn_only_enabled() is True
    finally:
        torch.use_deterministic_algorithms(previous_enabled, warn_only=previous_warn_only)


def test_sft_preflight_cli는_JSON과_오류코드를_출력한다(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config_path = tmp_path / "sft-preflight.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    runner = CliRunner()
    success = runner.invoke(
        app,
        ["sft", "preflight", "--config", str(config_path), "--measure-baseline"],
    )
    assert success.exit_code == 0
    payload = json.loads(success.stdout)
    assert payload["status"] == "ok"
    assert payload["baseline_measured"] is True
    assert not config.run_dir.exists()

    missing = config.model_copy(update={"train_data": tmp_path / "missing.jsonl"})
    config_path.write_text(
        yaml.safe_dump(missing.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    failure = runner.invoke(app, ["sft", "preflight", "--config", str(config_path)])
    assert failure.exit_code == 3


def test_sft_atomic_resume_eval_generation_and_cli(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = SFTTrainer(config)
    result = first.run()
    checkpoint = Path(str(result["checkpoint"]))
    assert checkpoint.is_file() and (config.run_dir / "data-manifest.json").is_file()
    sft_payload = load_checkpoint(checkpoint, first.fingerprints, supported_schema_versions={2})
    assert sft_payload["micro_step"] == 0
    assert sft_payload["precision"] == "fp32"
    assert sft_payload["validation_batches_seen"] == 1
    assert sft_payload["sampler"] == first.sampler.state_dict()
    assert sft_payload["validation_sampler"] == first.validation_sampler.state_dict()
    assert (config.run_dir / "checkpoints/best.pt").is_file()
    best_payload = load_checkpoint(
        config.run_dir / "checkpoints/best.pt",
        first.fingerprints,
        supported_schema_versions={2},
    )
    assert best_payload["step"] == 1
    assert best_payload["best_validation_loss"] == result["best_validation_loss"]
    legacy_payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    legacy_payload.pop("redistribution_allowed")
    legacy_payload.pop("release_gate")
    legacy_checkpoint = save_checkpoint(tmp_path / "legacy-checkpoints", legacy_payload, step=1)
    legacy = SFTTrainer(config)
    legacy.resume(legacy_checkpoint)
    assert legacy.step == 1
    resumed_config = config.model_copy(update={"max_steps": 2})
    resumed = SFTTrainer(resumed_config)
    resumed.resume(config.run_dir / "checkpoints/latest.pt")
    assert resumed.step == 1
    assert resumed.sampler.state_dict() == first.sampler.state_dict()
    assert resumed.validation_sampler.state_dict() == first.validation_sampler.state_dict()
    resumed.run()
    generated = generate_chat(resumed_config, config.run_dir / "checkpoints/latest.pt", "안녕")
    assert isinstance(generated["response"], str)
    report = evaluate_chat(resumed_config, config.run_dir / "checkpoints/latest.pt")
    assert set(report["gates"]) == {"safety", "repetition", "eos"}  # type: ignore[arg-type]
    assert (config.run_dir / "heldout-evaluation.json").is_file()

    import yaml

    yaml_path = tmp_path / "sft.yaml"
    yaml_path.write_text(
        yaml.safe_dump(resumed_config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    runner = CliRunner()
    assert (
        runner.invoke(app, ["sft", "train", "--config", str(yaml_path), "--dry-run"]).exit_code == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "sft",
                "generate",
                "--config",
                str(yaml_path),
                "--checkpoint",
                str(config.run_dir / "checkpoints/latest.pt"),
                "--prompt",
                "안녕",
            ],
        ).exit_code
        == 0
    )


def test_base_checkpoint_weights_are_reused(tmp_path: Path) -> None:
    config = _config(tmp_path)
    trainer = SFTTrainer(config)
    for parameter in trainer.model.parameters():
        parameter.data.fill_(0.125)
    base = trainer.save()
    reused = SFTTrainer(
        config.model_copy(update={"base_checkpoint": base, "run_dir": tmp_path / "reused"})
    )
    assert all(
        torch.allclose(parameter, torch.full_like(parameter, 0.125))
        for parameter in reused.model.parameters()
    )

    result = reused.run()
    sft_checkpoint = Path(str(result["checkpoint"]))
    manifest = json.loads((reused.run_dir / "data-manifest.json").read_text())
    assert manifest["base_checkpoint"]["sha256"] == sha256_file(base)
    assert manifest["base_checkpoint"]["training_fingerprints"] == trainer.fingerprints
    base_payload = torch.load(base, map_location="cpu", weights_only=True)
    first_tensor = next(iter(base_payload["model"].values()))
    first_tensor.view(-1)[0] += 1.0
    torch.save(base_payload, base)
    with pytest.raises(IntegrityError, match="fingerprint"):
        SFTTrainer(
            config.model_copy(update={"base_checkpoint": base, "run_dir": tmp_path / "reused"})
        ).resume(sft_checkpoint)


def test_sft_config_training_defaults(tmp_path: Path) -> None:
    explicit = _config(tmp_path)
    values = explicit.model_dump(
        exclude={
            "precision",
            "gradient_accumulation_steps",
            "validation_interval",
            "validation_batches",
        }
    )
    config = SFTConfig.model_validate(values)
    assert config.precision == "auto"
    assert config.gradient_accumulation_steps == 1
    assert config.validation_interval == 10
    assert config.validation_batches == 4


def test_sft_gradient_accumulation_matches_large_batch(tmp_path: Path) -> None:
    accumulated = _config(tmp_path / "accum").model_copy(update={"gradient_accumulation_steps": 2})
    large_batch = _config(tmp_path / "large").model_copy(update={"micro_batch_size": 2})
    accumulated_trainer = SFTTrainer(accumulated)
    large_batch_trainer = SFTTrainer(large_batch)
    accumulated_trainer.run()
    large_batch_trainer.run()
    for accumulated_parameter, large_parameter in zip(
        accumulated_trainer.model.parameters(), large_batch_trainer.model.parameters(), strict=True
    ):
        assert torch.allclose(accumulated_parameter, large_parameter, atol=1e-6, rtol=1e-6)


def test_sft_continuous_and_resume_are_deterministic(tmp_path: Path) -> None:
    continuous = _config(tmp_path / "continuous", max_steps=2)
    continuous_trainer = SFTTrainer(continuous)
    continuous_trainer.run()

    staged = _config(tmp_path / "staged", max_steps=2)
    SFTTrainer(staged).run(stop_after_steps=1)
    resumed_trainer = SFTTrainer(staged)
    resumed_trainer.resume(staged.run_dir / "checkpoints/latest.pt")
    resumed_trainer.run()

    assert resumed_trainer.sampler.state_dict() == continuous_trainer.sampler.state_dict()
    assert (
        resumed_trainer.validation_sampler.state_dict()
        == continuous_trainer.validation_sampler.state_dict()
    )
    for continuous_parameter, resumed_parameter in zip(
        continuous_trainer.model.parameters(), resumed_trainer.model.parameters(), strict=True
    ):
        assert torch.equal(continuous_parameter, resumed_parameter)


def test_sft_fresh_run은_기존_run_dir를_거부하고_resume만_계속_사용한다(
    tmp_path: Path,
) -> None:
    empty = _config(tmp_path / "empty")
    empty.run_dir.mkdir(parents=True)
    with pytest.raises(ConflictError, match="존재하지 않는 별도 경로"):
        SFTTrainer(empty).run()
    assert not list(empty.run_dir.iterdir())

    nonempty = _config(tmp_path / "nonempty")
    nonempty.run_dir.mkdir(parents=True)
    sentinel = nonempty.run_dir / "사용자-파일.txt"
    sentinel.write_text("보존", encoding="utf-8")
    with pytest.raises(ConflictError, match="존재하지 않는 별도 경로"):
        SFTTrainer(nonempty).run()
    assert sentinel.read_text(encoding="utf-8") == "보존"
    assert list(nonempty.run_dir.iterdir()) == [sentinel]

    staged = _config(tmp_path / "staged-fresh", max_steps=2)
    first = SFTTrainer(staged)
    first.run(stop_after_steps=1)
    checkpoint = staged.run_dir / "checkpoints/latest.pt"
    before = checkpoint.read_bytes()
    with pytest.raises(ConflictError, match="존재하지 않는 별도 경로"):
        SFTTrainer(staged).run()
    assert checkpoint.read_bytes() == before

    resumed = SFTTrainer(staged)
    resumed.resume(checkpoint)
    assert resumed.run()["step"] == 2

    config_path = tmp_path / "fresh-contract.yaml"
    config_path.write_text(
        yaml.safe_dump(staged.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    runner = CliRunner()
    fresh_cli = runner.invoke(app, ["sft", "train", "--config", str(config_path)])
    assert fresh_cli.exit_code != 0
    assert "존재하지 않는 별도 경로" in fresh_cli.stderr
    resume_cli = runner.invoke(app, ["sft", "resume", "--config", str(config_path)])
    assert resume_cli.exit_code == 0


def test_sft_pilot과_full은_동일_base에서_서로_다른_fresh_run을_시작한다(
    tmp_path: Path,
) -> None:
    baseline_config = _config(tmp_path / "baseline")
    baseline = SFTTrainer(baseline_config)
    for parameter in baseline.model.parameters():
        parameter.data.fill_(0.0625)
    base_checkpoint = baseline.save()
    expected_sha = sha256_file(base_checkpoint)

    pilot_config = baseline_config.model_copy(
        update={"base_checkpoint": base_checkpoint, "run_dir": tmp_path / "pilot-run"}
    )
    full_config = baseline_config.model_copy(
        update={"base_checkpoint": base_checkpoint, "run_dir": tmp_path / "full-run"}
    )
    assert SFTTrainer(pilot_config).run()["step"] == 1
    assert SFTTrainer(full_config).run()["step"] == 1
    assert pilot_config.run_dir != full_config.run_dir
    for config in (pilot_config, full_config):
        manifest = json.loads((config.run_dir / "data-manifest.json").read_text())
        assert manifest["base_checkpoint"]["sha256"] == expected_sha

    with pytest.raises(ConflictError, match="존재하지 않는 별도 경로"):
        SFTTrainer(pilot_config).run()


def test_sft_validation_uses_same_fixed_subset_every_time(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _write(
        config.heldout_data,
        [
            _row("heldout-1", "heldout", "인사해 주세요", "안녕하세요"),
            _row("heldout-2", "heldout", "이름을 말해 주세요", "LLMEX입니다"),
        ],
    )
    trainer = SFTTrainer(config)
    first_loss = trainer.validate()
    first_state = trainer.validation_sampler.state_dict()
    second_loss = trainer.validate()
    assert second_loss == pytest.approx(first_loss, abs=0.0, rel=0.0)
    assert trainer.validation_sampler.state_dict() == first_state
    assert trainer.validation_batches_seen == 2


def test_sft_max_steps_extension_preserves_original_scheduler_horizon(tmp_path: Path) -> None:
    config = _config(tmp_path, max_steps=1)
    SFTTrainer(config).run()
    extended = config.model_copy(update={"max_steps": 3})
    trainer = SFTTrainer(extended)
    trainer.resume(config.run_dir / "checkpoints/latest.pt")
    assert trainer.scheduler_horizon == 1
    trainer.run()
    events = [
        json.loads(line)
        for line in (config.run_dir / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    learning_rates = [event["learning_rate"] for event in events if event["event"] == "sft"]
    assert learning_rates == pytest.approx(
        [
            config.optimizer.learning_rate,
            config.optimizer.min_learning_rate,
            config.optimizer.min_learning_rate,
        ]
    )
    payload = torch.load(
        config.run_dir / "checkpoints/latest.pt", map_location="cpu", weights_only=True
    )
    assert payload["scheduler"] == {
        "step": 3,
        "horizon": 1,
        "extension_policy": "hold-minimum",
    }


def test_sft_resume_rejects_corrupted_strict_state(tmp_path: Path) -> None:
    config = _config(tmp_path)
    trainer = SFTTrainer(config)
    trainer.run()
    checkpoint = config.run_dir / "checkpoints/latest.pt"
    corruptions: dict[str, tuple[str, object]] = {
        "precision": ("precision", "fp16"),
        "micro-step": ("micro_step", 1),
        "best-loss": ("best_validation_loss", float("nan")),
        "validation-count": ("validation_batches_seen", -1),
        "scheduler": (
            "scheduler",
            {"step": 99, "horizon": 1, "extension_policy": "hold-minimum"},
        ),
        "train-sampler": ("sampler", {"seed": config.seed, "epoch": 0, "cursor": 999}),
        "validation-sampler": ("validation_sampler", {}),
        "optimizer": ("optimizer", {}),
        "scaler": ("scaler", {"scale": 1.0}),
        "rng": ("rng", {}),
    }
    for name, (field, value) in corruptions.items():
        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        payload[field] = value
        damaged = tmp_path / name
        from llmex.train.checkpoint import save_checkpoint

        path = save_checkpoint(damaged, payload, step=1)
        with pytest.raises(IntegrityError):
            SFTTrainer(config).resume(path)


def test_sft_checkpoint_is_rejected_inside_accumulation(tmp_path: Path) -> None:
    trainer = SFTTrainer(_config(tmp_path))
    trainer.micro_step = 1
    with pytest.raises(IntegrityError, match="optimizer 경계"):
        trainer.save()


@pytest.mark.parametrize("operation", ["generate", "evaluate"])
def test_sft_inference_rejects_corrupted_non_model_state(tmp_path: Path, operation: str) -> None:
    config = _config(tmp_path)
    result = SFTTrainer(config).run()
    payload = torch.load(Path(str(result["checkpoint"])), map_location="cpu", weights_only=True)
    payload["optimizer"] = {}
    damaged = tmp_path / f"damaged-{operation}.pt"
    torch.save(payload, damaged)
    with pytest.raises(IntegrityError, match="optimizer"):
        if operation == "generate":
            generate_chat(config, damaged, "안녕")
        else:
            evaluate_chat(config, damaged)
