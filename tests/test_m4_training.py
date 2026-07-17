# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
import json
import pickle
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import torch
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import ModelConfig, OptimizerConfig, TrainingConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.model import CausalLM
from llmex.train.checkpoint import (
    CHECKPOINT_CUDA_RNG_STATE_NUMEL,
    audit_checkpoints,
    load_checkpoint,
    save_checkpoint,
)
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
        load_checkpoint(checkpoint, trainer.fingerprints, supported_schema_versions={1})
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
        load_checkpoint(checkpoint, {}, supported_schema_versions={1})
    assert not marker.exists()


def test_train_audit_checks_completed_pointers_hashes_and_finite_tensors(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    config = _config(manifest, tmp_path / "audit", max_steps=1)
    Trainer(config).run()

    report = audit_checkpoints(config)
    checkpoints = cast(dict[str, dict[str, Any]], report["checkpoints"])
    assert report["status"] == "통과"
    assert set(checkpoints) == {"step", "latest", "best"}
    assert all(value["step"] == 1 for value in checkpoints.values())
    assert all(len(value["sha256"]) == 64 for value in checkpoints.values())
    assert all(value["model"]["finite"] for value in checkpoints.values())
    assert checkpoints["step"]["sha256"] == checkpoints["latest"]["sha256"]
    assert checkpoints["step"]["bytes"] == checkpoints["latest"]["bytes"]
    assert all(value["optimizer"]["resume_state"] for value in checkpoints.values())
    assert not (config.run_dir / "checkpoints/final.pt").exists()

    runner = CliRunner()
    config_path = tmp_path / "audit.yaml"
    import yaml

    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    cli = runner.invoke(app, ["train", "audit", "--config", str(config_path)])
    assert cli.exit_code == 0, cli.output
    assert json.loads(cli.output)["completed_step"] == 1

    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    first = next(iter(payload["model"].values()))
    first.view(-1)[0] = float("inf")
    torch.save(payload, best)
    with pytest.raises(IntegrityError, match="NaN/Inf"):
        audit_checkpoints(config)
    best.unlink()
    with pytest.raises(IntegrityError, match="best checkpoint가 없습니다"):
        audit_checkpoints(config)


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_train_audit_rejects_nonfinite_model_tensors(tmp_path: Path, nonfinite: float) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    first = next(iter(payload["model"].values()))
    first.view(-1)[0] = nonfinite
    torch.save(payload, best)
    with pytest.raises(IntegrityError, match="NaN/Inf"):
        audit_checkpoints(config)


@pytest.mark.parametrize("corruption", ["missing", "shape", "dtype"])
def test_train_audit_rejects_model_state_contract_corruption(
    tmp_path: Path, corruption: str
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    name = next(iter(payload["model"]))
    if corruption == "missing":
        del payload["model"][name]
    elif corruption == "shape":
        payload["model"][name] = payload["model"][name].reshape(-1)[:-1]
    else:
        payload["model"][name] = payload["model"][name].to(torch.float64)
    torch.save(payload, best)
    with pytest.raises(IntegrityError, match=r"모델 (key|tensor shape|tensor dtype)"):
        audit_checkpoints(config)


@pytest.mark.parametrize(
    "corruption", ["optimizer", "rng", "sampler", "validation_sampler", "scaler"]
)
def test_train_audit_rejects_resume_state_corruption(tmp_path: Path, corruption: str) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    if corruption == "optimizer":
        state = next(iter(payload["optimizer"]["state"].values()))
        state["exp_avg"].view(-1)[0] = float("inf")
    elif corruption == "rng":
        payload["rng"]["torch_cpu"] = payload["rng"]["torch_cpu"].to(torch.int16)
    elif corruption == "sampler":
        payload["sampler"]["cursor"] += 1
    elif corruption == "validation_sampler":
        payload["validation_sampler"]["cursor"] += 1
    else:
        payload["scaler"] = {"scale": float("inf")}
    torch.save(payload, best)
    with pytest.raises(IntegrityError, match=r"optimizer|RNG|sampler|scaler"):
        audit_checkpoints(config)


@pytest.mark.parametrize(
    "state_numel",
    [CHECKPOINT_CUDA_RNG_STATE_NUMEL - 1, CHECKPOINT_CUDA_RNG_STATE_NUMEL + 1],
)
def test_train_audit_requires_exact_cuda_rng_size_when_cuda_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state_numel: int
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    payload["rng"]["torch_cuda"] = [torch.zeros(state_numel, dtype=torch.uint8)]
    torch.save(payload, best)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(IntegrityError, match="CUDA RNG state"):
        audit_checkpoints(config)


def test_train_audit_allows_missing_cuda_rng_state_with_false_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    payload["rng"].pop("torch_cuda", None)
    save_checkpoint(best.parent, payload, step=1, best=True)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)

    report = audit_checkpoints(config)
    checkpoints = cast(dict[str, dict[str, Any]], report["checkpoints"])
    assert all(not checkpoint["rng"]["torch_cuda"] for checkpoint in checkpoints.values())


@pytest.mark.parametrize("cuda_state", [None, []])
def test_train_audit_rejects_present_invalid_cuda_rng_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cuda_state: object
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    payload["rng"]["torch_cuda"] = cuda_state
    save_checkpoint(best.parent, payload, step=1, best=True)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(IntegrityError, match="torch CUDA RNG"):
        audit_checkpoints(config)


def test_train_audit_requires_cuda_rng_state_per_available_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    payload["rng"]["torch_cuda"] = [torch.zeros(CHECKPOINT_CUDA_RNG_STATE_NUMEL, dtype=torch.uint8)]
    torch.save(payload, best)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)

    with pytest.raises(IntegrityError, match="CUDA RNG state count"):
        audit_checkpoints(config)


