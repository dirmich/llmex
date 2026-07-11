"""RoPE GQA causal self-attention."""

import math
from typing import TypeAlias

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from llmex.config import ModelConfig
from llmex.model.rope import RotaryEmbedding

KVCache: TypeAlias = tuple[Tensor, Tensor]


class GroupedQueryAttention(nn.Module):
    """MHA를 n_kv_heads == n_heads인 특수 경우로 포함하는 GQA."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.n_heads = config.n_heads
        self.n_kv_heads = config.n_kv_heads
        self.head_dim = config.d_model // config.n_heads
        self.groups = config.n_heads // config.n_kv_heads
        self.max_seq_len = config.max_seq_len
        self.dropout = config.dropout
        self.q_proj = nn.Linear(config.d_model, config.n_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(config.d_model, config.n_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(config.d_model, config.n_kv_heads * self.head_dim, bias=False)
        self.out_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.rope = RotaryEmbedding(self.head_dim, config.max_seq_len, config.rope_theta)

    def _shape(self, value: Tensor, heads: int) -> Tensor:
        batch, length, _ = value.shape
        return value.view(batch, length, heads, self.head_dim).transpose(1, 2)

    def forward(
        self,
        inputs: Tensor,
        *,
        cache: KVCache | None = None,
        use_cache: bool = False,
        implementation: str = "sdpa",
    ) -> tuple[Tensor, KVCache | None]:
        batch, length, _ = inputs.shape
        past_length = 0 if cache is None else cache[0].size(-2)
        if past_length + length > self.max_seq_len:
            raise ValueError("attention 길이가 max_seq_len을 벗어났습니다")
        query = self.rope(self._shape(self.q_proj(inputs), self.n_heads), offset=past_length)
        key = self.rope(self._shape(self.k_proj(inputs), self.n_kv_heads), offset=past_length)
        value = self._shape(self.v_proj(inputs), self.n_kv_heads)
        if cache is not None:
            key = torch.cat((cache[0], key), dim=-2)
            value = torch.cat((cache[1], value), dim=-2)
        present = (key, value) if use_cache else None
        key = key.repeat_interleave(self.groups, dim=1)
        value = value.repeat_interleave(self.groups, dim=1)
        key_length = key.size(-2)
        query_positions = torch.arange(past_length, past_length + length, device=inputs.device)
        key_positions = torch.arange(key_length, device=inputs.device)
        allowed = key_positions[None, :] <= query_positions[:, None]
        if implementation == "sdpa":
            attended = F.scaled_dot_product_attention(
                query,
                key,
                value,
                attn_mask=allowed,
                dropout_p=self.dropout if self.training else 0.0,
            )
        elif implementation == "eager":
            scores = query @ key.transpose(-2, -1) / math.sqrt(self.head_dim)
            scores = scores.masked_fill(~allowed, torch.finfo(scores.dtype).min)
            probabilities = torch.softmax(scores.float(), dim=-1).to(dtype=scores.dtype)
            probabilities = F.dropout(probabilities, self.dropout, self.training)
            attended = probabilities @ value
        else:
            raise ValueError("attention 구현은 'sdpa' 또는 'eager'여야 합니다")
        merged = attended.transpose(1, 2).contiguous().view(batch, length, -1)
        return self.out_proj(merged), present
