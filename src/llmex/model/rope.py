"""Rotary positional embedding과 device/dtype별 지연 cache."""

import torch
from torch import Tensor, nn


class RotaryEmbedding(nn.Module):
    """인접한 두 좌표를 회전하는 RoPE를 제공한다."""

    def __init__(self, head_dim: int, max_seq_len: int, theta: float = 10000.0) -> None:
        super().__init__()
        if head_dim % 2:
            raise ValueError("RoPE head 차원은 짝수여야 합니다")
        inverse = 1.0 / (theta ** (torch.arange(0, head_dim, 2, dtype=torch.float32) / head_dim))
        self.max_seq_len = max_seq_len
        self.inverse_frequency: Tensor
        self.register_buffer("inverse_frequency", inverse, persistent=False)
        self._cos_cached: Tensor | None = None
        self._sin_cached: Tensor | None = None

    def cos_sin(
        self, length: int, *, offset: int, device: torch.device, dtype: torch.dtype
    ) -> tuple[Tensor, Tensor]:
        if length < 1 or offset < 0 or offset + length > self.max_seq_len:
            raise ValueError("RoPE 위치 범위가 max_seq_len을 벗어났습니다")
        cached = self._cos_cached
        if cached is None or cached.device != device or cached.dtype != dtype:
            positions = torch.arange(self.max_seq_len, device=device, dtype=torch.float32)
            angles = torch.outer(positions, self.inverse_frequency.to(device=device))
            self._cos_cached = angles.cos().to(dtype=dtype)[None, None]
            self._sin_cached = angles.sin().to(dtype=dtype)[None, None]
        assert self._cos_cached is not None and self._sin_cached is not None
        return (
            self._cos_cached[:, :, offset : offset + length],
            self._sin_cached[:, :, offset : offset + length],
        )

    def forward(self, inputs: Tensor, *, offset: int = 0) -> Tensor:
        cos, sin = self.cos_sin(
            inputs.size(-2), offset=offset, device=inputs.device, dtype=inputs.dtype
        )
        even, odd = inputs[..., 0::2], inputs[..., 1::2]
        return torch.stack((even * cos - odd * sin, even * sin + odd * cos), dim=-1).flatten(-2)
