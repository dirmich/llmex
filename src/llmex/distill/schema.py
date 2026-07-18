"""증류 inventory와 spool의 엄격한 schema v2."""

import hashlib
from typing import Any, Literal

from pydantic import Field, model_validator

from llmex.chat.data import ResponseQualityContract, validate_conversation_act_binding
from llmex.config import StrictModel
from llmex.fingerprint import fingerprint


class SourceProvenance(StrictModel):
    dataset: str = Field(min_length=1)
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    collected_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_split: Literal["train", "heldout"]
    metadata: dict[str, str | int]
    response_quality: ResponseQualityContract | None = None

    @model_validator(mode="after")
    def validate_conversation_act_binding(self) -> "SourceProvenance":
        validate_conversation_act_binding(self.metadata, self.response_quality)
        return self


class LogicalRequest(StrictModel):
    schema_version: Literal[2]
    id: str = Field(pattern=r"^distill-[0-9a-f]{24}$")
    prompt: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split: Literal["train", "heldout"]
    source: SourceProvenance

    @model_validator(mode="after")
    def preserve_upstream_heldout(self) -> "LogicalRequest":
        if self.source.source_split == "heldout" and self.split != "heldout":
            raise ValueError("upstream heldout은 distill heldout으로 보존해야 합니다")
        expected = hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()
        if self.prompt_sha256 != expected or self.id != f"distill-{expected[:24]}":
            raise ValueError("logical request prompt hash 또는 ID가 다릅니다")
        return self


class SpoolRecord(StrictModel):
    schema_version: Literal[2]
    request_id: str
    config_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["accepted", "rejected", "failed"]
    reason: str | None
    attempts: int = Field(ge=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    response: str | None
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_record(self) -> "SpoolRecord":
        basis: dict[str, Any] = self.model_dump(exclude={"record_sha256"})
        if fingerprint(basis) != self.record_sha256:
            raise ValueError("spool record hash가 정규화 내용과 다릅니다")
        return self
