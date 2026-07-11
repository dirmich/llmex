"""원자적 checkpoint 저장, 포인터 갱신과 엄격한 상태 복구."""
# pyright: reportUnknownMemberType=false

import os
import random
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch

from llmex.errors import IntegrityError


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


def atomic_save(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("wb") as stream:
            torch.save(payload, stream)
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


def save_checkpoint(
    directory: Path,
    payload: dict[str, object],
    *,
    step: int,
    best: bool = False,
) -> Path:
    step_path = directory / f"step-{step:08d}.pt"
    atomic_save(step_path, payload)
    atomic_save(directory / "latest.pt", payload)
    if best:
        atomic_save(directory / "best.pt", payload)
    return step_path


def load_checkpoint(path: Path, expected_fingerprints: dict[str, str]) -> dict[str, Any]:
    if not path.is_file():
        raise IntegrityError(f"checkpoint가 없습니다: {path}")
    try:
        value = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise IntegrityError(f"checkpoint를 읽을 수 없습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrityError("지원하지 않는 checkpoint schema입니다")
    checkpoint = cast(dict[str, Any], value)
    if checkpoint.get("schema_version") != 1:
        raise IntegrityError("지원하지 않는 checkpoint schema입니다")
    actual = checkpoint.get("fingerprints")
    if actual != expected_fingerprints:
        raise IntegrityError(
            "checkpoint fingerprint가 현재 입력과 다릅니다: "
            f"기대={expected_fingerprints}, 실제={actual}"
        )
    required = {"model", "optimizer", "scheduler", "scaler", "sampler", "rng", "step"}
    if not required.issubset(checkpoint):
        raise IntegrityError(
            f"checkpoint 필수 상태가 없습니다: {sorted(required - checkpoint.keys())}"
        )
    return checkpoint
