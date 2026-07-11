"""엄격한 YAML 설정 모델과 로더."""

from pathlib import Path
from typing import Annotated, Any, Literal, TypeVar

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)

from llmex.errors import ConfigError


class StrictModel(BaseModel):
    """알 수 없는 키와 암묵적 타입 변환을 거부하는 기반 모델."""

    model_config = ConfigDict(extra="forbid", strict=True)


def _parse_path(value: object) -> Path:
    if not isinstance(value, (str, Path)):
        raise ValueError("경로는 문자열이어야 합니다")
    return Path(value)


YamlPath = Annotated[Path, BeforeValidator(_parse_path)]


class PathConfig(StrictModel):
    """프로젝트 영속 경로."""

    data: YamlPath = Path("data")
    artifacts: YamlPath = Path("artifacts")
    runs: YamlPath = Path("runs")


class DumpConfig(StrictModel):
    """날짜가 고정된 Wikimedia dump 입력."""

    date: str = Field(pattern=r"^\d{8}$")
    url: HttpUrl
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_pinned_url(self) -> "DumpConfig":
        if "latest" in str(self.url):
            raise ValueError("학습 설정에는 latest URL을 사용할 수 없습니다")
        if self.date not in str(self.url):
            raise ValueError("dump URL에 date가 포함되어야 합니다")
        return self


class CleaningConfig(StrictModel):
    """M1에서 사용할 최소 정제 정책."""

    min_chars: int = Field(default=100, ge=1)
    normalize: Literal["NFC"] = "NFC"
    min_hangul_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
    max_repetition_ratio: float = Field(default=0.35, ge=0.0, le=1.0)
    max_markup_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    table_policy: Literal["drop"] = "drop"
    math_policy: Literal["text"] = "text"
    list_policy: Literal["text"] = "text"
    reference_policy: Literal["drop"] = "drop"
    near_dedup: bool = False
    near_dedup_threshold: float = Field(default=0.9, gt=0.0, le=1.0)
    shingle_size: int = Field(default=5, ge=2, le=20)


class DownloadConfig(StrictModel):
    """다운로드 자원 및 복구 정책."""

    timeout_seconds: float = Field(default=30.0, gt=0.0)
    retries: int = Field(default=3, ge=0, le=20)
    retry_backoff_seconds: float = Field(default=1.0, ge=0.0)
    disk_overhead_ratio: float = Field(default=1.1, ge=1.0)


class DataConfig(StrictModel):
    """데이터 명령 공통 설정."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    seed: int = Field(ge=0)
    paths: PathConfig = PathConfig()
    dump: DumpConfig
    cleaning: CleaningConfig = CleaningConfig()
    download: DownloadConfig = DownloadConfig()


class ModelConfig(StrictModel):
    """decoder-only 모델 형상 설정."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    vocab_size: int = Field(gt=0)
    max_seq_len: int = Field(gt=0)
    n_layers: int = Field(gt=0)
    d_model: int = Field(gt=0)
    n_heads: int = Field(gt=0)
    n_kv_heads: int = Field(gt=0)
    ffn_hidden_size: int = Field(gt=0)
    dropout: float = Field(ge=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_attention_shape(self) -> "ModelConfig":
        if self.d_model % self.n_heads != 0:
            raise ValueError("d_model은 n_heads로 나누어져야 합니다")
        if self.n_heads % self.n_kv_heads != 0:
            raise ValueError("n_heads는 n_kv_heads로 나누어져야 합니다")
        return self


ConfigT = TypeVar("ConfigT", bound=StrictModel)


def load_yaml(path: Path, model: type[ConfigT]) -> ConfigT:
    """YAML 한 파일을 읽어 지정 모델로 엄격하게 검증한다."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"설정 파일을 읽을 수 없습니다: {path}: {exc}") from exc
    try:
        value: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML 구문이 올바르지 않습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"설정 최상위 값은 매핑이어야 합니다: {path}")
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(item) for item in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(f"설정 검증에 실패했습니다: {path}: {details}") from exc
