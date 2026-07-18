"""원자적 checkpoint 저장, 포인터 갱신과 엄격한 상태 복구."""
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

import hashlib
import io
import json
import math
import os
import random
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch

from llmex.config import TrainingConfig
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint
from llmex.model import CausalLM
from llmex.train.data import DeterministicBatchSampler, TokenShardDataset
from llmex.train.optim import parameter_groups

SFT_CHECKPOINT_REQUIRED_STATE = frozenset(
    {
        "model",
        "optimizer",
        "scheduler",
        "scaler",
        "sampler",
        "validation_sampler",
        "rng",
        "step",
        "micro_step",
        "precision",
        "best_validation_loss",
        "validation_batches_seen",
    }
)
TRAIN_CHECKPOINT_REQUIRED_STATE = frozenset(
    {"model", "optimizer", "scheduler", "scaler", "sampler", "validation_sampler", "rng", "step"}
)
# 기존 import 사용자를 위한 pretrain 계약 별칭이다.
CHECKPOINT_REQUIRED_STATE = TRAIN_CHECKPOINT_REQUIRED_STATE
# baseline-100m best.pt에서 관측한 PyTorch CUDA RNG byte-state의 정확한 크기다.
CHECKPOINT_CUDA_RNG_STATE_NUMEL = 16


@dataclass(frozen=True)
class _CheckpointSnapshot:
    checkpoint: dict[str, Any]
    size: int
    sha256: str


def rng_state() -> dict[str, object]:
    numpy_state = cast(tuple[str, np.ndarray[Any, Any], int, int, float], np.random.get_state())
    state: dict[str, object] = {
        "python": random.getstate(),
        "numpy": {
            "algorithm": numpy_state[0],
            "keys": torch.from_numpy(numpy_state[1].copy()),
            "position": numpy_state[2],
            "has_gauss": numpy_state[3],
            "cached_gaussian": numpy_state[4],
        },
        "torch_cpu": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()
    return state


def restore_rng_state(state: dict[str, object]) -> None:
    random.setstate(state["python"])  # type: ignore[arg-type]
    numpy_state = cast(dict[str, object], state["numpy"])
    keys = cast(torch.Tensor, numpy_state["keys"]).cpu().numpy().astype(np.uint32, copy=False)
    np.random.set_state(
        (
            str(numpy_state["algorithm"]),
            keys,
            int(cast(int, numpy_state["position"])),
            int(cast(int, numpy_state["has_gauss"])),
            float(cast(float, numpy_state["cached_gaussian"])),
        )
    )
    torch.set_rng_state(state["torch_cpu"])  # type: ignore[arg-type]
    if "torch_cuda" in state and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state["torch_cuda"])  # type: ignore[arg-type]


def _serialize_checkpoint(payload: dict[str, object]) -> bytes:
    stream = io.BytesIO()
    torch.save(payload, stream)
    return stream.getvalue()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_save(path: Path, payload: dict[str, object]) -> None:
    _atomic_write(path, _serialize_checkpoint(payload))


def save_checkpoint(
    directory: Path,
    payload: dict[str, object],
    *,
    step: int,
    best: bool = False,
) -> Path:
    data = _serialize_checkpoint(payload)
    step_path = directory / f"step-{step:08d}.pt"
    _atomic_write(step_path, data)
    _atomic_write(directory / "latest.pt", data)
    if best:
        _atomic_write(directory / "best.pt", data)
    return step_path


def _read_immutable_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise IntegrityError(f"checkpoint가 없습니다: {path}")
    for _ in range(3):
        try:
            with path.open("rb") as stream:
                before = os.fstat(stream.fileno())
                data = stream.read()
                after = os.fstat(stream.fileno())
        except OSError as exc:
            raise IntegrityError(f"checkpoint를 읽을 수 없습니다: {path}: {exc}") from exc
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
        if identity_before == identity_after and len(data) == before.st_size:
            return data
    raise IntegrityError(f"checkpoint immutable snapshot을 읽을 수 없습니다: {path}")


