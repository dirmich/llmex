"""AdamW parameter group과 warmup+cosine learning-rate schedule."""

import math

from torch import nn

from llmex.config import OptimizerConfig


def parameter_groups(model: nn.Module, weight_decay: float) -> list[dict[str, object]]:
    decay: list[nn.Parameter] = []
    no_decay: list[nn.Parameter] = []
    seen: set[int] = set()
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad or id(parameter) in seen:
            continue
        seen.add(id(parameter))
        (
            decay if parameter.ndim >= 2 and not name.endswith("embedding.weight") else no_decay
        ).append(parameter)
    return [
        {"params": decay, "weight_decay": weight_decay},
        {"params": no_decay, "weight_decay": 0.0},
    ]


def learning_rate(step: int, max_steps: int, config: OptimizerConfig) -> float:
    """step은 완료할 optimizer update의 0-based index다."""
    if step < config.warmup_steps:
        return config.learning_rate * (step + 1) / max(1, config.warmup_steps)
    if max_steps <= config.warmup_steps:
        return config.min_learning_rate
    progress = (step - config.warmup_steps) / max(1, max_steps - config.warmup_steps - 1)
    progress = min(1.0, max(0.0, progress))
    ratio = 0.5 * (1.0 + math.cos(math.pi * progress))
    return config.min_learning_rate + ratio * (config.learning_rate - config.min_learning_rate)
