"""엄격한 JSONL chat loader와 provenance/license/hash 검증."""

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from llmex.config import StrictModel
from llmex.errors import InputError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file


class Message(StrictModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


def _empty_term_groups() -> list[list[str]]:
    return []


class ResponseQualityContract(StrictModel):
    """teacher 응답에 적용할 source 결속 품질 계약."""

    schema_version: Literal[1] = 1
    mode: Literal[
        "conversation",
        "conversation-question",
        "conversation-suggestion",
        "translation-only",
        "direct-message",
        "uncertainty",
    ]
    target_language: Literal["ko", "en", "ja"]
    max_sentences: int = Field(default=3, ge=1, le=8)
    required_numbers: list[list[str]] = Field(default_factory=_empty_term_groups)
    required_entities: list[list[str]] = Field(default_factory=_empty_term_groups)
    required_terms: list[list[str]] = Field(default_factory=_empty_term_groups)

    @field_validator("required_numbers", "required_entities", "required_terms")
    @classmethod
    def validate_term_groups(cls, groups: list[list[str]]) -> list[list[str]]:
        if any(not group or any(not value.strip() for value in group) for group in groups):
            raise ValueError("응답 품질 계약의 필수 표면형 묶음은 비어 있을 수 없습니다")
        return groups


class Provenance(StrictModel):
    dataset: str = Field(min_length=1)
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    collected_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_dataset: str | None = None
    source_license: str | None = None
    teacher_model: str | None = None
    teacher_output_license: str | None = None
    request_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    raw_response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_id: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_collected_at: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_metadata: dict[str, str | int] | None = None
    response_quality: ResponseQualityContract | None = None

    @model_validator(mode="after")
    def validate_conversation_act_binding(self) -> "Provenance":
        validate_conversation_act_binding(self.source_metadata or {}, self.response_quality)
        return self


def validate_conversation_act_binding(
    metadata: dict[str, str | int], contract: ResponseQualityContract | None
) -> None:
    """대화 행위 metadata와 품질 계약이 서로 우회되지 않게 결속한다."""
    metadata_act = metadata.get("conversation_act")
    contract_act: str | None = None
    if contract is not None and contract.mode.startswith("conversation-"):
        contract_act = contract.mode.removeprefix("conversation-")
    if metadata_act is None and contract_act is None:
        return
    if metadata_act not in {"question", "suggestion"} or metadata_act != contract_act:
        raise ValueError("conversation_act metadata와 response_quality mode가 일치해야 합니다")


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
                "provenance": self.provenance.model_dump(exclude_none=True),
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
    prompt_sha256: str
    source_sha256: str | None
    source_key: str


@dataclass(frozen=True)
class ChatDataset:
    examples: tuple[ChatExample, ...]
    file_sha256: str
    fingerprint: str
    licenses: tuple[str, ...]


def canonical_final_user_prompt(messages: tuple[Message, ...] | list[Message]) -> str:
    """마지막 user turn을 Unicode·공백 정규화한 split 결속 문자열로 만든다."""

    for message in reversed(messages):
        if message.role == "user":
            normalized = unicodedata.normalize(
                "NFC", unicodedata.normalize("NFKC", message.content)
            )
            return " ".join(normalized.split())
    raise IntegrityError("대화에 final-user prompt가 없습니다")


def final_user_prompt_sha256(messages: tuple[Message, ...] | list[Message]) -> str:
    return hashlib.sha256(canonical_final_user_prompt(messages).encode("utf-8")).hexdigest()


def provenance_source_key(provenance: Provenance, *, fallback_sha256: str | None = None) -> str:
    """source SHA, 명시 ID, 호출자가 제공한 행 fallback 순으로 원천을 결속한다."""

    if provenance.source_sha256 is not None:
        return provenance.source_sha256
    if provenance.source_id is None and fallback_sha256 is not None:
        return fallback_sha256
    return fingerprint(
        {
            "dataset": provenance.dataset,
            "source": provenance.source,
            "source_id": provenance.source_id,
        }
    )


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
                messages = tuple(row.messages)
                examples.append(
                    ChatExample(
                        row.id,
                        row.split,
                        messages,
                        row.sha256,
                        final_user_prompt_sha256(messages),
                        row.provenance.source_sha256,
                        provenance_source_key(row.provenance),
                    )
                )
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
