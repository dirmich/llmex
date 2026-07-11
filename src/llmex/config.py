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
    norm_eps: float = Field(default=1e-5, gt=0.0)
    rope_theta: float = Field(default=10000.0, gt=0.0)
    init_std: float = Field(default=0.02, gt=0.0)

    @model_validator(mode="after")
    def validate_attention_shape(self) -> "ModelConfig":
        if self.d_model % self.n_heads != 0:
            raise ValueError("d_model은 n_heads로 나누어져야 합니다")
        if self.n_heads % self.n_kv_heads != 0:
            raise ValueError("n_heads는 n_kv_heads로 나누어져야 합니다")
        if (self.d_model // self.n_heads) % 2 != 0:
            raise ValueError("RoPE를 위해 attention head 차원은 짝수여야 합니다")
        return self


class TokenizerConfig(StrictModel):
    """M2 byte-level BPE 학습, 평가와 shard 설정."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    seed: int = Field(default=42, ge=0)
    vocab_size: Literal[16000, 32000]
    corpus: YamlPath
    output_dir: YamlPath
    shard_tokens: int = Field(default=10_000_000, gt=1)
    evaluation_samples: int = Field(default=10_000, gt=0)


class OptimizerConfig(StrictModel):
    """AdamW 최적화 설정."""

    learning_rate: float = Field(gt=0.0)
    min_learning_rate: float = Field(default=0.0, ge=0.0)
    weight_decay: float = Field(default=0.1, ge=0.0)
    beta1: float = Field(default=0.9, ge=0.0, lt=1.0)
    beta2: float = Field(default=0.95, ge=0.0, lt=1.0)
    eps: float = Field(default=1e-8, gt=0.0)
    warmup_steps: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_learning_rates(self) -> "OptimizerConfig":
        if self.min_learning_rate > self.learning_rate:
            raise ValueError("min_learning_rate는 learning_rate 이하여야 합니다")
        return self


class TrainingConfig(StrictModel):
    """M4 단일 프로세스 학습과 완전 재개 설정."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    seed: int = Field(default=42, ge=0)
    model: ModelConfig
    shards_manifest: YamlPath
    run_dir: YamlPath
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    precision: Literal["auto", "bf16", "fp16", "fp32"] = "auto"
    sequence_length: int = Field(gt=1)
    micro_batch_size: int = Field(gt=0)
    gradient_accumulation_steps: int = Field(default=1, gt=0)
    max_steps: int = Field(gt=0)
    gradient_clip_norm: float = Field(default=1.0, gt=0.0)
    validation_interval: int = Field(default=10, gt=0)
    validation_batches: int = Field(default=4, gt=0)
    checkpoint_interval: int = Field(default=10, gt=0)
    log_interval: int = Field(default=1, gt=0)
    optimizer: OptimizerConfig
    deterministic: bool = True

    @model_validator(mode="after")
    def validate_training(self) -> "TrainingConfig":
        if self.sequence_length > self.model.max_seq_len:
            raise ValueError("sequence_length는 model.max_seq_len 이하여야 합니다")
        if self.optimizer.warmup_steps > self.max_steps:
            raise ValueError("warmup_steps는 max_steps 이하여야 합니다")
        return self


class EvaluationConfig(StrictModel):
    """M5 checkpoint 평가·생성·benchmark 설정."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    seed: int = Field(default=42, ge=0)
    checkpoint: YamlPath
    training_config: YamlPath
    tokenizer_dir: YamlPath
    shards_manifest: YamlPath
    corpus: YamlPath | None = None
    output_dir: YamlPath
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    splits: list[Literal["validation", "test"]] = ["validation", "test"]
    batch_size: int = Field(default=4, gt=0)
    max_batches: int | None = Field(default=None, gt=0)
    prompts: list[str] = [
        "대한민국의 수도는",
        "한국어에서 조사는",
        "세종대왕은",
        "2026년 7월 11일은",
    ]
    max_new_tokens: int = Field(default=32, ge=0)
    temperature: float = Field(default=0.0, ge=0.0)
    top_k: int | None = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    repetition_penalty: float = Field(default=1.0, gt=0.0)
    use_cache: bool = True
    benchmark_warmup: int = Field(default=2, ge=0)
    benchmark_iterations: int = Field(default=5, gt=0)
    canaries_file: YamlPath | None = None
    canary_max_rank: int = Field(default=10, gt=0)


class BudgetConfig(StrictModel):
    """M6 실행을 중단시키는 자원 상한과 최소 여유."""

    minimum_free_disk_gib: float = Field(gt=0.0)
    minimum_available_memory_gib: float = Field(gt=0.0)
    maximum_hours: float = Field(gt=0.0)
    maximum_energy_kwh: float = Field(gt=0.0)
    maximum_parameters: int = Field(gt=0, le=120_000_000)
    token_budget: int = Field(gt=0)


class PipelineStageConfig(StrictModel):
    """shell 해석 없이 실행하는 재개 가능한 한 단계."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    command: list[str] = Field(min_length=1)
    outputs: list[YamlPath] = []
    external: bool = False
    timeout_seconds: int = Field(default=3600, gt=0)


class PipelineConfig(StrictModel):
    """M6 전체 파이프라인과 외부 승인 게이트."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    seed: int = Field(default=42, ge=0)
    run_dir: YamlPath
    budget: BudgetConfig
    stages: list[PipelineStageConfig] = Field(min_length=1)
    required_evidence: list[YamlPath] = []
    tokenizer_candidates: list[Literal[16000, 32000]] = [16000, 32000]
    selected_tokenizer: Literal[16000, 32000]
    baseline_parameters: int = Field(gt=0, le=120_000_000)

    @model_validator(mode="after")
    def validate_pipeline(self) -> "PipelineConfig":
        names = [stage.name for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("pipeline 단계 이름은 중복될 수 없습니다")
        if self.selected_tokenizer not in self.tokenizer_candidates:
            raise ValueError("선택 tokenizer는 비교 후보에 포함되어야 합니다")
        if self.baseline_parameters > self.budget.maximum_parameters:
            raise ValueError("baseline 파라미터가 승인 예산을 초과합니다")
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
