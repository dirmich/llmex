"""학습 엔진이 공유하는 장치, 정밀도, 난수와 autocast 설정."""
# pyright: reportUnknownMemberType=false

import random
from contextlib import AbstractContextManager, nullcontext
from typing import Any

import numpy as np
import torch

from llmex.errors import ConfigError


def resolve_device(name: str) -> torch.device:
    """요청한 학습 장치를 확인하고 auto를 실제 장치로 확정한다."""

    if name == "auto":
        name = (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
    if name == "cuda" and not torch.cuda.is_available():
        raise ConfigError("CUDA를 사용할 수 없습니다")
    if name == "mps" and not torch.backends.mps.is_available():
        raise ConfigError("MPS를 사용할 수 없습니다")
    return torch.device(name)


def resolve_precision(requested: str, device: torch.device) -> tuple[str, torch.dtype | None, bool]:
    """요청 정밀도를 실제 정밀도, autocast dtype, scaler 사용 여부로 확정한다."""

    if requested == "auto":
        if device.type == "cuda" and torch.cuda.is_bf16_supported():
            requested = "bf16"
        elif device.type == "cuda":
            requested = "fp16"
        else:
            requested = "fp32"
    if requested == "bf16":
        supported = device.type == "cuda" and torch.cuda.is_bf16_supported()
        supported |= device.type == "cpu"
        if not supported:
            raise ConfigError("선택한 장치가 bf16 autocast를 지원하지 않습니다")
        return requested, torch.bfloat16, False
    if requested == "fp16":
        if device.type != "cuda":
            raise ConfigError("fp16 학습은 CUDA에서만 지원합니다")
        return requested, torch.float16, True
    return "fp32", None, False


def seed_everything(seed: int, deterministic: bool) -> None:
    """Python, NumPy, PyTorch 난수와 결정적 연산 정책을 함께 설정한다."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(deterministic)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.benchmark = False


def autocast_context(
    device: torch.device, dtype: torch.dtype | None
) -> AbstractContextManager[Any]:
    """fp32에는 빈 context를, 혼합 정밀도에는 torch autocast를 반환한다."""

    if dtype is None:
        return nullcontext()
    return torch.autocast(device.type, dtype=dtype)
