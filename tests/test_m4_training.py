# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
import json
import pickle
from pathlib import Path

import numpy as np
import pytest
import torch
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import ModelConfig, OptimizerConfig, TrainingConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.model import CausalLM
from llmex.train.checkpoint import load_checkpoint
from llmex.train.data import DeterministicBatchSampler, TokenShardDataset
from llmex.train.engine import Trainer
from llmex.train.optim import learning_rate, parameter_groups


def _manifest(tmp_path: Path, *, corrupt: bool = False) -> Path:
    directory = tmp_path / "shards"
    directory.mkdir(parents=True)
    splits: dict[str, object] = {}
    for split, offset in (("train", 0), ("validation", 1), ("test", 2)):
        tokens = np.tile(
            np.array([1, 4 + offset, 5 + offset, 6 + offset, 7 + offset, 2], dtype="<u2"), 30
        )
        first, second = tokens[:77], tokens[77:]
        shards: list[dict[str, object]] = []
        for index, values in enumerate((first, second)):
            path = directory / f"{split}-{index:05d}.bin"
            values.tofile(path)
            shards.append(
                {
                    "path": path.name,
                    "tokens": len(values),
                    "sha256": sha256_file(path),
                    "min_id": int(values.min()),
                    "max_id": int(values.max()),
                }
            )
        splits[split] = {"tokens": len(tokens), "documents": 30, "boundaries": [], "shards": shards}
    manifest: dict[str, object] = {
        "schema_version": 1,
        "dtype": "<u2",
        "tokenizer_sha256": "a" * 64,
        "tokenizer_fingerprint": "b" * 64,
        "corpus": {"fingerprint": "c" * 64},
        "eos_id": 2,
        "splits": splits,
    }
    manifest["fingerprint"] = fingerprint(manifest)
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    if corrupt:
        (directory / "train-00000.bin").write_bytes("손상".encode())
    return path


def _config(manifest: Path, run_dir: Path, *, max_steps: int = 4) -> TrainingConfig:
    return TrainingConfig(
        name="m4-test",
        seed=123,
        model=ModelConfig(
            name="tiny",
            vocab_size=16,
            max_seq_len=8,
            n_layers=1,
            d_model=8,
            n_heads=2,
            n_kv_heads=1,
            ffn_hidden_size=16,
            dropout=0.0,
        ),
        shards_manifest=manifest,
        run_dir=run_dir,
        device="cpu",
        precision="fp32",
        sequence_length=8,
        micro_batch_size=2,
        gradient_accumulation_steps=2,
        max_steps=max_steps,
        gradient_clip_norm=1.0,
        validation_interval=2,
        validation_batches=1,
        checkpoint_interval=2,
        log_interval=1,
        optimizer=OptimizerConfig(
            learning_rate=0.03, min_learning_rate=0.003, weight_decay=0.1, warmup_steps=1
        ),
    )


