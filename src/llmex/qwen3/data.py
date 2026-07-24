"""Qwen chat template 기반 assistant-only SFT tokenization."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from llmex.chat.data import ChatExample, Message
from llmex.errors import IntegrityError


class ChatTemplateTokenizer(Protocol):
    def apply_chat_template(
        self,
        conversation: Sequence[Mapping[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        enable_thinking: bool,
    ) -> list[int]: ...


@dataclass(frozen=True)
class Qwen3Features:
    input_ids: tuple[int, ...]
    attention_mask: tuple[int, ...]
    labels: tuple[int, ...]


def _chat(messages: Sequence[Message]) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in messages]


def _ids(
    tokenizer: ChatTemplateTokenizer,
    messages: Sequence[Message],
    *,
    generation_prompt: bool,
) -> list[int]:
    encoded = tokenizer.apply_chat_template(
        _chat(messages),
        tokenize=True,
        add_generation_prompt=generation_prompt,
        enable_thinking=False,
    )
    # Transformers returns BatchEncoding for recent tokenizers; normalize it
    # to the flat id list expected by the masking code.
    if hasattr(encoded, "input_ids"):
        return list(encoded.input_ids[0] if encoded.input_ids and isinstance(encoded.input_ids[0], list) else encoded.input_ids)
    return list(encoded)


def tokenize_assistant_only(
    tokenizer: ChatTemplateTokenizer,
    messages: Sequence[Message],
    *,
    max_length: int,
) -> Qwen3Features:
    """assistant 본문과 종료 token만 label에 남깁니다."""

    full_ids = _ids(tokenizer, messages, generation_prompt=False)
    labels = [-100] * len(full_ids)
    for index, message in enumerate(messages):
        if message.role != "assistant":
            continue
        prefix_ids = _ids(tokenizer, messages[:index], generation_prompt=True)
        through_ids = _ids(tokenizer, messages[: index + 1], generation_prompt=False)
        prefix_changed = through_ids[: len(prefix_ids)] != prefix_ids
        full_changed = full_ids[: len(through_ids)] != through_ids
        if prefix_changed or full_changed:
            encode = getattr(tokenizer, "__call__", None)
            if encode is None:
                raise IntegrityError("Qwen chat template prefix가 불안정하고 tokenizer 인코더가 없습니다")
            content_ids = encode(message.content, add_special_tokens=False)["input_ids"]
            start = next((pos for pos in range(len(full_ids) - len(content_ids) + 1)
                          if full_ids[pos : pos + len(content_ids)] == content_ids), None)
            if start is None:
                raise IntegrityError("assistant content token span을 찾을 수 없습니다")
            labels[start : start + len(content_ids)] = content_ids
            if start + len(content_ids) < len(full_ids):
                labels[start + len(content_ids)] = full_ids[start + len(content_ids)]
            continue
        labels[len(prefix_ids) : len(through_ids)] = through_ids[len(prefix_ids) :]
    if len(full_ids) > max_length:
        full_ids = full_ids[-max_length:]
        labels = labels[-max_length:]
    if not full_ids or all(label == -100 for label in labels):
        raise IntegrityError("truncation 뒤 assistant 학습 token이 없습니다")
    return Qwen3Features(tuple(full_ids), (1,) * len(full_ids), tuple(labels))


class Qwen3ChatDataset:
    """Transformers Trainer가 읽는 최소 map-style dataset."""

    def __init__(
        self,
        examples: Sequence[ChatExample],
        tokenizer: ChatTemplateTokenizer,
        *,
        max_length: int,
    ) -> None:
        self._features = tuple(
            tokenize_assistant_only(tokenizer, example.messages, max_length=max_length)
            for example in examples
        )

    def __len__(self) -> int:
        return len(self._features)

    def __getitem__(self, index: int) -> dict[str, list[int]]:
        item = self._features[index]
        return {
            "input_ids": list(item.input_ids),
            "attention_mask": list(item.attention_mask),
            "labels": list(item.labels),
        }


@dataclass(frozen=True)
class Qwen3DataCollator:
    """오른쪽 padding을 적용하고 pad label은 loss에서 제외합니다."""

    pad_token_id: int

    def __call__(self, features: Sequence[Mapping[str, Sequence[int]]]) -> dict[str, object]:
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - 기본 프로젝트 의존성
            raise RuntimeError("torch가 필요합니다") from exc
        width = max(len(item["input_ids"]) for item in features)
        input_ids: list[list[int]] = []
        attention_mask: list[list[int]] = []
        labels: list[list[int]] = []
        for item in features:
            padding = width - len(item["input_ids"])
            input_ids.append([*item["input_ids"], *([self.pad_token_id] * padding)])
            attention_mask.append([*item["attention_mask"], *([0] * padding)])
            labels.append([*item["labels"], *([-100] * padding)])
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }
