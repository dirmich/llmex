"""Root mean square 정규화."""

import torch
from torch import Tensor, nn


class RMSNorm(nn.Module):
    """마지막 차원을 float32로 정규화하고 입력 dtype으로 복원한다."""

    def __init__(self, size: int, eps: float = 1e-5) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(size))

    def forward(self, inputs: Tensor) -> Tensor:
        normalized = inputs.float() * torch.rsqrt(
            inputs.float().square().mean(dim=-1, keepdim=True) + self.eps
        )
        return normalized.to(dtype=inputs.dtype) * self.weight
