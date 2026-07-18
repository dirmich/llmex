"""Decoder-only causal language model, loss와 생성."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from typing import cast

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from llmex.config import ModelConfig
from llmex.model.attention import KVCache
from llmex.model.block import DecoderBlock
from llmex.model.norm import RMSNorm


@dataclass(frozen=True)
class CausalLMOutput:
    logits: Tensor
    loss: Tensor | None
    cache: tuple[KVCache, ...] | None


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens: int = 20
    temperature: float = 1.0
    top_k: int | None = None
    top_p: float = 1.0
    eos_id: int | None = None
    use_cache: bool = True
    repetition_penalty: float = 1.0


class CausalLM(nn.Module):
    """tied embedding을 사용하는 Pre-Norm causal LM."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.dropout = nn.Dropout(config.dropout)
        self.blocks = nn.ModuleList(DecoderBlock(config) for _ in range(config.n_layers))
        self.final_norm = RMSNorm(config.d_model, config.norm_eps)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        self.lm_head.weight = self.token_embedding.weight
        self.apply(self._initialize)
        scale = 1.0 / (2.0 * config.n_layers) ** 0.5
        for untyped_block in self.blocks:
            block = cast(DecoderBlock, untyped_block)
            block.attention.out_proj.weight.data.mul_(scale)
            block.ffn.down.weight.data.mul_(scale)

    def _initialize(self, module: nn.Module) -> None:
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=self.config.init_std)

    def forward(
        self,
        input_ids: Tensor,
        *,
        targets: Tensor | None = None,
        ignore_index: int = -100,
        cache: tuple[KVCache, ...] | None = None,
        use_cache: bool = False,
        implementation: str = "sdpa",
    ) -> CausalLMOutput:
        if input_ids.ndim != 2 or input_ids.dtype != torch.long:
            raise ValueError("input_ids는 int64[B,T]여야 합니다")
        if targets is not None and targets.shape != input_ids.shape:
            raise ValueError("targets shape은 input_ids와 같아야 합니다")
        if targets is not None and input_ids.size(1) < 2:
            raise ValueError("shifted loss 계산에는 두 개 이상의 token이 필요합니다")
        if cache is not None and len(cache) != len(self.blocks):
            raise ValueError("KV cache layer 수가 모델과 다릅니다")
        past = 0 if cache is None else cache[0][0].size(-2)
        if input_ids.size(1) < 1 or past + input_ids.size(1) > self.config.max_seq_len:
            raise ValueError("입력 길이가 max_seq_len 범위를 벗어났습니다")
        hidden = self.dropout(self.token_embedding(input_ids))
        presents: list[KVCache] = []
        for index, untyped_block in enumerate(self.blocks):
            block = cast(DecoderBlock, untyped_block)
            layer_cache = None if cache is None else cache[index]
            hidden, present = block(
                hidden, cache=layer_cache, use_cache=use_cache, implementation=implementation
            )
            if present is not None:
                presents.append(present)
        logits = self.lm_head(self.final_norm(hidden))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(
                logits[:, :-1].contiguous().view(-1, self.config.vocab_size),
                targets[:, 1:].contiguous().view(-1),
                ignore_index=ignore_index,
            )
        return CausalLMOutput(logits, loss, tuple(presents) if use_cache else None)

    @torch.no_grad()
    def generate(
        self,
        input_ids: Tensor,
        generation: GenerationConfig,
        *,
        generator: torch.Generator | None = None,
    ) -> Tensor:
        if generation.max_new_tokens < 0 or generation.temperature < 0:
            raise ValueError("생성 길이와 temperature는 음수일 수 없습니다")
        if generation.top_k is not None and generation.top_k < 1:
            raise ValueError("top_k는 1 이상이어야 합니다")
        if not 0.0 < generation.top_p <= 1.0:
            raise ValueError("top_p는 0 초과 1 이하여야 합니다")
        if generation.repetition_penalty <= 0.0:
            raise ValueError("repetition_penalty는 0보다 커야 합니다")
        if generation.eos_id is not None and not 0 <= generation.eos_id < self.config.vocab_size:
            raise ValueError("eos_id가 vocab 범위를 벗어났습니다")
        if input_ids.ndim != 2 or input_ids.dtype != torch.long or input_ids.size(1) < 1:
            raise ValueError("prompt는 비어 있지 않은 int64[B,T]여야 합니다")
        result = input_ids
        cache: tuple[KVCache, ...] | None = None
        current = input_ids
        finished = torch.zeros(input_ids.size(0), dtype=torch.bool, device=input_ids.device)
        was_training = self.training
        self.eval()
        try:
            for _ in range(generation.max_new_tokens):
                if result.size(1) >= self.config.max_seq_len:
                    break
                output = self(current, cache=cache, use_cache=generation.use_cache)
                cache = output.cache
                scores = output.logits[:, -1]
                if generation.repetition_penalty != 1.0:
                    seen = torch.zeros_like(scores, dtype=torch.bool)
                    seen.scatter_(1, result, True)
                    adjusted = torch.where(
                        scores < 0,
                        scores * generation.repetition_penalty,
                        scores / generation.repetition_penalty,
                    )
                    scores = torch.where(seen, adjusted, scores)
                # 반복 4-gram은 대화 모델의 무한 루프를 조기에 차단한다.
                if result.size(1) >= 4:
                    for batch_index in range(result.size(0)):
                        history = result[batch_index].tolist()
                        prefix = tuple(history[-3:])
                        banned = {
                            history[i + 3]
                            for i in range(len(history) - 3)
                            if tuple(history[i : i + 3]) == prefix
                        }
                        if banned:
                            scores[batch_index, list(banned)] = float("-inf")
                if generation.temperature == 0:
                    next_token = scores.argmax(dim=-1, keepdim=True)
                else:
                    scores = scores / generation.temperature
                    if generation.top_k is not None:
                        k = min(generation.top_k, scores.size(-1))
                        threshold = torch.topk(scores, k).values[:, -1, None]
                        scores = scores.masked_fill(scores < threshold, -torch.inf)
                    if generation.top_p < 1.0:
                        sorted_scores, sorted_indices = torch.sort(scores, descending=True)
                        cumulative = torch.softmax(sorted_scores, dim=-1).cumsum(dim=-1)
                        remove = (
                            cumulative - torch.softmax(sorted_scores, dim=-1) > generation.top_p
                        )
                        sorted_scores = sorted_scores.masked_fill(remove, -torch.inf)
                        scores = torch.full_like(scores, -torch.inf).scatter(
                            1, sorted_indices, sorted_scores
                        )
                    next_token = torch.multinomial(
                        torch.softmax(scores, dim=-1), 1, generator=generator
                    )
                if generation.eos_id is not None:
                    next_token = torch.where(
                        finished[:, None],
                        torch.full_like(next_token, generation.eos_id),
                        next_token,
                    )
                result = torch.cat((result, next_token), dim=1)
                current = next_token if generation.use_cache else result
                if generation.eos_id is not None:
                    finished |= next_token.squeeze(1) == generation.eos_id
                    if bool(torch.all(finished)):
                        break
        finally:
            self.train(was_training)
        if generation.eos_id is not None:
            # 생성 한도에 도달해도 응답은 항상 명시적 EOS로 닫는다.
            result[:, -1] = torch.where(
                result[:, -1] == generation.eos_id,
                result[:, -1],
                torch.full_like(result[:, -1], generation.eos_id),
            )
        return result

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def memory_estimate(self, *, bytes_per_parameter: int = 4) -> dict[str, int]:
        parameters = self.parameter_count()
        return {
            "parameters": parameters,
            "weights_bytes": parameters * bytes_per_parameter,
            "training_bytes_adamw": parameters * (bytes_per_parameter + 4 + 8),
        }
