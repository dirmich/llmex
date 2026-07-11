"""Pre-Norm decoder block과 SwiGLU."""

from torch import Tensor, nn
from torch.nn import functional as F

from llmex.config import ModelConfig
from llmex.model.attention import GroupedQueryAttention, KVCache
from llmex.model.norm import RMSNorm


class SwiGLU(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.gate = nn.Linear(config.d_model, config.ffn_hidden_size, bias=False)
        self.up = nn.Linear(config.d_model, config.ffn_hidden_size, bias=False)
        self.down = nn.Linear(config.ffn_hidden_size, config.d_model, bias=False)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, inputs: Tensor) -> Tensor:
        return self.dropout(self.down(F.silu(self.gate(inputs)) * self.up(inputs)))


class DecoderBlock(nn.Module):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.attention_norm = RMSNorm(config.d_model, config.norm_eps)
        self.attention = GroupedQueryAttention(config)
        self.ffn_norm = RMSNorm(config.d_model, config.norm_eps)
        self.ffn = SwiGLU(config)
        self.residual_dropout = nn.Dropout(config.dropout)

    def forward(
        self,
        inputs: Tensor,
        *,
        cache: KVCache | None = None,
        use_cache: bool = False,
        implementation: str = "sdpa",
    ) -> tuple[Tensor, KVCache | None]:
        attended, present = self.attention(
            self.attention_norm(inputs),
            cache=cache,
            use_cache=use_cache,
            implementation=implementation,
        )
        hidden = inputs + self.residual_dropout(attended)
        return hidden + self.ffn(self.ffn_norm(hidden)), present