def test_train_audit_restores_each_cuda_rng_state_on_indexed_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    payload["rng"]["torch_cuda"] = [
        torch.zeros(CHECKPOINT_CUDA_RNG_STATE_NUMEL, dtype=torch.uint8),
        torch.ones(CHECKPOINT_CUDA_RNG_STATE_NUMEL, dtype=torch.uint8),
    ]
    save_checkpoint(best.parent, payload, step=1, best=True)
    original_generator = torch.Generator
    restored_devices: list[str] = []

    class FakeCudaGenerator:
        def __init__(self, device: str) -> None:
            restored_devices.append(device)

        def set_state(self, state: torch.Tensor):
            assert state.dtype == torch.uint8
            assert state.shape == (CHECKPOINT_CUDA_RNG_STATE_NUMEL,)
            return self

    def generator(*, device: str) -> torch.Generator | FakeCudaGenerator:
        if device == "cpu":
            return original_generator(device=device)
        return FakeCudaGenerator(device)

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)
    monkeypatch.setattr(torch, "Generator", generator)

    report = audit_checkpoints(config)
    checkpoints = cast(dict[str, dict[str, Any]], report["checkpoints"])
    assert all(checkpoint["rng"]["torch_cuda"] for checkpoint in checkpoints.values())
    assert restored_devices == ["cuda:0", "cuda:1"] * 3


def test_train_audit_wraps_cuda_generator_restore_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    best = config.run_dir / "checkpoints/best.pt"
    payload = torch.load(best, map_location="cpu", weights_only=True)
    payload["rng"]["torch_cuda"] = [torch.zeros(CHECKPOINT_CUDA_RNG_STATE_NUMEL, dtype=torch.uint8)]
    save_checkpoint(best.parent, payload, step=1, best=True)
    original_generator = torch.Generator

    def generator(*, device: str) -> torch.Generator:
        if device.startswith("cuda"):
            raise RuntimeError("synthetic CUDA generator failure")
        return original_generator(device=device)

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(torch, "Generator", generator)

    with pytest.raises(IntegrityError, match="synthetic CUDA generator failure"):
        audit_checkpoints(config)


def test_train_audit_rejects_every_malformed_fp16_scaler_with_cli_code_5(
    tmp_path: Path,
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    Trainer(config).run()
    step = config.run_dir / "checkpoints/step-00000001.pt"
    payload = torch.load(step, map_location="cpu", weights_only=True)
    payload["precision"] = "fp16"
    valid_scaler: dict[str, object] = {
        "scale": 65536.0,
        "growth_factor": 2.0,
        "backoff_factor": 0.5,
        "growth_interval": 2000,
        "_growth_tracker": 0,
    }
    import yaml

    config_path = tmp_path / "audit.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    fields = tuple(valid_scaler)
    corruptions: list[tuple[str, object]] = [
        *((field, "invalid") for field in fields),
        *((field, True) for field in fields),
        *(
            (field, value)
            for field in fields
            for value in (float("nan"), float("inf"), float("-inf"))
        ),
        ("scale", 0.0),
        ("scale", -1.0),
        ("growth_factor", 1.0),
        ("growth_factor", 0.0),
        ("backoff_factor", 0.0),
        ("backoff_factor", 1.0),
        ("backoff_factor", -1.0),
        ("backoff_factor", 2.0),
        ("growth_interval", 1.5),
        ("growth_interval", 0),
        ("growth_interval", -1),
        ("_growth_tracker", 1.5),
        ("_growth_tracker", -1),
    ]
    for field, value in corruptions:
        payload["scaler"] = {**valid_scaler, field: value}
        torch.save(payload, step)

        try:
            audit_checkpoints(config)
        except IntegrityError as exc:
            assert "scaler" in str(exc), f"{field}={value!r}: {exc}"
        else:
            pytest.fail(f"fp16 scaler 손상을 허용했습니다: {field}={value!r}")
        cli = CliRunner().invoke(app, ["train", "audit", "--config", str(config_path)])
        assert cli.exit_code == 5, f"{field}={value!r}: {cli.output}"


def test_train_audit_rejects_fingerprint_and_step_latest_mismatch_with_cli_code_5(
    tmp_path: Path,
) -> None:
    config = _config(_manifest(tmp_path), tmp_path / "audit", max_steps=1)
    trainer = Trainer(config)
    trainer.run()
    latest = config.run_dir / "checkpoints/latest.pt"
    payload = torch.load(latest, map_location="cpu", weights_only=True)
    payload["fingerprints"] = {**payload["fingerprints"], "model": "0" * 64}
    torch.save(payload, latest)
    with pytest.raises(IntegrityError, match="fingerprint"):
        audit_checkpoints(config)

    import yaml

    config_path = tmp_path / "audit.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    cli = CliRunner().invoke(app, ["train", "audit", "--config", str(config_path)])
    assert cli.exit_code == 5

    trainer.save()
    payload = torch.load(latest, map_location="cpu", weights_only=True)
    payload["step"] = 0
    payload["scheduler"] = {"step": 0}
    torch.save(payload, latest)
    with pytest.raises(IntegrityError, match="완료 checkpoint step"):
        audit_checkpoints(config)


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
