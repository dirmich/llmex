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
    }
    basis = {"id": identifier, "messages": messages, "provenance": provenance, "split": split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _config(tmp_path: Path, *, max_steps: int = 1) -> SFTConfig:
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
            max_seq_len=64,
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
        sequence_length=48,
        micro_batch_size=1,
        max_steps=max_steps,
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

    encoded = tokenize_chat(
        load_tokenizer(config.tokenizer_dir),
        (
            Message(role="system", content="안전하게 답하세요"),
            Message(role="user", content="안녕"),
            Message(role="assistant", content="반가워요"),
        ),
        max_length=64,
    )
    assert encoded.labels[0] == -100
    trained = [label for label in encoded.labels if label != -100]
    assert trained and trained[-1] == 2
    assert any(label == -100 for label in encoded.labels[1:])


def test_sft_atomic_resume_eval_generation_and_cli(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = SFTTrainer(config)
    result = first.run()
    checkpoint = Path(str(result["checkpoint"]))
    assert checkpoint.is_file() and (config.run_dir / "data-manifest.json").is_file()
    resumed_config = config.model_copy(update={"max_steps": 2})
    resumed = SFTTrainer(resumed_config)
    resumed.resume(config.run_dir / "checkpoints/latest.pt")
    assert resumed.step == 1 and resumed.cursor == 1
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
