"""엄격한 JSONL chat loader와 provenance/license/hash 검증."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from llmex.config import StrictModel
from llmex.errors import InputError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file


class Message(StrictModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class Provenance(StrictModel):
    dataset: str = Field(min_length=1)
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    collected_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ChatRow(StrictModel):
    schema_version: Literal[1]
    id: str = Field(min_length=1)
    split: Literal["train", "heldout"]
    messages: list[Message] = Field(min_length=2)
    provenance: Provenance
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_turns(self) -> "ChatRow":
        roles = [message.role for message in self.messages]
        if roles[0] == "assistant" or roles[-1] != "assistant":
            raise ValueError("대화는 system/user로 시작하고 assistant로 끝나야 합니다")
        if any(role == "system" for role in roles[1:]):
            raise ValueError("system turn은 맨 처음에 한 번만 허용됩니다")
        conversational = [role for role in roles if role != "system"]
        if any(
            role != ("user" if index % 2 == 0 else "assistant")
            for index, role in enumerate(conversational)
        ):
            raise ValueError("system 뒤 user/assistant turn이 번갈아야 합니다")
        expected = fingerprint(
            {
                "id": self.id,
                "messages": [message.model_dump() for message in self.messages],
                "provenance": self.provenance.model_dump(),
                "split": self.split,
            }
        )
        if self.sha256 != expected:
            raise ValueError("행 sha256가 정규화 내용과 다릅니다")
        return self


@dataclass(frozen=True)
class ChatExample:
    id: str
    split: str
    messages: tuple[Message, ...]
    sha256: str


@dataclass(frozen=True)
class ChatDataset:
    examples: tuple[ChatExample, ...]
    file_sha256: str
    fingerprint: str
    licenses: tuple[str, ...]


def load_chat_jsonl(path: Path, *, split: str, allowed_licenses: set[str]) -> ChatDataset:
    if not path.is_file():
        raise InputError(f"chat JSONL 파일이 없습니다: {path}")
    examples: list[ChatExample] = []
    licenses: set[str] = set()
    ids: set[str] = set()
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    raise IntegrityError(f"빈 JSONL 행은 허용하지 않습니다: {path}:{line_number}")
                value = json.loads(line)
                row = ChatRow.model_validate(value)
                if row.split != split:
                    raise IntegrityError(f"split 불일치: {path}:{line_number}")
                if row.provenance.license not in allowed_licenses:
                    raise IntegrityError(
                        f"허가되지 않은 라이선스: {row.provenance.license}: {path}:{line_number}"
                    )
                if row.id in ids:
                    raise IntegrityError(f"중복 chat id: {row.id}")
                ids.add(row.id)
                licenses.add(row.provenance.license)
                examples.append(ChatExample(row.id, row.split, tuple(row.messages), row.sha256))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise IntegrityError(f"chat JSONL schema 검증 실패: {path}: {exc}") from exc
    if not examples:
        raise IntegrityError(f"chat JSONL이 비었습니다: {path}")
    digest = sha256_file(path)
    manifest = {
        "schema_version": 1,
        "file_sha256": digest,
        "rows": [example.sha256 for example in examples],
        "split": split,
        "licenses": sorted(licenses),
    }
    return ChatDataset(tuple(examples), digest, fingerprint(manifest), tuple(sorted(licenses)))
