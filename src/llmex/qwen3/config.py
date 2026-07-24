"""Qwen3-14B QLoRA 전용 설정."""

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BeforeValidator, Field, ValidationError, model_validator

from llmex.config import StrictModel
from llmex.errors import ConfigError


def _path(value: object) -> Path:
    if not isinstance(value, (str, Path)):
        raise ValueError("경로는 문자열이어야 합니다")
    return Path(value)


ConfigPath = Annotated[Path, BeforeValidator(_path)]


class QLoRAConfig(StrictModel):
    """4-bit 양자화와 LoRA adapter 설정."""

    load_in_4bit: Literal[True] = True
    quant_type: Literal["nf4", "fp4"] = "nf4"
    double_quant: bool = True
    compute_dtype: Literal["bfloat16", "float16"] = "bfloat16"
    rank: int = Field(default=32, gt=0)
    alpha: int = Field(default=64, gt=0)
    dropout: float = Field(default=0.05, ge=0.0, lt=1.0)
    target_modules: list[str] = Field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        min_length=1,
    )

    @model_validator(mode="after")
    def unique_targets(self) -> "QLoRAConfig":
        if len(self.target_modules) != len(set(self.target_modules)):
            raise ValueError("target_modules는 중복될 수 없습니다")
        return self


class Qwen3Config(StrictModel):
    """기존 100M trainer와 독립적인 Qwen3 SFT 설정."""

    schema_version: Literal[1] = 1
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    model_dir: ConfigPath
    train_data: ConfigPath
    heldout_data: ConfigPath
    output_dir: ConfigPath
    allowed_licenses: list[str] = Field(min_length=1)
    sequence_length: int = Field(default=2048, ge=128)
    seed: int = Field(default=42, ge=0)
    max_steps: int = Field(default=100, gt=0)
    learning_rate: float = Field(default=2e-5, gt=0.0)
    warmup_steps: int = Field(default=10, ge=0)
    micro_batch_size: int = Field(default=1, gt=0)
    gradient_accumulation_steps: int = Field(default=16, gt=0)
    eval_batch_size: int = Field(default=1, gt=0)
    logging_steps: int = Field(default=1, gt=0)
    eval_steps: int = Field(default=25, gt=0)
    save_steps: int = Field(default=25, gt=0)
    max_eval_examples: int | None = Field(default=100, gt=0)
    gradient_checkpointing: bool = True
    trust_remote_code: Literal[False] = False
    qlora: QLoRAConfig = Field(default_factory=QLoRAConfig)

    @model_validator(mode="after")
    def validate_training(self) -> "Qwen3Config":
        if self.warmup_steps > self.max_steps:
            raise ValueError("warmup_steps는 max_steps 이하여야 합니다")
        if len(self.allowed_licenses) != len(set(self.allowed_licenses)):
            raise ValueError("allowed_licenses는 중복될 수 없습니다")
        if self.model_dir == self.output_dir:
            raise ValueError("output_dir는 원본 model_dir와 달라야 합니다")
        return self


def load_qwen3_config(path: Path) -> Qwen3Config:
    """엄격한 YAML 설정을 로드합니다."""

    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Qwen3 설정을 읽을 수 없습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"Qwen3 설정 최상위는 mapping이어야 합니다: {path}")
    try:
        return Qwen3Config.model_validate(value)
    except ValidationError as exc:
        raise ConfigError(f"Qwen3 설정 검증 실패: {path}: {exc}") from exc