def test_shard_boundary_window_sampler_state_and_corruption(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    dataset = TokenShardDataset(manifest, "train", 8)
    assert dataset.window(73).tolist() == [4, 5, 6, 7, 2, 1, 4, 5]
    first = DeterministicBatchSampler(dataset.window_count, 3, 9)
    first.next()
    state = first.state_dict()
    expected = first.next()
    restored = DeterministicBatchSampler(dataset.window_count, 3, 9)
    restored.load_state_dict(state)
    assert restored.next() == expected
    bad = tmp_path / "bad"
    with pytest.raises(IntegrityError, match="checksum"):
        TokenShardDataset(_manifest(bad, corrupt=True), "train", 8)


def test_adamw_groups_and_scheduler_boundaries() -> None:
    model = CausalLM(_config(Path("x"), Path("y")).model)
    groups = parameter_groups(model, 0.1)
    assert groups[0]["weight_decay"] == 0.1 and groups[1]["weight_decay"] == 0.0
    assert sum(len(group["params"]) for group in groups) == len(list(model.parameters()))  # type: ignore[arg-type]
    config = OptimizerConfig(learning_rate=1.0, min_learning_rate=0.1, warmup_steps=2)
    assert learning_rate(0, 6, config) == 0.5
    assert learning_rate(1, 6, config) == 1.0
    assert learning_rate(5, 6, config) == pytest.approx(0.1)


def test_gradient_accumulation_matches_large_batch() -> None:
    torch.manual_seed(7)
    base = CausalLM(_config(Path("x"), Path("y")).model)
    accumulated = CausalLM(base.config)
    accumulated.load_state_dict(base.state_dict())
    tokens = torch.randint(0, 16, (4, 8))
    large_opt = torch.optim.SGD(base.parameters(), lr=0.01)
    small_opt = torch.optim.SGD(accumulated.parameters(), lr=0.01)
    large_opt.zero_grad()
    large_loss = base(tokens, targets=tokens).loss
    assert large_loss is not None
    large_loss.backward()
    large_opt.step()
    small_opt.zero_grad()
    for part in tokens.chunk(2):
        loss = accumulated(part, targets=part).loss
        assert loss is not None
        (loss / 2).backward()
    small_opt.step()
    for first, second in zip(base.parameters(), accumulated.parameters(), strict=True):
        torch.testing.assert_close(first, second, atol=2e-7, rtol=2e-6)


def test_deterministic_resume_equivalence_metrics_and_best(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    config = _config(manifest, tmp_path / "continuous")
    continuous = Trainer(config)
    continuous.run()
    expected = {key: value.clone() for key, value in continuous.model.state_dict().items()}

    resumed_config = _config(manifest, tmp_path / "resumed")
    interrupted = Trainer(resumed_config)
    original_save = interrupted.save

    def stopping_save(*, best: bool = False) -> Path:
        path = original_save(best=best)
        if interrupted.step == 2 and not best:
            interrupted.terminate_requested = True
        return path

    interrupted.save = stopping_save  # type: ignore[method-assign]
    interrupted.run()
    assert interrupted.step == 2
    resumed = Trainer(resumed_config)
    resumed.resume()
    resumed.run()
    assert resumed.step == 4
    for key, value in resumed.model.state_dict().items():
        torch.testing.assert_close(value, expected[key], atol=0, rtol=0)
    assert (resumed_config.run_dir / "checkpoints/latest.pt").is_file()
    assert (resumed_config.run_dir / "checkpoints/best.pt").is_file()
    events = [
        json.loads(line)
        for line in (resumed_config.run_dir / "metrics.jsonl").read_text().splitlines()
    ]
    assert {event["event"] for event in events} >= {"train", "validation"}
    train_events = [event for event in events if event["event"] == "train"]
    assert all(event["session_tokens"] <= event["tokens"] for event in train_events)


def test_fingerprint_rejection_nan_diagnostic_and_corrupt_checkpoint(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    trainer = Trainer(_config(manifest, tmp_path / "run", max_steps=1))
    trainer.run()
    changed = _config(manifest, tmp_path / "run", max_steps=1).model_copy(update={"seed": 124})
    with pytest.raises(IntegrityError, match="fingerprint"):
        Trainer(changed).resume()
    checkpoint = tmp_path / "broken.pt"
    checkpoint.write_bytes(b"not torch")
    with pytest.raises(IntegrityError, match="읽을 수 없습니다"):
        load_checkpoint(checkpoint, trainer.fingerprints)
    failing = Trainer(_config(manifest, tmp_path / "nan", max_steps=1))
    for parameter in failing.model.parameters():
        parameter.data.fill_(float("nan"))
        break
    with pytest.raises(IntegrityError, match="loss"):
        failing.run()
    assert (failing.run_dir / "failure.json").is_file()


def test_checkpoint_never_executes_malicious_pickle(tmp_path: Path) -> None:
    marker = tmp_path / "executed"

    class Payload:
        def __reduce__(self) -> tuple[object, tuple[str]]:
            return (eval, (f"open({str(marker)!r}, 'w').write('pwned')",))

    checkpoint = tmp_path / "malicious.pt"
    checkpoint.write_bytes(pickle.dumps(Payload()))
    with pytest.raises(IntegrityError, match="읽을 수 없습니다"):
        load_checkpoint(checkpoint, {})
    assert not marker.exists()


def test_cpu_overfit_and_cli_train_resume_smoke(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    config = _config(manifest, tmp_path / "overfit", max_steps=50)
    config = config.model_copy(update={"validation_interval": 50, "checkpoint_interval": 50})
    trainer = Trainer(config)
    initial = trainer.validate()
    trainer.run()
    assert trainer.last_loss is not None and trainer.last_loss < initial
    yaml_path = tmp_path / "train.yaml"
    import yaml

    yaml_path.write_text(
        yaml.safe_dump(
            config.model_copy(
                update={
                    "run_dir": tmp_path / "cli",
                    "max_steps": 1,
                    "validation_interval": 1,
                    "checkpoint_interval": 1,
                }
            ).model_dump(mode="json"),
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    runner = CliRunner()
    dry = runner.invoke(app, ["train", "smoke", "--config", str(yaml_path), "--dry-run"])
    assert dry.exit_code == 0 and not (tmp_path / "cli").exists()
    result = runner.invoke(app, ["train", "run", "--config", str(yaml_path)])
    assert result.exit_code == 0, result.output
    resume = runner.invoke(app, ["train", "resume", "--config", str(yaml_path)])
    assert resume.exit_code == 0, resume.output
