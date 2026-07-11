"""M1 document schema v1."""

from typing import Any, Literal

from pydantic import Field

from llmex.config import StrictModel


class Attribution(StrictModel):
    page_id: int = Field(gt=0)
    revision_id: int = Field(gt=0)
    source_url: str
    dump_url: str
    dump_date: str = Field(pattern=r"^\d{8}$")
    license: str


class Quality(StrictModel):
    chars: int = Field(ge=0)
    bytes: int = Field(ge=0)
    hangul_ratio: float = Field(ge=0.0, le=1.0)
    repetition_ratio: float = Field(ge=0.0, le=1.0)
    markup_ratio: float = Field(ge=0.0, le=1.0)
    policy_stats: dict[str, int]


class Document(StrictModel):
    schema_version: Literal[1] = 1
    page_id: int = Field(gt=0)
    revision_id: int = Field(gt=0)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_url: str
    dump_url: str
    dump_date: str = Field(pattern=r"^\d{8}$")
    license: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality: Quality
    split: Literal["train", "validation", "test"] | None = None

    def attribution(self) -> Attribution:
        return Attribution.model_validate(self.model_dump(include=set(Attribution.model_fields)))

    def json_row(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
