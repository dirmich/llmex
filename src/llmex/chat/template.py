"""고정 chat template와 assistant-only SFT label 생성."""

from dataclasses import dataclass

from tokenizers import Tokenizer

from llmex.chat.data import Message
from llmex.errors import IntegrityError
from llmex.tokenizer.core import SPECIAL_IDS

ROLE_PREFIX = {"system": "<|system|>\n", "user": "<|user|>\n", "assistant": "<|assistant|>\n"}


@dataclass(frozen=True)
class TokenizedChat:
    input_ids: tuple[int, ...]
    labels: tuple[int, ...]


def render_chat(messages: tuple[Message, ...], *, add_generation_prompt: bool = False) -> str:
    text = "".join(f"{ROLE_PREFIX[item.role]}{item.content}\n" for item in messages)
    if add_generation_prompt:
        text += ROLE_PREFIX["assistant"]
    return text


def tokenize_chat(
    tokenizer: Tokenizer, messages: tuple[Message, ...], *, max_length: int
) -> TokenizedChat:
    ids = [SPECIAL_IDS["<bos>"]]
    labels = [-100]
    for message in messages:
        prefix = tokenizer.encode(ROLE_PREFIX[message.role]).ids
        content = tokenizer.encode(message.content + "\n").ids
        ids.extend(prefix)
        labels.extend([-100] * len(prefix))
        ids.extend(content)
        labels.extend(content if message.role == "assistant" else [-100] * len(content))
        if message.role == "assistant":
            ids.append(SPECIAL_IDS["<eos>"])
            labels.append(SPECIAL_IDS["<eos>"])
    if len(ids) > max_length:
        ids, labels = ids[-max_length:], labels[-max_length:]
    if len(ids) < 2 or all(label == -100 for label in labels[1:]):
        raise IntegrityError("truncation 뒤 assistant 학습 token이 없습니다")
    return TokenizedChat(tuple(ids), tuple(labels))