def _load_checkpoint_snapshot(
    path: Path,
    expected_fingerprints: dict[str, str],
    required_state: Collection[str],
    supported_schema_versions: Collection[int],
) -> _CheckpointSnapshot:
    data = _read_immutable_bytes(path)
    checkpoint = load_checkpoint_bytes(
        data,
        expected_fingerprints,
        supported_schema_versions=supported_schema_versions,
        required_state=required_state,
        source=str(path),
    )
    return _CheckpointSnapshot(checkpoint, len(data), hashlib.sha256(data).hexdigest())


def load_checkpoint_bytes(
    data: bytes,
    expected_fingerprints: dict[str, str],
    *,
    supported_schema_versions: Collection[int],
    required_state: Collection[str] = SFT_CHECKPOINT_REQUIRED_STATE,
    source: str = "checkpoint snapshot",
) -> dict[str, Any]:
    """이미 고정한 bytes를 재읽기 없이 안전 역직렬화하고 resume 계약으로 검증한다."""

    try:
        value = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
    except Exception as exc:
        raise IntegrityError(f"checkpoint를 읽을 수 없습니다: {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrityError("checkpoint가 매핑이 아닙니다")
    schema_version: object = cast(dict[object, object], value).get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version not in supported_schema_versions
    ):
        raise IntegrityError(
            "지원하지 않는 checkpoint schema입니다: "
            f"실제={schema_version}, 지원={sorted(supported_schema_versions)}"
        )
    checkpoint = cast(dict[str, Any], value)
    actual = checkpoint.get("fingerprints")
    if actual != expected_fingerprints:
        raise IntegrityError(
            "checkpoint fingerprint가 현재 입력과 다릅니다: "
            f"기대={expected_fingerprints}, 실제={actual}"
        )
    missing = set(required_state) - checkpoint.keys()
    if missing:
        raise IntegrityError(f"checkpoint 필수 상태가 없습니다: {sorted(missing)}")
    return checkpoint


def load_checkpoint(
    path: Path,
    expected_fingerprints: dict[str, str],
    *,
    supported_schema_versions: Collection[int],
    required_state: Collection[str] = SFT_CHECKPOINT_REQUIRED_STATE,
) -> dict[str, Any]:
    """호출자가 선언한 resume 상태 계약으로 checkpoint를 안전하게 읽는다."""

    return _load_checkpoint_snapshot(
        path, expected_fingerprints, required_state, supported_schema_versions
    ).checkpoint


def load_checkpoint_snapshot(
    path: Path,
    expected_fingerprints: dict[str, str],
    *,
    supported_schema_versions: Collection[int],
    required_state: Collection[str] = SFT_CHECKPOINT_REQUIRED_STATE,
) -> tuple[dict[str, Any], str]:
    """한 번 고정해 읽은 checkpoint payload와 그 bytes의 SHA-256을 반환한다."""

    snapshot = _load_checkpoint_snapshot(
        path, expected_fingerprints, required_state, supported_schema_versions
    )
    return snapshot.checkpoint, snapshot.sha256


def validate_model_state(
    raw_state: object, *, context: str = "checkpoint model"
) -> dict[str, torch.Tensor]:
    """모델 상태가 비어 있지 않은 str→finite Tensor 매핑인지 검증한다."""

    if not isinstance(raw_state, Mapping) or not raw_state:
        raise IntegrityError(f"{context} 상태가 비었거나 매핑이 아닙니다")
    state = cast(Mapping[object, object], raw_state)
    if not all(isinstance(name, str) for name in state):
        raise IntegrityError(f"{context} key가 문자열이 아닙니다")
    if not all(isinstance(value, torch.Tensor) for value in state.values()):
        raise IntegrityError(f"{context} 상태가 str→Tensor 매핑이 아닙니다")
    typed_state = cast(dict[str, torch.Tensor], dict(state))
    for name, value in typed_state.items():
        if not bool(torch.isfinite(value).all()):
            raise IntegrityError(f"{context}.{name} tensor에 NaN/Inf가 있습니다")
    return typed_state


