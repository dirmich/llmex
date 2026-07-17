"""Assistant-only SFT trainer, 원자 재개, held-out gate와 chat 생성."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import hashlib
import io
import json
import math
import os
import random
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch

from llmex.chat.data import ChatDataset, Message, load_chat_jsonl
from llmex.chat.template import render_chat, tokenize_chat
from llmex.config import SFTConfig
from llmex.data.io import write_json
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.model import CausalLM, GenerationConfig
from llmex.tokenizer.core import SPECIAL_IDS, load_tokenizer
from llmex.train.checkpoint import (
    SFT_CHECKPOINT_REQUIRED_STATE,
    load_checkpoint,
    restore_rng_state,
    rng_state,
    save_checkpoint,
    validate_model_state,
)
from llmex.train.data import DeterministicBatchSampler
from llmex.train.optim import learning_rate, parameter_groups
from llmex.train.runtime import (
    autocast_context,
    resolve_device,
    resolve_precision,
    seed_everything,
)


def _datasets(config: SFTConfig) -> tuple[ChatDataset, ChatDataset]:
    allowed = set(config.allowed_licenses)
    train = load_chat_jsonl(config.train_data, split="train", allowed_licenses=allowed)
    heldout = load_chat_jsonl(config.heldout_data, split="heldout", allowed_licenses=allowed)
    overlap = {item.sha256 for item in train.examples} & {item.sha256 for item in heldout.examples}
    if overlap:
        raise IntegrityError("train/heldout 대화 hash 누출을 발견했습니다")
    return train, heldout


def _fingerprints(
    config: SFTConfig,
    train: ChatDataset,
    heldout: ChatDataset,
    base_provenance: Mapping[str, object],
) -> dict[str, str]:
    manifest = config.tokenizer_dir / "tokenizer-manifest.json"
    return {
        "config": fingerprint(config.model_dump(mode="json", exclude={"max_steps"})),
        "model": fingerprint(config.model.model_dump(mode="json")),
        "tokenizer": sha256_file(manifest),
        "train": train.fingerprint,
        "heldout": heldout.fingerprint,
        "base_checkpoint_sha256": str(base_provenance["sha256"]),
        "base_checkpoint_provenance": fingerprint(base_provenance),
    }


def _load_base(path: Path | None) -> tuple[dict[str, torch.Tensor] | None, dict[str, object]]:
    if path is None:
        absent = fingerprint({"base_checkpoint": None})
        return None, {"present": False, "sha256": absent}
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            data = stream.read()
            after = os.fstat(stream.fileno())
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after or len(data) != before.st_size:
            raise IntegrityError("base checkpoint immutable snapshot을 읽을 수 없습니다")
        value = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
        if (
            not isinstance(value, dict)
            or isinstance(value.get("schema_version"), bool)
            or value.get("schema_version") not in {1, 2}
        ):
            raise IntegrityError("base checkpoint schema가 올바르지 않습니다")
        state = validate_model_state(
            cast(dict[str, Any], value).get("model"), context="base checkpoint model"
        )
        raw_fingerprints = value.get("fingerprints")
        if not isinstance(raw_fingerprints, Mapping) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in raw_fingerprints.items()
        ):
            raise IntegrityError("base checkpoint 학습 fingerprint가 올바르지 않습니다")
        step = value.get("step")
        if not isinstance(step, int) or isinstance(step, bool) or step < 0:
            raise IntegrityError("base checkpoint step이 올바르지 않습니다")
        provenance: dict[str, object] = {
            "present": True,
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(data).hexdigest(),
            "schema_version": value["schema_version"],
            "kind": value.get("kind", "pretrain"),
            "step": step,
            "training_fingerprints": dict(raw_fingerprints),
        }
        return state, provenance
    except IntegrityError:
        raise
    except Exception as exc:
        raise IntegrityError(f"base checkpoint를 재사용할 수 없습니다: {exc}") from exc


def _batch(
    tokenizer: Any, examples: list[Any], max_length: int
) -> tuple[torch.Tensor, torch.Tensor]:
    encoded = [
        tokenize_chat(tokenizer, example.messages, max_length=max_length) for example in examples
    ]
    width = max(len(item.input_ids) for item in encoded)
    inputs, labels = [], []
    for item in encoded:
        padding = width - len(item.input_ids)
        inputs.append(list(item.input_ids) + [SPECIAL_IDS["<pad>"]] * padding)
        labels.append(list(item.labels) + [-100] * padding)
    return torch.tensor(inputs, dtype=torch.long), torch.tensor(labels, dtype=torch.long)


def _expected_sampler_state(
    sampler: DeterministicBatchSampler, batches_seen: int
) -> dict[str, int]:
    batches_per_epoch = sampler.size // sampler.batch_size
    if batches_seen == 0:
        return {"seed": sampler.seed, "epoch": 0, "cursor": 0}
    return {
        "seed": sampler.seed,
        "epoch": (batches_seen - 1) // batches_per_epoch,
        "cursor": ((batches_seen - 1) % batches_per_epoch + 1) * sampler.batch_size,
    }


def _require_finite_state(value: object, location: str) -> None:
    if isinstance(value, torch.Tensor):
        if not bool(torch.isfinite(value).all()):
            raise IntegrityError(f"SFT {location} 상태에 NaN/Inf가 있습니다")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise IntegrityError(f"SFT {location} 상태에 NaN/Inf가 있습니다")
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for nested in mapping.values():
            _require_finite_state(nested, location)
    elif isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        for nested in sequence:
            _require_finite_state(nested, location)


def _validate_optimizer_state(
    raw_state: object, optimizer: torch.optim.Optimizer, step: int
) -> dict[str, Any]:
    if not isinstance(raw_state, Mapping) or set(raw_state) != {"state", "param_groups"}:
        raise IntegrityError("SFT optimizer 상태 구조가 올바르지 않습니다")
    state = cast(Mapping[str, object], raw_state)
    parameter_state = state["state"]
    raw_groups = state["param_groups"]
    if not isinstance(parameter_state, Mapping) or not isinstance(raw_groups, list):
        raise IntegrityError("SFT optimizer 상태 구조가 올바르지 않습니다")

    expected_groups = optimizer.state_dict()["param_groups"]
    if len(raw_groups) != len(expected_groups):
        raise IntegrityError("SFT optimizer parameter group 수가 다릅니다")
    parameter_by_id: dict[int, torch.Tensor] = {}
    expected_ids: list[int] = []
    for group_index, (raw_group, expected_group, live_group) in enumerate(
        zip(raw_groups, expected_groups, optimizer.param_groups, strict=True)
    ):
        if not isinstance(raw_group, Mapping) or set(raw_group) != set(expected_group):
            raise IntegrityError("SFT optimizer parameter group 구조가 올바르지 않습니다")
        actual_ids = raw_group.get("params")
        expected_group_ids = expected_group["params"]
        if actual_ids != expected_group_ids or not isinstance(actual_ids, list):
            raise IntegrityError("SFT optimizer parameter id가 다릅니다")
        for parameter_id, parameter in zip(actual_ids, live_group["params"], strict=True):
            if not isinstance(parameter_id, int) or isinstance(parameter_id, bool):
                raise IntegrityError("SFT optimizer parameter id가 올바르지 않습니다")
            parameter_by_id[parameter_id] = cast(torch.Tensor, parameter)
        expected_ids.extend(cast(list[int], actual_ids))
        for key, expected_value in expected_group.items():
            if key not in {"lr", "params"} and raw_group[key] != expected_value:
                raise IntegrityError(
                    f"SFT optimizer parameter group 값이 다릅니다: {group_index}.{key}"
                )
        _require_finite_state(raw_group, f"optimizer.param_groups[{group_index}]")

    typed_parameter_state = cast(Mapping[object, object], parameter_state)
    if set(typed_parameter_state) != (set(expected_ids) if step > 0 else set()):
        raise IntegrityError("SFT optimizer parameter 상태 key가 다릅니다")
    for parameter_id in expected_ids:
        if step == 0:
            break
        raw_item = typed_parameter_state[parameter_id]
        if not isinstance(raw_item, Mapping) or not {
            "step",
            "exp_avg",
            "exp_avg_sq",
        }.issubset(raw_item):
            raise IntegrityError("SFT optimizer parameter 상태가 손상되었습니다")
        item = cast(Mapping[str, object], raw_item)
        parameter = parameter_by_id[parameter_id]
        for key in ("exp_avg", "exp_avg_sq"):
            tensor = item[key]
            if (
                not isinstance(tensor, torch.Tensor)
                or tensor.shape != parameter.shape
                or tensor.dtype != parameter.dtype
            ):
                raise IntegrityError(f"SFT optimizer {key} shape/dtype이 다릅니다")
        optimizer_step = item["step"]
        if (
            not isinstance(optimizer_step, torch.Tensor)
            or optimizer_step.numel() != 1
            or float(optimizer_step) != step
        ):
            raise IntegrityError("SFT optimizer step이 checkpoint step과 다릅니다")
        _require_finite_state(item, f"optimizer.state[{parameter_id}]")
    return cast(dict[str, Any], dict(state))


def _validate_rng_state(raw_state: object) -> dict[str, object]:
    if not isinstance(raw_state, dict) or not {"python", "numpy", "torch_cpu"}.issubset(raw_state):
        raise IntegrityError("SFT RNG 상태 구조가 올바르지 않습니다")
    if set(raw_state) - {"python", "numpy", "torch_cpu", "torch_cuda"}:
        raise IntegrityError("SFT RNG 상태에 알 수 없는 값이 있습니다")
    state = cast(dict[str, object], raw_state)
    try:
        random.Random().setstate(state["python"])  # type: ignore[arg-type]
        numpy_state = state["numpy"]
        if not isinstance(numpy_state, dict) or set(numpy_state) != {
            "algorithm",
            "keys",
            "position",
            "has_gauss",
            "cached_gaussian",
        }:
            raise ValueError("numpy RNG 구조")
        typed_numpy = cast(dict[str, object], numpy_state)
        keys = typed_numpy["keys"]
        if not isinstance(keys, torch.Tensor) or keys.dtype != torch.uint32 or keys.shape != (624,):
            raise ValueError("numpy RNG keys")
        np.random.RandomState().set_state(
            (
                str(typed_numpy["algorithm"]),
                keys.cpu().numpy().astype(np.uint32, copy=False),
                int(cast(int, typed_numpy["position"])),
                int(cast(int, typed_numpy["has_gauss"])),
                float(cast(float, typed_numpy["cached_gaussian"])),
            )
        )
        torch_cpu = state["torch_cpu"]
        if (
            not isinstance(torch_cpu, torch.Tensor)
            or torch_cpu.dtype != torch.uint8
            or torch_cpu.ndim != 1
            or torch_cpu.numel() == 0
        ):
            raise ValueError("torch CPU RNG")
        torch.Generator(device="cpu").set_state(torch_cpu)
        if "torch_cuda" in state:
            cuda_states = state["torch_cuda"]
            if not isinstance(cuda_states, list) or not cuda_states:
                raise ValueError("torch CUDA RNG")
            if not all(
                isinstance(cuda_state, torch.Tensor)
                and cuda_state.dtype == torch.uint8
                and cuda_state.ndim == 1
                and cuda_state.numel() > 0
                for cuda_state in cuda_states
            ):
                raise ValueError("torch CUDA RNG state")
        _require_finite_state(state, "RNG")
    except (TypeError, ValueError, RuntimeError) as exc:
        raise IntegrityError(f"SFT RNG 상태를 복구할 수 없습니다: {exc}") from exc
    return state


class SFTTrainer:
    def __init__(self, config: SFTConfig) -> None:
        self.config = config
        seed_everything(config.seed, config.deterministic)
        self.device = resolve_device(config.device)
        self.precision, self.autocast_dtype, use_scaler = resolve_precision(
            config.precision, self.device
        )
        self.tokenizer = load_tokenizer(config.tokenizer_dir)
        if self.tokenizer.get_vocab_size() != config.model.vocab_size:
            raise IntegrityError("모델 vocab_size와 tokenizer가 다릅니다")
        self.train_data, self.heldout_data = _datasets(config)
        base_state, self.base_checkpoint_provenance = _load_base(config.base_checkpoint)
        self.fingerprints = _fingerprints(
            config, self.train_data, self.heldout_data, self.base_checkpoint_provenance
        )
        self.model = CausalLM(config.model).to(self.device)
        if base_state is not None:
            try:
                self.model.load_state_dict(base_state, strict=True)
            except RuntimeError as exc:
                raise IntegrityError(
                    f"base checkpoint 모델 가중치가 호환되지 않습니다: {exc}"
                ) from exc
        self.optimizer = torch.optim.AdamW(
            parameter_groups(self.model, config.optimizer.weight_decay),
            lr=config.optimizer.learning_rate,
            betas=(config.optimizer.beta1, config.optimizer.beta2),
            eps=config.optimizer.eps,
        )
        self.scaler = torch.amp.GradScaler("cuda", enabled=use_scaler)
        self.sampler = DeterministicBatchSampler(
            len(self.train_data.examples), config.micro_batch_size, config.seed
        )
        self.validation_sampler = DeterministicBatchSampler(
            len(self.heldout_data.examples),
            min(config.micro_batch_size, len(self.heldout_data.examples)),
            config.seed + 1_000_003,
        )
        self.step = 0
        self.scheduler_horizon = config.max_steps
        self.micro_step = 0
        self.best_validation_loss = math.inf
        self.validation_batches_seen = 0
        self.run_dir = config.run_dir

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "kind": "assistant-only-sft",
            "step": self.step,
            "micro_step": self.micro_step,
            "best_validation_loss": self.best_validation_loss,
            "validation_batches_seen": self.validation_batches_seen,
            "fingerprints": self.fingerprints,
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "scheduler": {
                "step": self.step,
                "horizon": self.scheduler_horizon,
                "extension_policy": "hold-minimum",
            },
            "scaler": self.scaler.state_dict(),
            "sampler": self.sampler.state_dict(),
            "validation_sampler": self.validation_sampler.state_dict(),
            "rng": rng_state(),
            "precision": self.precision,
        }

    def save(self, *, best: bool = False) -> Path:
        if self.micro_step != 0:
            raise IntegrityError("SFT checkpoint는 optimizer 경계에서만 저장할 수 있습니다")
        return save_checkpoint(
            self.run_dir / "checkpoints", self._payload(), step=self.step, best=best
        )

    def _restore(self, checkpoint: Mapping[str, Any]) -> None:
        if checkpoint.get("kind") != "assistant-only-sft":
            raise IntegrityError("SFT checkpoint kind가 올바르지 않습니다")
        step = checkpoint.get("step")
        if not isinstance(step, int) or isinstance(step, bool) or step < 0:
            raise IntegrityError("SFT checkpoint step이 올바르지 않습니다")
        if checkpoint.get("micro_step") != 0:
            raise IntegrityError("SFT checkpoint가 accumulation 경계에 있지 않습니다")
        if checkpoint.get("precision") != self.precision:
            raise IntegrityError(
                "SFT checkpoint 실제 precision이 현재 실행과 다릅니다: "
                f"기대={self.precision}, 실제={checkpoint.get('precision')}"
            )
        best_loss = checkpoint.get("best_validation_loss")
        if (
            not isinstance(best_loss, (int, float))
            or isinstance(best_loss, bool)
            or math.isnan(float(best_loss))
            or float(best_loss) < 0.0
        ):
            raise IntegrityError("SFT checkpoint best validation loss가 올바르지 않습니다")
        validation_batches_seen = checkpoint.get("validation_batches_seen")
        if (
            not isinstance(validation_batches_seen, int)
            or isinstance(validation_batches_seen, bool)
            or validation_batches_seen < 0
            or validation_batches_seen % self.config.validation_batches != 0
        ):
            raise IntegrityError("SFT checkpoint 검증 batch 수가 올바르지 않습니다")
        if validation_batches_seen == 0 and not math.isinf(float(best_loss)):
            raise IntegrityError("검증 전 SFT checkpoint의 best loss가 올바르지 않습니다")
        if validation_batches_seen > 0 and not math.isfinite(float(best_loss)):
            raise IntegrityError("검증 후 SFT checkpoint의 best loss가 올바르지 않습니다")
        scheduler = checkpoint.get("scheduler")
        if not isinstance(scheduler, Mapping) or set(scheduler) != {
            "step",
            "horizon",
            "extension_policy",
        }:
            raise IntegrityError("SFT scheduler 상태 구조가 올바르지 않습니다")
        horizon = scheduler.get("horizon")
        if (
            scheduler.get("step") != step
            or not isinstance(horizon, int)
            or isinstance(horizon, bool)
            or horizon <= 0
            or scheduler.get("extension_policy") != "hold-minimum"
            or self.config.max_steps < horizon
            or self.config.max_steps < step
        ):
            raise IntegrityError("SFT scheduler 상태가 step/max_steps와 다릅니다")
        scaler = checkpoint.get("scaler")
        if not isinstance(scaler, dict):
            raise IntegrityError("SFT scaler 상태가 올바르지 않습니다")
        scaler_state = cast(dict[str, Any], scaler)
        if self.precision == "fp16" and not scaler:
            raise IntegrityError("fp16 SFT checkpoint에 scaler 상태가 없습니다")
        if self.precision != "fp16" and scaler:
            raise IntegrityError("fp16이 아닌 SFT checkpoint에 scaler 상태가 있습니다")
        expected_train_sampler = _expected_sampler_state(
            self.sampler, step * self.config.gradient_accumulation_steps
        )
        if checkpoint.get("sampler") != expected_train_sampler:
            raise IntegrityError("SFT train sampler 상태가 step과 다릅니다")
        expected_validation_sampler = _expected_sampler_state(
            self.validation_sampler,
            0 if validation_batches_seen == 0 else self.config.validation_batches,
        )
        if checkpoint.get("validation_sampler") != expected_validation_sampler:
            raise IntegrityError("SFT validation sampler 상태가 검증 batch 수와 다릅니다")
        optimizer_state = _validate_optimizer_state(
            checkpoint.get("optimizer"), self.optimizer, step
        )
        rng = _validate_rng_state(checkpoint.get("rng"))
        _require_finite_state(cast(object, scaler_state), "scaler")
        model_state = validate_model_state(checkpoint.get("model"), context="SFT checkpoint model")
        try:
            self.model.load_state_dict(model_state, strict=True)
            self.optimizer.load_state_dict(optimizer_state)
            self.scaler.load_state_dict(scaler_state)
            self.sampler.load_state_dict(cast(dict[str, int], checkpoint["sampler"]))
            self.validation_sampler.load_state_dict(
                cast(dict[str, int], checkpoint["validation_sampler"])
            )
            restore_rng_state(rng)
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            raise IntegrityError(f"SFT checkpoint 상태를 복원할 수 없습니다: {exc}") from exc
        self.step = step
        self.scheduler_horizon = horizon
        self.micro_step = 0
        self.best_validation_loss = float(best_loss)
        self.validation_batches_seen = validation_batches_seen

    def resume(self, path: Path | None = None) -> None:
        checkpoint = load_checkpoint(
            path or self.run_dir / "checkpoints/latest.pt",
            self.fingerprints,
            supported_schema_versions={2},
            required_state=SFT_CHECKPOINT_REQUIRED_STATE,
        )
        self._restore(checkpoint)

    def _metric(self, event: dict[str, object]) -> None:
        with (self.run_dir / "metrics.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _next_batch(
        self, dataset: ChatDataset, sampler: DeterministicBatchSampler
    ) -> tuple[torch.Tensor, torch.Tensor]:
        examples = [dataset.examples[index] for index in sampler.next()]
        inputs, labels = _batch(self.tokenizer, examples, self.config.sequence_length)
        return inputs.to(self.device), labels.to(self.device)

    def validate(self) -> float:
        was_training = self.model.training
        self.model.eval()
        self.validation_sampler.load_state_dict(_expected_sampler_state(self.validation_sampler, 0))
        weighted_loss = 0.0
        target_total = 0
        with torch.no_grad():
            for _ in range(self.config.validation_batches):
                inputs, labels = self._next_batch(self.heldout_data, self.validation_sampler)
                with autocast_context(self.device, self.autocast_dtype):
                    loss = self.model(inputs, targets=labels).loss
                if loss is None or not bool(torch.isfinite(loss)):
                    raise IntegrityError(f"SFT 검증 loss가 유한하지 않습니다: step={self.step}")
                target_count = int((labels[:, 1:] != -100).sum())
                weighted_loss += float(loss) * target_count
                target_total += target_count
                self.validation_batches_seen += 1
        self.model.train(was_training)
        if target_total == 0:
            raise IntegrityError("SFT heldout batch에 assistant 검증 token이 없습니다")
        return weighted_loss / target_total

    def run(self, *, stop_after_steps: int | None = None) -> dict[str, object]:
        if stop_after_steps is not None and stop_after_steps <= 0:
            raise ValueError("stop_after_steps는 양수여야 합니다")
        target_step = self.config.max_steps
        if stop_after_steps is not None:
            target_step = min(target_step, self.step + stop_after_steps)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.run_dir / "resolved-config.json", self.config.model_dump(mode="json"))
        write_json(
            self.run_dir / "data-manifest.json",
            {
                "schema_version": 1,
                "fingerprints": self.fingerprints,
                "train_file_sha256": self.train_data.file_sha256,
                "heldout_file_sha256": self.heldout_data.file_sha256,
                "licenses": sorted(set(self.train_data.licenses + self.heldout_data.licenses)),
                "base_checkpoint": self.base_checkpoint_provenance,
            },
        )
        last_loss = math.nan
        self.model.train()
        while self.step < target_step:
            self.optimizer.zero_grad(set_to_none=True)
            micro_batches = [
                self._next_batch(self.train_data, self.sampler)
                for _ in range(self.config.gradient_accumulation_steps)
            ]
            target_counts = [int((labels[:, 1:] != -100).sum()) for _, labels in micro_batches]
            total_targets = sum(target_counts)
            if total_targets == 0:
                raise IntegrityError("SFT accumulation batch에 assistant 학습 token이 없습니다")
            total_loss = 0.0
            for micro_step, ((inputs, labels), target_count) in enumerate(
                zip(micro_batches, target_counts, strict=True)
            ):
                self.micro_step = micro_step + 1
                with autocast_context(self.device, self.autocast_dtype):
                    loss = self.model(inputs, targets=labels).loss
                    if loss is None:
                        raise IntegrityError("SFT 모델이 학습 loss를 반환하지 않았습니다")
                    scaled_loss = loss * (target_count / total_targets)
                if not bool(torch.isfinite(loss)):
                    raise IntegrityError(f"SFT loss가 유한하지 않습니다: step={self.step}")
                self.scaler.scale(scaled_loss).backward()
                total_loss += float(loss.detach()) * target_count
            self.scaler.unscale_(self.optimizer)
            norm = torch.nn.utils.clip_grad_norm_(
                self.model.parameters(), self.config.gradient_clip_norm
            )
            if not bool(torch.isfinite(norm)):
                raise IntegrityError("SFT gradient norm이 유한하지 않습니다")
            lr = (
                self.config.optimizer.min_learning_rate
                if self.step >= self.scheduler_horizon
                else learning_rate(self.step, self.scheduler_horizon, self.config.optimizer)
            )
            for group in self.optimizer.param_groups:
                group["lr"] = lr
            self.scaler.step(self.optimizer)
            self.scaler.update()
            self.step += 1
            self.micro_step = 0
            last_loss = total_loss / total_targets
            if self.step % self.config.log_interval == 0:
                self._metric(
                    {
                        "event": "sft",
                        "step": self.step,
                        "loss": last_loss,
                        "learning_rate": lr,
                        "precision": self.precision,
                        "device": self.device.type,
                    }
                )
            if (
                self.step % self.config.validation_interval == 0
                or self.step == self.config.max_steps
            ):
                validation_loss = self.validate()
                improved = validation_loss < self.best_validation_loss
                self.best_validation_loss = min(self.best_validation_loss, validation_loss)
                self._metric(
                    {
                        "event": "validation",
                        "step": self.step,
                        "loss": validation_loss,
                        "perplexity": math.exp(min(validation_loss, 80.0)),
                    }
                )
                if improved:
                    self.save(best=True)
            if self.step % self.config.checkpoint_interval == 0:
                self.save()
        checkpoint = self.save()
        return {
            "step": self.step,
            "loss": last_loss,
            "best_validation_loss": self.best_validation_loss,
            "checkpoint": str(checkpoint),
        }


def train_sft(config: SFTConfig, *, resume: Path | None = None) -> dict[str, object]:
    trainer = SFTTrainer(config)
    if resume is not None:
        trainer.resume(resume)
    return trainer.run()


def _load_sft(
    config: SFTConfig, checkpoint: Path
) -> tuple[CausalLM, Any, ChatDataset, dict[str, str]]:
    trainer = SFTTrainer(config)
    trainer.resume(checkpoint)
    return (
        trainer.model.eval(),
        trainer.tokenizer,
        trainer.heldout_data,
        trainer.fingerprints,
    )


def _generated(
    model: CausalLM, tokenizer: Any, messages: tuple[Message, ...], config: SFTConfig
) -> tuple[list[int], str]:
    prompt = render_chat(messages, add_generation_prompt=True)
    ids = tokenizer.encode(prompt).ids
    if not ids or len(ids) >= config.model.max_seq_len:
        raise IntegrityError("chat prompt가 비었거나 문맥 길이를 초과합니다")
    device = next(model.parameters()).device
    output = model.generate(
        torch.tensor([ids], dtype=torch.long, device=device),
        GenerationConfig(
            max_new_tokens=config.max_new_tokens, temperature=0, eos_id=SPECIAL_IDS["<eos>"]
        ),
    )[0, len(ids) :].tolist()
    return output, tokenizer.decode(output, skip_special_tokens=True)


def generate_chat(config: SFTConfig, checkpoint: Path, prompt: str) -> dict[str, object]:
    model, tokenizer, _, fingerprints = _load_sft(config, checkpoint)
    generated, text = _generated(model, tokenizer, (Message(role="user", content=prompt),), config)
    return {
        "prompt": prompt,
        "response": text,
        "token_ids": generated,
        "eos_reached": SPECIAL_IDS["<eos>"] in generated,
        "fingerprints": fingerprints,
    }


def evaluate_chat(config: SFTConfig, checkpoint: Path) -> dict[str, object]:
    model, tokenizer, heldout, fingerprints = _load_sft(config, checkpoint)
    examples = list(heldout.examples[: config.max_eval_examples])
    losses: list[float] = []
    rows: list[dict[str, object]] = []
    unsafe = 0
    repetition_failures = 0
    eos_failures = 0
    for example in examples:
        inputs, labels = _batch(tokenizer, [example], config.sequence_length)
        device = next(model.parameters()).device
        with torch.no_grad():
            loss = model(inputs.to(device), targets=labels.to(device)).loss
        assert loss is not None
        losses.append(float(loss))
        prompt_messages = example.messages[:-1]
        generated, text = _generated(model, tokenizer, prompt_messages, config)
        repetition = 0.0 if not generated else 1.0 - len(set(generated)) / len(generated)
        unsafe_hits = [pattern for pattern in config.unsafe_patterns if pattern in text]
        unsafe += bool(unsafe_hits)
        repetition_failures += repetition > config.repetition_threshold
        eos_failures += SPECIAL_IDS["<eos>"] not in generated
        rows.append(
            {
                "id": example.id,
                "response": text,
                "loss": float(loss),
                "repetition_rate": repetition,
                "unsafe_hits": unsafe_hits,
                "eos_reached": SPECIAL_IDS["<eos>"] in generated,
            }
        )
    payload: dict[str, object] = {
        "schema_version": 1,
        "kind": "heldout-chat-evaluation",
        "examples": len(rows),
        "assistant_nll": sum(losses) / len(losses),
        "perplexity": math.exp(min(sum(losses) / len(losses), 80.0)),
        "gates": {
            "safety": "통과" if unsafe == 0 else "실패",
            "repetition": "통과" if repetition_failures == 0 else "실패",
            "eos": "통과" if eos_failures == 0 else "실패",
        },
        "rows": rows,
        "fingerprints": fingerprints,
    }
    payload["fingerprint"] = fingerprint(payload)
    write_json(config.run_dir / "heldout-evaluation.json", payload)
    return payload
