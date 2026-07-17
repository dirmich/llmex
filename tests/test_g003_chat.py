# pyright: reportUnknownMemberType=false
import json
from pathlib import Path

import pytest
import torch
from tokenizers.trainers import BpeTrainer
from typer.testing import CliRunner

from llmex.chat.data import Message, load_chat_jsonl
from llmex.chat.runtime import SFTTrainer, evaluate_chat, generate_chat
from llmex.chat.template import tokenize_chat
from llmex.cli import app
from llmex.config import ModelConfig, OptimizerConfig, SFTConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.tokenizer.core import SPECIAL_TOKENS, build_tokenizer
from llmex.train.checkpoint import load_checkpoint, save_checkpoint


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