def checkpoint_fingerprints(
    config: TrainingConfig, manifest: Mapping[str, Any] | None = None
) -> dict[str, str]:
    """학습 입력에서 checkpoint 호환성 fingerprint를 다시 계산한다."""

    try:
        if manifest is None:
            manifest = cast(
                dict[str, Any], json.loads(config.shards_manifest.read_text(encoding="utf-8"))
            )
        corpus = cast(Mapping[str, Any], manifest["corpus"])
        tokenizer = str(manifest["tokenizer_fingerprint"])
        shards = str(manifest["fingerprint"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IntegrityError(f"checkpoint fingerprint 입력을 읽을 수 없습니다: {exc}") from exc
    return {
        "config": fingerprint(config.model_dump(mode="json")),
        "corpus": fingerprint(corpus),
        "tokenizer": tokenizer,
        "model": fingerprint(config.model.model_dump(mode="json")),
        "shards": shards,
    }


def _require_int(value: object, location: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise IntegrityError(f"checkpoint {location} 값이 올바른 정수가 아닙니다")
    return value


def _require_finite(value: object, location: str) -> None:
    if isinstance(value, torch.Tensor):
        if not bool(torch.isfinite(value).all()):
            raise IntegrityError(f"checkpoint {location} tensor에 NaN/Inf가 있습니다")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise IntegrityError(f"checkpoint {location} 값에 NaN/Inf가 있습니다")
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            _require_finite(item, f"{location}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        for index, item in enumerate(sequence):
            _require_finite(item, f"{location}[{index}]")


def _audit_model_state(
    path: Path, checkpoint: dict[str, Any], expected: Mapping[str, torch.Tensor]
) -> dict[str, object]:
    raw_model = checkpoint.get("model")
    if not isinstance(raw_model, Mapping) or not raw_model:
        raise IntegrityError(f"checkpoint 모델 상태가 비었거나 매핑이 아닙니다: {path}")
    untyped_model = cast(Mapping[object, object], raw_model)
    if not all(isinstance(name, str) for name in untyped_model):
        raise IntegrityError(f"checkpoint 모델 key가 문자열이 아닙니다: {path}")
    model = cast(Mapping[str, object], untyped_model)
    actual_keys = set(model)
    expected_keys = set(expected)
    if actual_keys != expected_keys:
        raise IntegrityError(
            f"checkpoint 모델 key가 현재 모델과 다릅니다: {path}: "
            f"누락={sorted(expected_keys - actual_keys)}, "
            f"추가={sorted(actual_keys - expected_keys)}"
        )
    parameter_count = 0
    for name, expected_tensor in expected.items():
        value = model[name]
        if not isinstance(value, torch.Tensor):
            raise IntegrityError(f"checkpoint 모델 상태가 tensor 매핑이 아닙니다: {path}: {name}")
        if value.shape != expected_tensor.shape:
            raise IntegrityError(
                f"checkpoint 모델 tensor shape이 다릅니다: {path}: {name}: "
                f"기대={tuple(expected_tensor.shape)}, 실제={tuple(value.shape)}"
            )
        if value.dtype != expected_tensor.dtype:
            raise IntegrityError(
                f"checkpoint 모델 tensor dtype이 다릅니다: {path}: {name}: "
                f"기대={expected_tensor.dtype}, 실제={value.dtype}"
            )
        _require_finite(value, f"모델.{name}")
        parameter_count += value.numel()
    return {
        "tensor_count": len(expected),
        "parameter_count": parameter_count,
        "finite": True,
        "exact_state_dict": True,
    }


def _audit_optimizer_state(
    path: Path,
    raw_optimizer: object,
    model: CausalLM,
    config: TrainingConfig,
    step: int,
) -> dict[str, object]:
    if not isinstance(raw_optimizer, Mapping):
        raise IntegrityError(f"checkpoint optimizer 상태가 매핑이 아닙니다: {path}")
    optimizer = cast(Mapping[str, object], raw_optimizer)
    raw_state = optimizer.get("state")
    raw_groups = optimizer.get("param_groups")
    if not isinstance(raw_state, Mapping) or not isinstance(raw_groups, list):
        raise IntegrityError(f"checkpoint optimizer 구조가 올바르지 않습니다: {path}")
    state_by_id = cast(Mapping[object, object], raw_state)
    groups = cast(list[object], raw_groups)

    expected_groups = parameter_groups(model, config.optimizer.weight_decay)
    if len(groups) != len(expected_groups):
        raise IntegrityError(f"checkpoint optimizer parameter group 수가 다릅니다: {path}")
    parameter_by_id: dict[int, torch.Tensor] = {}
    expected_ids: list[int] = []
    next_id = 0
    for group_index, (raw_group, expected_group) in enumerate(
        zip(groups, expected_groups, strict=True)
    ):
        if not isinstance(raw_group, Mapping) or not isinstance(raw_group.get("params"), list):
            raise IntegrityError(f"checkpoint optimizer parameter group이 손상되었습니다: {path}")
        actual_ids = cast(list[object], raw_group["params"])
        expected_parameters = cast(list[torch.Tensor], expected_group["params"])
        group_ids = list(range(next_id, next_id + len(expected_parameters)))
        if actual_ids != group_ids:
            raise IntegrityError(
                f"checkpoint optimizer parameter id가 다릅니다: {path}: group={group_index}"
            )
        for parameter_id, parameter in zip(group_ids, expected_parameters, strict=True):
            parameter_by_id[parameter_id] = parameter
        expected_ids.extend(group_ids)
        next_id += len(group_ids)
        required_group = {"lr", "betas", "eps", "weight_decay", "params"}
        if not required_group.issubset(raw_group):
            raise IntegrityError(f"checkpoint optimizer parameter group 필수 값이 없습니다: {path}")
        expected_decay = float(cast(float, expected_group["weight_decay"]))
        if raw_group["weight_decay"] != expected_decay:
            raise IntegrityError(f"checkpoint optimizer weight_decay가 다릅니다: {path}")
        if raw_group["betas"] != (config.optimizer.beta1, config.optimizer.beta2):
            raise IntegrityError(f"checkpoint optimizer betas가 다릅니다: {path}")
        if raw_group["eps"] != config.optimizer.eps:
            raise IntegrityError(f"checkpoint optimizer eps가 다릅니다: {path}")
        _require_finite(raw_group, f"optimizer.param_groups[{group_index}]")

    if set(state_by_id) != set(expected_ids):
        raise IntegrityError(f"checkpoint optimizer parameter 상태 key가 다릅니다: {path}")
    for parameter_id in expected_ids:
        raw_item = state_by_id[parameter_id]
        if not isinstance(raw_item, Mapping):
            raise IntegrityError(f"checkpoint optimizer parameter 상태가 손상되었습니다: {path}")
        item = cast(Mapping[str, object], raw_item)
        if not {"step", "exp_avg", "exp_avg_sq"}.issubset(item):
            raise IntegrityError(f"checkpoint optimizer parameter 필수 상태가 없습니다: {path}")
        parameter = parameter_by_id[parameter_id]
        for key in ("exp_avg", "exp_avg_sq"):
            tensor = item[key]
            if (
                not isinstance(tensor, torch.Tensor)
                or tensor.shape != parameter.shape
                or tensor.dtype != parameter.dtype
            ):
                raise IntegrityError(
                    f"checkpoint optimizer {key} shape/dtype이 다릅니다: {path}: {parameter_id}"
                )
        optimizer_step = item["step"]
        if (
            not isinstance(optimizer_step, torch.Tensor)
            or optimizer_step.numel() != 1
            or float(optimizer_step) != step
        ):
            raise IntegrityError(f"checkpoint optimizer step이 checkpoint step과 다릅니다: {path}")
        _require_finite(item, f"optimizer.state[{parameter_id}]")
    return {"parameter_count": len(expected_ids), "finite": True, "resume_state": True}


def _expected_sampler_position(size: int, batch_size: int, batches: int) -> tuple[int, int]:
    batches_per_epoch = size // batch_size
    if batches_per_epoch < 1:
        raise IntegrityError("sampler dataset 크기가 batch_size보다 작습니다")
    if batches == 0:
        return 0, 0
    return (batches - 1) // batches_per_epoch, ((batches - 1) % batches_per_epoch + 1) * batch_size


def _audit_sampler_state(
    path: Path,
    raw_state: object,
    *,
    name: str,
    size: int,
    batch_size: int,
    seed: int,
    batches: int,
) -> dict[str, int]:
    if not isinstance(raw_state, dict) or set(raw_state) != {"seed", "epoch", "cursor"}:
        raise IntegrityError(f"checkpoint {name} sampler 구조가 올바르지 않습니다: {path}")
    state = cast(dict[str, object], raw_state)
    actual_seed = _require_int(state["seed"], f"{name} sampler seed")
    epoch = _require_int(state["epoch"], f"{name} sampler epoch")
    cursor = _require_int(state["cursor"], f"{name} sampler cursor")
    if actual_seed != seed:
        raise IntegrityError(f"checkpoint {name} sampler seed가 다릅니다: {path}")
    expected_epoch, expected_cursor = _expected_sampler_position(size, batch_size, batches)
    if (epoch, cursor) != (expected_epoch, expected_cursor):
        raise IntegrityError(
            f"checkpoint {name} sampler 진행 상태가 step과 다릅니다: {path}: "
            f"기대={(expected_epoch, expected_cursor)}, 실제={(epoch, cursor)}"
        )
    sampler = DeterministicBatchSampler(size, batch_size, seed)
    sampler.load_state_dict(cast(dict[str, int], raw_state))
    return {"seed": seed, "epoch": epoch, "cursor": cursor}


def _audit_rng_state(path: Path, raw_rng: object) -> dict[str, object]:
    if not isinstance(raw_rng, dict) or not {"python", "numpy", "torch_cpu"}.issubset(raw_rng):
        raise IntegrityError(f"checkpoint RNG 구조가 올바르지 않습니다: {path}")
    rng = cast(dict[str, object], raw_rng)
    try:
        python_rng = random.Random()
        python_rng.setstate(rng["python"])  # type: ignore[arg-type]
        numpy_state = cast(dict[str, object], rng["numpy"])
        if set(numpy_state) != {
            "algorithm",
            "keys",
            "position",
            "has_gauss",
            "cached_gaussian",
        }:
            raise ValueError("numpy RNG key")
        keys = numpy_state["keys"]
        if not isinstance(keys, torch.Tensor) or keys.dtype != torch.uint32 or keys.shape != (624,):
            raise ValueError("numpy RNG keys")
        numpy_rng = np.random.RandomState()
        numpy_rng.set_state(
            (
                str(numpy_state["algorithm"]),
                keys.cpu().numpy().astype(np.uint32, copy=False),
                _require_int(numpy_state["position"], "numpy RNG position"),
                _require_int(numpy_state["has_gauss"], "numpy RNG has_gauss"),
                float(cast(float, numpy_state["cached_gaussian"])),
            )
        )
        torch_cpu = rng["torch_cpu"]
        if (
            not isinstance(torch_cpu, torch.Tensor)
            or torch_cpu.dtype != torch.uint8
            or torch_cpu.ndim != 1
            or torch_cpu.numel() == 0
        ):
            raise ValueError("torch CPU RNG")
        torch.Generator(device="cpu").set_state(torch_cpu)
        has_valid_cuda_states = False
        if "torch_cuda" in rng:
            raw_cuda_states = rng["torch_cuda"]
            if not isinstance(raw_cuda_states, list) or not raw_cuda_states:
                raise ValueError("torch CUDA RNG")
            typed_cuda_states = cast(list[object], raw_cuda_states)
            for state in typed_cuda_states:
                if (
                    not isinstance(state, torch.Tensor)
                    or state.dtype != torch.uint8
                    or state.ndim != 1
                    or state.numel() != CHECKPOINT_CUDA_RNG_STATE_NUMEL
                ):
                    raise ValueError("torch CUDA RNG state")
            has_valid_cuda_states = True
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                if len(typed_cuda_states) != device_count:
                    raise ValueError(
                        "torch CUDA RNG state count: "
                        f"expected={device_count}, actual={len(typed_cuda_states)}"
                    )
                for index, state in enumerate(typed_cuda_states):
                    torch.Generator(device=f"cuda:{index}").set_state(cast(torch.Tensor, state))
        _require_finite(rng, "RNG")
    except IntegrityError:
        raise
    except Exception as exc:
        raise IntegrityError(f"checkpoint RNG 상태를 복구할 수 없습니다: {path}: {exc}") from exc
    return {
        "python": True,
        "numpy": True,
        "torch_cpu": True,
        "torch_cuda": has_valid_cuda_states,
    }


def _audit_scaler_state(path: Path, checkpoint: dict[str, Any]) -> dict[str, object]:
    try:
        raw_scaler = checkpoint["scaler"]
        if not isinstance(raw_scaler, dict):
            raise ValueError("scaler state is not a mapping")
        scaler = cast(dict[str, object], raw_scaler)
        precision = checkpoint.get("precision")
        if precision == "fp16":
            required = {
                "scale",
                "growth_factor",
                "backoff_factor",
                "growth_interval",
                "_growth_tracker",
            }
            if set(scaler) != required:
                raise ValueError("fp16 scaler state structure is invalid")

            numeric_values: dict[str, float] = {}
            for field in ("scale", "growth_factor", "backoff_factor"):
                value = scaler[field]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"scaler {field} is not numeric")
                numeric_values[field] = float(value)
            if not all(math.isfinite(value) for value in numeric_values.values()):
                raise ValueError("fp16 scaler contains a non-finite value")
            if numeric_values["scale"] <= 0:
                raise ValueError("scaler scale must be positive")
            if numeric_values["growth_factor"] <= 1:
                raise ValueError("scaler growth_factor must be greater than one")
            if not 0 < numeric_values["backoff_factor"] < 1:
                raise ValueError("scaler backoff_factor must be between zero and one")

            growth_interval = scaler["growth_interval"]
            growth_tracker = scaler["_growth_tracker"]
            if (
                isinstance(growth_interval, bool)
                or not isinstance(growth_interval, int)
                or growth_interval <= 0
            ):
                raise ValueError("scaler growth_interval must be a positive integer")
            if (
                isinstance(growth_tracker, bool)
                or not isinstance(growth_tracker, int)
                or growth_tracker < 0
            ):
                raise ValueError("scaler growth tracker must be a nonnegative integer")
        elif precision in {"fp32", "bf16"}:
            if scaler:
                raise ValueError("disabled scaler state is not empty")
        else:
            raise ValueError("checkpoint precision state is invalid")
        _require_finite(scaler, "scaler")
    except IntegrityError:
        raise
    except Exception as exc:
        raise IntegrityError(f"checkpoint scaler 상태를 복구할 수 없습니다: {path}: {exc}") from exc
    return {"enabled": precision == "fp16", "finite": True}


def audit_checkpoints(config: TrainingConfig) -> dict[str, object]:
    """완료 step/latest/best checkpoint를 수정 없이 재현 가능하게 감사한다."""

    expected_fingerprints = checkpoint_fingerprints(config)
    model = CausalLM(config.model)
    expected_model = model.state_dict()
    train_data = TokenShardDataset(config.shards_manifest, "train", config.sequence_length)
    validation_data = TokenShardDataset(
        config.shards_manifest, "validation", config.sequence_length
    )
    checkpoint_dir = config.run_dir / "checkpoints"
    targets = (
        ("step", checkpoint_dir / f"step-{config.max_steps:08d}.pt"),
        ("latest", checkpoint_dir / "latest.pt"),
        ("best", checkpoint_dir / "best.pt"),
    )
    results: dict[str, dict[str, object]] = {}
    for role, path in targets:
        if not path.is_file():
            raise IntegrityError(f"{role} checkpoint가 없습니다: {path}")
        snapshot = _load_checkpoint_snapshot(
            path,
            expected_fingerprints,
            TRAIN_CHECKPOINT_REQUIRED_STATE,
            {1},
        )
        checkpoint = snapshot.checkpoint
        step = _require_int(checkpoint["step"], "step")
        if role in {"step", "latest"} and step != config.max_steps:
            raise IntegrityError(
                f"완료 checkpoint step이 max_steps와 다릅니다: {path}: "
                f"기대={config.max_steps}, 실제={step}"
            )
        if role == "best" and not 0 <= step <= config.max_steps:
            raise IntegrityError(f"best checkpoint step 범위가 올바르지 않습니다: {path}: {step}")
        if checkpoint["scheduler"] != {"step": step}:
            raise IntegrityError(f"scheduler 상태가 checkpoint step과 다릅니다: {path}")
        best_loss = checkpoint.get("best_validation_loss")
        wall_seconds = checkpoint.get("accumulated_wall_seconds")
        if not isinstance(best_loss, (int, float)) or not math.isfinite(float(best_loss)):
            raise IntegrityError(f"checkpoint best validation loss가 유한하지 않습니다: {path}")
        if (
            not isinstance(wall_seconds, (int, float))
            or not math.isfinite(float(wall_seconds))
            or float(wall_seconds) < 0
        ):
            raise IntegrityError(f"checkpoint 누적 실행 시간이 올바르지 않습니다: {path}")

        validation_events = (step - 1) // config.validation_interval + 1 if step else 0
        results[role] = {
            "path": str(path),
            "bytes": snapshot.size,
            "sha256": snapshot.sha256,
            "schema_version": checkpoint["schema_version"],
            "step": step,
            "fingerprints": checkpoint["fingerprints"],
            "required_state": sorted(TRAIN_CHECKPOINT_REQUIRED_STATE),
            "model": _audit_model_state(path, checkpoint, expected_model),
            "optimizer": _audit_optimizer_state(path, checkpoint["optimizer"], model, config, step),
            "scaler": _audit_scaler_state(path, checkpoint),
            "sampler": _audit_sampler_state(
                path,
                checkpoint["sampler"],
                name="train",
                size=train_data.window_count,
                batch_size=config.micro_batch_size,
                seed=config.seed,
                batches=step * config.gradient_accumulation_steps,
            ),
            "validation_sampler": _audit_sampler_state(
                path,
                checkpoint["validation_sampler"],
                name="validation",
                size=validation_data.window_count,
                batch_size=config.micro_batch_size,
                seed=config.seed + 1_000_003,
                batches=validation_events * config.validation_batches,
            ),
            "rng": _audit_rng_state(path, checkpoint["rng"]),
        }
    if (
        results["step"]["sha256"] != results["latest"]["sha256"]
        or results["step"]["bytes"] != results["latest"]["bytes"]
    ):
        raise IntegrityError("완료 step/latest checkpoint가 동일 immutable snapshot이 아닙니다")
    return {
        "schema_version": 1,
        "status": "통과",
        "completed_step": config.max_steps,
        "expected_fingerprints": expected_fingerprints,
        "checkpoints": results,
    }
