"""LLMEX 명령행 인터페이스."""

import json
import logging
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Never

import typer

from llmex import __version__
from llmex.config import (
    DataConfig,
    DistillationConfig,
    EvaluationConfig,
    ModelConfig,
    PipelineConfig,
    SFTConfig,
    SFTCurriculumConfig,
    SFTMixConfig,
    SFTQualityConfig,
    StrictModel,
    TokenizerConfig,
    TrainingConfig,
    load_yaml,
)
from llmex.data.download import download, fetch_metadata
from llmex.data.io import prepare_output, read_jsonl_zst, write_json, write_jsonl_zst
from llmex.data.pipeline import (
    build_report,
    clean_rows,
    dedup_rows,
    extract_rows,
    raw_manifest,
    report_markdown,
    run_e2e,
    split_rows,
)
from llmex.errors import ExitCode, LlmexError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.logging import configure_logging
from llmex.paths import project_root
from llmex.run import create_run
from llmex.tokenizer.core import train as train_tokenizer
from llmex.tokenizer.evaluate import evaluate as evaluate_tokenizer
from llmex.tokenizer.pack import pack as pack_tokenizer

app = typer.Typer(
    name="llmex",
    help="한국어 Wikipedia 기반 소형 언어 모델 실험 도구",
    no_args_is_help=True,
    invoke_without_command=True,
)
config_app = typer.Typer(help="YAML 설정을 검증합니다.", no_args_is_help=True)
fingerprint_app = typer.Typer(help="입력 fingerprint를 계산합니다.", no_args_is_help=True)
run_app = typer.Typer(help="재현 가능한 실행 디렉터리를 관리합니다.", no_args_is_help=True)
data_app = typer.Typer(help="Wikimedia M1 데이터 파이프라인을 실행합니다.", no_args_is_help=True)
tokenizer_app = typer.Typer(help="M2 토크나이저와 token shard를 생성합니다.", no_args_is_help=True)
model_app = typer.Typer(help="M3 decoder-only 모델을 검사합니다.", no_args_is_help=True)
train_app = typer.Typer(help="M4 결정적 학습과 checkpoint 재개를 실행합니다.", no_args_is_help=True)
sft_app = typer.Typer(
    help="허가된 대화 데이터로 assistant-only SFT를 실행합니다.", no_args_is_help=True
)
distill_app = typer.Typer(
    help="OpenAI 호환 teacher에서 재개 가능한 증류 데이터를 수집합니다.", no_args_is_help=True
)
pipeline_app = typer.Typer(
    help="M6 전체 파이프라인과 외부 게이트를 관리합니다.", no_args_is_help=True
)
release_app = typer.Typer(
    help="M7 릴리스 번들·감사·외부 승인 gate를 관리합니다.", no_args_is_help=True
)
app.add_typer(config_app, name="config")
app.add_typer(fingerprint_app, name="fingerprint")
app.add_typer(run_app, name="run")
app.add_typer(data_app, name="data")
app.add_typer(tokenizer_app, name="tokenizer")
app.add_typer(model_app, name="model")
app.add_typer(train_app, name="train")
app.add_typer(sft_app, name="sft")
app.add_typer(distill_app, name="distill")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(release_app, name="release")


@release_app.command("bundle")
def release_bundle(
    output: Annotated[Path, typer.Option("--output")] = Path("dist/reproducibility"),
) -> None:
    """checksum·SBOM·provenance를 포함한 로컬 재현 bundle을 생성합니다."""
    try:
        from llmex.release import bundle

        result = bundle(project_root(), output)
    except (LlmexError, OSError, subprocess.SubprocessError) as error:
        if isinstance(error, LlmexError):
            _emit_error(error)
        from llmex.errors import InputError

        _emit_error(InputError(f"릴리스 bundle 생성 실패: {error}"))
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@release_app.command("audit")
def release_audit() -> None:
    """비밀·경로·라이선스 문서·clean-room 참조 경계를 검사합니다."""
    try:
        from llmex.release import audit

        result = audit(project_root())
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@release_app.command("gate")
def release_gate(
    approvals: Annotated[Path, typer.Option("--approvals")],
    repository: Annotated[Path, typer.Option("--repository-root")] = Path("."),
) -> None:
    """법무·장기 baseline·수동 품질·공개 배포의 외부 승인을 검증합니다."""
    try:
        from llmex.release import external_gate

        result = external_gate(approvals, repository)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


class ConfigKind(StrEnum):
    """지원하는 M0 설정 종류."""

    DATA = "data"
    MODEL = "model"
    TOKENIZER = "tokenizer"
    TRAINING = "training"
    EVALUATION = "evaluation"
    PIPELINE = "pipeline"
    SFT = "sft"
    SFT_CURRICULUM = "sft-curriculum"
    SFT_MIX = "sft-mix"
    SFT_QUALITY = "sft-quality"
    DISTILLATION = "distillation"


def _model(kind: ConfigKind) -> type[StrictModel]:
    if kind is ConfigKind.DATA:
        return DataConfig
    if kind is ConfigKind.TOKENIZER:
        return TokenizerConfig
    if kind is ConfigKind.TRAINING:
        return TrainingConfig
    if kind is ConfigKind.EVALUATION:
        return EvaluationConfig
    if kind is ConfigKind.PIPELINE:
        return PipelineConfig
    if kind is ConfigKind.SFT:
        return SFTConfig
    if kind is ConfigKind.SFT_CURRICULUM:
        return SFTCurriculumConfig
    if kind is ConfigKind.SFT_MIX:
        return SFTMixConfig
    if kind is ConfigKind.SFT_QUALITY:
        return SFTQualityConfig
    if kind is ConfigKind.DISTILLATION:
        return DistillationConfig
    return ModelConfig


def _distill_call(config_path: Path, action: str) -> None:
    try:
        config = load_yaml(config_path, DistillationConfig)
        from llmex.distill import collect, export, preflight, prepare, status, validate

        operations = {
            "preflight": preflight,
            "prepare": prepare,
            "collect": collect,
            "resume": collect,
            "status": status,
            "export": export,
            "validate": validate,
        }
        result = operations[action](config)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@distill_app.command("preflight")
def distill_preflight(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """`/v1/models`로 endpoint와 teacher model을 확인합니다."""
    _distill_call(config_path, "preflight")


@distill_app.command("prepare")
def distill_prepare(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """공개 instruction과 Wikipedia에서 logical request inventory를 만듭니다."""
    _distill_call(config_path, "prepare")


@distill_app.command("collect")
def distill_collect(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """아직 완료되지 않은 teacher request를 수집합니다."""
    _distill_call(config_path, "collect")


@distill_app.command("resume")
def distill_resume(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """완료 spool은 재호출하지 않고 실패·미완료 request만 재개합니다."""
    _distill_call(config_path, "resume")


@distill_app.command("status")
def distill_status(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """수집 진행률과 상태별 건수를 출력합니다."""
    _distill_call(config_path, "status")


@distill_app.command("export")
def distill_export(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """필터를 통과한 응답을 결정적 ChatDataset JSONL로 압축합니다."""
    _distill_call(config_path, "export")


@distill_app.command("validate")
def distill_validate(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """spool·checksum·라이선스·split 비누출을 실패-폐쇄로 검증합니다."""
    _distill_call(config_path, "validate")


def _sft_config(path: Path) -> SFTConfig:
    return load_yaml(path, SFTConfig)


def _sft_curriculum_call(config_path: Path, action: str) -> None:
    try:
        config = load_yaml(config_path, SFTCurriculumConfig)
        from llmex.chat.curriculum import (
            preflight_curriculum,
            prepare_curriculum,
            status_curriculum,
            validate_curriculum,
        )

        operations = {
            "preflight": preflight_curriculum,
            "prepare": prepare_curriculum,
            "status": status_curriculum,
            "validate": validate_curriculum,
        }
        result = operations[action](config)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@sft_app.command("curriculum-preflight")
def sft_curriculum_preflight(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """보정 커리큘럼 입력·비누출·토큰 질량을 출력 생성 없이 검증합니다."""
    _sft_curriculum_call(config_path, "preflight")


@sft_app.command("curriculum-prepare")
def sft_curriculum_prepare(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """결정적 보정 예제와 hash replay를 원자적으로 생성합니다."""
    _sft_curriculum_call(config_path, "prepare")


@sft_app.command("curriculum-status")
def sft_curriculum_status(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """보정 커리큘럼 출력의 pending/ready 상태를 확인합니다."""
    _sft_curriculum_call(config_path, "status")


@sft_app.command("curriculum-validate")
def sft_curriculum_validate(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """보정 커리큘럼을 현재 입력에서 재유도해 실패-폐쇄 검증합니다."""
    _sft_curriculum_call(config_path, "validate")


def _sft_mix_call(config_path: Path, action: str) -> None:
    try:
        config = load_yaml(config_path, SFTMixConfig)
        from llmex.chat.mixer import preflight_mix, prepare_mix, status_mix, validate_mix

        operations = {
            "prepare": prepare_mix,
            "preflight": preflight_mix,
            "status": status_mix,
            "validate": validate_mix,
        }
        result = operations[action](config)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@sft_app.command("prepare-mix")
def sft_prepare_mix(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """공개·teacher 데이터를 split 비누출 JSONL로 결정적 혼합합니다."""
    _sft_mix_call(config_path, "prepare")


@sft_app.command("preflight-mix")
def sft_preflight_mix(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """입력·teacher manifest·길이 gate를 출력 생성 없이 검증합니다."""
    _sft_mix_call(config_path, "preflight")


@sft_app.command("status-mix")
def sft_status_mix(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """혼합 출력의 pending/ready 상태와 결속을 확인합니다."""
    _sft_mix_call(config_path, "status")


@sft_app.command("validate-mix")
def sft_validate_mix(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """혼합 출력을 현재 입력과 재유도해 실패-폐쇄 검증합니다."""
    _sft_mix_call(config_path, "validate")


def _sft_quality_call(config_path: Path, action: str) -> None:
    try:
        config = load_yaml(config_path, SFTQualityConfig)
        from llmex.chat.quality import (
            preflight_quality,
            quality_eval,
            status_quality,
            validate_quality,
        )

        operations = {
            "preflight": preflight_quality,
            "eval": quality_eval,
            "status": status_quality,
            "validate": validate_quality,
        }
        result = operations[action](config)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@sft_app.command("quality-preflight")
def sft_quality_preflight(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """고정 suite·checkpoint·SFT 결속과 평가 계획을 검증합니다."""
    _sft_quality_call(config_path, "preflight")


@sft_app.command("quality-eval")
def sft_quality_eval(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """고정 decoding matrix로 immutable 자동 대화 품질 평가를 실행합니다."""
    _sft_quality_call(config_path, "eval")


@sft_app.command("quality-status")
def sft_quality_status(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """자동 대화 품질 평가 artifact 상태를 확인합니다."""
    _sft_quality_call(config_path, "status")


@sft_app.command("quality-validate")
def sft_quality_validate(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """자동 대화 품질 평가 artifact 결속을 검증합니다."""
    _sft_quality_call(config_path, "validate")


@sft_app.command("quality-review-template")
def sft_quality_review_template(
    config_path: Annotated[Path, typer.Option("--config")],
) -> None:
    """통과한 자동 평가에 결속된 결정적 blind review 표본을 생성합니다."""
    try:
        config = load_yaml(config_path, SFTQualityConfig)
        from llmex.chat.quality_review import quality_review_template

        result = quality_review_template(config)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


def _sft_quality_review_gate_call(
    config_path: Path,
    repository: Path,
    quality_reviews: list[Path],
    safety_review: Path,
    adjudications: list[Path],
    *,
    validate: bool,
) -> None:
    try:
        config = load_yaml(config_path, SFTQualityConfig)
        from llmex.chat.quality_review import quality_gate, validate_quality_gate

        operation = validate_quality_gate if validate else quality_gate
        result = operation(
            config,
            repository,
            quality_reviews,
            safety_review,
            adjudications,
        )
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@sft_app.command("quality-gate")
def sft_quality_gate(
    config_path: Annotated[Path, typer.Option("--config")],
    repository: Annotated[Path, typer.Option("--repository")],
    quality_reviews: Annotated[list[Path], typer.Option("--quality-review")],
    safety_review: Annotated[Path, typer.Option("--safety-review")],
    adjudications: Annotated[list[Path] | None, typer.Option("--adjudication")] = None,
) -> None:
    """독립 서명된 human review로 실패-폐쇄 수동 품질 gate를 생성합니다."""
    _sft_quality_review_gate_call(
        config_path,
        repository,
        quality_reviews,
        safety_review,
        adjudications or [],
        validate=False,
    )


@sft_app.command("quality-review-validate")
def sft_quality_review_validate(
    config_path: Annotated[Path, typer.Option("--config")],
    repository: Annotated[Path, typer.Option("--repository")],
    quality_reviews: Annotated[list[Path], typer.Option("--quality-review")],
    safety_review: Annotated[Path, typer.Option("--safety-review")],
    adjudications: Annotated[list[Path] | None, typer.Option("--adjudication")] = None,
) -> None:
    """수동 quality gate와 모든 서명 evidence를 현재 artifact에서 재검증합니다."""
    _sft_quality_review_gate_call(
        config_path,
        repository,
        quality_reviews,
        safety_review,
        adjudications or [],
        validate=True,
    )


def _sft_train(config_path: Path, resume: Path | None, dry_run: bool) -> None:
    try:
        config = _sft_config(config_path)
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "run_dir": str(config.run_dir),
                        "fingerprint": fingerprint(config.model_dump(mode="json")),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        from llmex.chat import train_sft

        result = train_sft(config, resume=resume)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@sft_app.command("preflight")
def sft_preflight(
    config_path: Annotated[Path, typer.Option("--config")],
    measure_baseline: Annotated[
        bool, typer.Option("--measure-baseline/--no-measure-baseline")
    ] = False,
) -> None:
    """SFT 전체 초기화와 선택적 step-0 baseline을 출력 생성 없이 검증합니다."""
    try:
        from llmex.chat import preflight_sft

        result = preflight_sft(_sft_config(config_path), measure_baseline=measure_baseline)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@sft_app.command("train")
def sft_train(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """새 assistant-only SFT run을 시작합니다."""
    _sft_train(config_path, None, dry_run)


@sft_app.command("resume")
def sft_resume(
    config_path: Annotated[Path, typer.Option("--config")],
    checkpoint: Annotated[Path | None, typer.Option("--checkpoint")] = None,
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """원자 checkpoint에서 optimizer/RNG/data cursor를 완전 재개합니다."""
    try:
        config = _sft_config(config_path)
    except LlmexError as error:
        _emit_error(error)
    _sft_train(config_path, checkpoint or config.run_dir / "checkpoints/latest.pt", dry_run)


@sft_app.command("eval")
def sft_eval(
    config_path: Annotated[Path, typer.Option("--config")],
    checkpoint: Annotated[Path, typer.Option("--checkpoint")],
) -> None:
    """heldout assistant NLL과 safety/repetition/EOS gate를 평가합니다."""
    try:
        from llmex.chat import evaluate_chat

        result = evaluate_chat(_sft_config(config_path), checkpoint)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@sft_app.command("generate")
def sft_generate(
    config_path: Annotated[Path, typer.Option("--config")],
    checkpoint: Annotated[Path, typer.Option("--checkpoint")],
    prompt: Annotated[str, typer.Option("--prompt")],
    temperature: Annotated[float, typer.Option("--temperature", min=0.0, max=2.0)] = 0.0,
    top_k: Annotated[int | None, typer.Option("--top-k", min=1)] = None,
    top_p: Annotated[float, typer.Option("--top-p", min=0.001, max=1.0)] = 1.0,
    repetition_penalty: Annotated[float, typer.Option("--repetition-penalty", min=0.01)] = 1.2,
    seed: Annotated[int, typer.Option("--seed", min=0)] = 0,
    max_new_tokens: Annotated[int | None, typer.Option("--max-new-tokens", min=1)] = None,
) -> None:
    """고정 chat template과 명시적 decoding으로 assistant 응답을 생성합니다."""
    try:
        from llmex.chat import generate_chat
        from llmex.model import GenerationConfig
        from llmex.tokenizer.core import SPECIAL_IDS

        config = _sft_config(config_path)
        result = generate_chat(
            config,
            checkpoint,
            prompt,
            generation=GenerationConfig(
                max_new_tokens=max_new_tokens or config.max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                eos_id=SPECIAL_IDS["<eos>"],
            ),
            seed=seed,
        )
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


def _emit_error(error: LlmexError) -> Never:
    logging.getLogger("llmex").error(str(error), extra={"fields": {"error_code": error.code.name}})
    raise typer.Exit(code=int(error.code))


def _pipeline_call(config_path: Path, action: str, allow_external: bool = False) -> None:
    try:
        config = load_yaml(config_path, PipelineConfig)
        from llmex.pipeline import export, preflight, recovery_drill, run

        if action == "preflight":
            result = preflight(config)
        elif action == "export":
            result = export(config)
        elif action == "drill":
            result = recovery_drill(config)
        elif action == "status":
            result = json.loads(
                (config.run_dir / "pipeline-status.json").read_text(encoding="utf-8")
            )
        else:
            result = run(config, allow_external=allow_external)
    except (LlmexError, OSError, json.JSONDecodeError) as error:
        if isinstance(error, LlmexError):
            _emit_error(error)
        from llmex.errors import InputError

        _emit_error(InputError(f"pipeline artifact를 읽을 수 없습니다: {error}"))
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@pipeline_app.command("preflight")
def pipeline_preflight(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """저장공간·메모리·모델 크기 예산을 실행 전에 검사합니다."""
    _pipeline_call(config_path, "preflight")


@pipeline_app.command("run")
def pipeline_run(
    config_path: Annotated[Path, typer.Option("--config")],
    allow_external: Annotated[
        bool, typer.Option(help="외부 증거가 갖춰진 단계를 실행합니다.")
    ] = False,
) -> None:
    """완료 단계는 건너뛰며 전체 단계를 재개 실행합니다."""
    _pipeline_call(config_path, "run", allow_external)


@pipeline_app.command("status")
def pipeline_status(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """현재 단계별 상태와 재개 가능 여부를 출력합니다."""
    _pipeline_call(config_path, "status")


@pipeline_app.command("drill")
def pipeline_drill(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """중간 파일 제거 뒤 상태 불변성과 복구 경로를 검증합니다."""
    _pipeline_call(config_path, "drill")


@pipeline_app.command("export")
def pipeline_export(config_path: Annotated[Path, typer.Option("--config")]) -> None:
    """JSON/Markdown 대시보드와 메트릭 묶음을 내보냅니다."""
    _pipeline_call(config_path, "export")


@app.callback()
def main(
    log_level: Annotated[
        str, typer.Option(help="구조화 로그 수준(DEBUG, INFO, WARNING, ERROR)")
    ] = "INFO",
    version: Annotated[bool, typer.Option("--version", help="버전을 출력합니다.")] = False,
) -> None:
    """공통 로깅과 버전 처리를 설정합니다."""

    configure_logging(log_level)
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=ExitCode.SUCCESS)


@config_app.command("validate")
def validate_config(
    path: Annotated[Path, typer.Argument(help="검증할 YAML 파일")],
    kind: Annotated[ConfigKind, typer.Option(help="설정 종류")],
) -> None:
    """알 수 없는 키와 잘못된 타입을 포함한 설정을 거부합니다."""

    try:
        loaded = load_yaml(path, _model(kind))
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(loaded.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


@fingerprint_app.command("file")
def fingerprint_file(
    path: Annotated[Path, typer.Argument(help="SHA-256을 계산할 파일")],
) -> None:
    """파일 SHA-256을 출력합니다."""

    try:
        typer.echo(sha256_file(path))
    except LlmexError as error:
        _emit_error(error)


@run_app.command("create")
def create_run_command(
    config_path: Annotated[Path, typer.Option("--config", help="검증할 YAML 설정")],
    kind: Annotated[ConfigKind, typer.Option(help="설정 종류")],
    dry_run: Annotated[bool, typer.Option(help="파일을 만들지 않고 계획만 출력합니다.")] = False,
    force: Annotated[bool, typer.Option(help="동일 실행 디렉터리 재사용을 허용합니다.")] = False,
) -> None:
    """검증된 설정과 환경/Git manifest를 실행 디렉터리에 저장합니다."""

    try:
        loaded = load_yaml(config_path, _model(kind))
        config = loaded.model_dump(mode="json")
        name = str(config["name"])
        root = project_root()
        runs_dir = root / "runs"
        if dry_run:
            typer.echo(
                json.dumps(
                    {"dry_run": True, "name": name, "fingerprint": fingerprint(config)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        run = create_run(name=name, config=config, runs_dir=runs_dir, root=root, force=force)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps({"path": str(run.path), "fingerprint": run.fingerprint}))


def _data_config(path: Path) -> DataConfig:
    return load_yaml(path, DataConfig)


def _operation(command: str, config: DataConfig, inputs: dict[str, object]) -> dict[str, object]:
    return {"command": command, "config": config.model_dump(mode="json"), "inputs": inputs}


def _tokenizer_command(command: str, config_path: Path, dry_run: bool, force: bool) -> None:
    try:
        config = load_yaml(config_path, TokenizerConfig)
        operation = {"command": f"tokenizer {command}", "config": config.model_dump(mode="json")}
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "output": str(config.output_dir),
                        "fingerprint": fingerprint(operation),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        functions = {
            "train": train_tokenizer,
            "evaluate": evaluate_tokenizer,
            "pack": pack_tokenizer,
        }
        result = functions[command](config, force=force)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@model_app.command("inspect")
def model_inspect(
    config_path: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path | None, typer.Option("--output")] = None,
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """정확한 파라미터 수와 가중치·AdamW 학습 메모리를 기록합니다."""
    try:
        from llmex.model import CausalLM

        config = load_yaml(config_path, ModelConfig)
        target = output or Path("artifacts") / "model" / config.name / "inspect.json"
        operation = {"command": "model inspect", "config": config.model_dump(mode="json")}
        if dry_run:
            typer.echo(
                json.dumps(
                    {"dry_run": True, "output": str(target), "fingerprint": fingerprint(operation)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        operation_fingerprint = prepare_output(target, operation, force=force)
        model = CausalLM(config)
        estimate = model.memory_estimate()
        result: dict[str, object] = {
            "schema_version": 1,
            "model": config.name,
            "config": config.model_dump(mode="json"),
            "fingerprint": operation_fingerprint,
            **estimate,
            "weight_tying": model.lm_head.weight is model.token_embedding.weight,
        }
        write_json(target, result)
        write_json(target.with_name("resolved-config.json"), config.model_dump(mode="json"))
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@model_app.command("export-hf")
def model_export_hf(
    config_path: Annotated[Path, typer.Option("--config")],
    checkpoint: Annotated[Path, typer.Option("--checkpoint")],
    expected_checkpoint_sha256: Annotated[str, typer.Option("--expected-checkpoint-sha256")],
    output_dir: Annotated[Path, typer.Option("--output-dir")],
) -> None:
    """검증된 SFT checkpoint를 private HF Llama 디렉터리로 내보냅니다."""

    try:
        from llmex.model.export import export_hf

        config = load_yaml(config_path, SFTConfig)
        result = export_hf(config, checkpoint, expected_checkpoint_sha256, output_dir)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@model_app.command("export-gguf")
def model_export_gguf(
    hf_dir: Annotated[Path, typer.Option("--hf-dir")],
    expected_hf_manifest_sha256: Annotated[str, typer.Option("--expected-hf-manifest-sha256")],
    llama_cpp_dir: Annotated[Path, typer.Option("--llama-cpp-dir")],
    output: Annotated[Path, typer.Option("--output")],
    outtype: Annotated[str, typer.Option("--outtype")] = "f16",
) -> None:
    """HF Llama export를 llama.cpp 공식 converter로 GGUF로 변환합니다."""

    try:
        from llmex.model.export import export_gguf

        result = export_gguf(
            hf_dir,
            expected_hf_manifest_sha256,
            llama_cpp_dir,
            output,
            outtype=outtype,
        )
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


def _training_command(config_path: Path, resume: Path | None, dry_run: bool) -> None:
    try:
        config = load_yaml(config_path, TrainingConfig)
        operation = {"command": "train", "config": config.model_dump(mode="json")}
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "run_dir": str(config.run_dir),
                        "fingerprint": fingerprint(operation),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        from llmex.train import train

        result = train(config, resume=resume)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


def _m5_command(command: str, config_path: Path, dry_run: bool, prompt: str | None = None) -> None:
    try:
        config = load_yaml(config_path, EvaluationConfig)
        operation = {"command": command, "config": config.model_dump(mode="json"), "prompt": prompt}
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "command": command,
                        "output_dir": str(config.output_dir),
                        "fingerprint": fingerprint(operation),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        from llmex.evaluation import benchmark, evaluate, generate

        if command == "generate":
            result = generate(config, prompt)
        elif command == "benchmark":
            result = benchmark(config)
        else:
            result = evaluate(config)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@app.command("eval")
def evaluation_run(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """checkpoint의 validation/test 손실·perplexity와 품질 평가를 실행합니다."""
    _m5_command("eval", config_path, dry_run)


@app.command("generate")
def generation_run(
    config_path: Annotated[Path, typer.Option("--config")],
    prompt: Annotated[
        str | None, typer.Option("--prompt", help="설정의 고정 prompt 대신 사용할 입력")
    ] = None,
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """greedy 또는 확률 sampling으로 checkpoint에서 텍스트를 생성합니다."""
    _m5_command("generate", config_path, dry_run, prompt)


@app.command("benchmark")
def benchmark_run(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """cache 추론 latency, 처리량과 CUDA peak memory를 측정합니다."""
    _m5_command("benchmark", config_path, dry_run)


@train_app.command("run")
def training_run(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """새 학습 run을 시작합니다."""
    _training_command(config_path, None, dry_run)


@train_app.command("audit")
def training_audit(
    config_path: Annotated[Path, typer.Option("--config")],
) -> None:
    """완료 step/latest/best checkpoint의 무결성과 모델 유한성을 감사합니다."""
    try:
        config = load_yaml(config_path, TrainingConfig)
        from llmex.train.checkpoint import audit_checkpoints

        result = audit_checkpoints(config)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@train_app.command("resume")
def training_resume(
    config_path: Annotated[Path, typer.Option("--config")],
    checkpoint: Annotated[Path | None, typer.Option("--checkpoint")] = None,
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """latest 또는 지정 checkpoint의 모든 상태를 복구해 재개합니다."""
    try:
        config = load_yaml(config_path, TrainingConfig)
    except LlmexError as error:
        _emit_error(error)
    _training_command(config_path, checkpoint or config.run_dir / "checkpoints/latest.pt", dry_run)


@train_app.command("smoke")
def training_smoke(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """CPU/CUDA smoke 설정을 끝까지 학습하고 검증합니다."""
    _training_command(config_path, None, dry_run)


@tokenizer_app.command("train")
def tokenizer_train(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """train split만 읽어 byte-level BPE를 학습합니다."""
    _tokenizer_command("train", config_path, dry_run, force)


@tokenizer_app.command("evaluate")
def tokenizer_evaluate(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """압축률과 Unicode round-trip을 평가합니다."""
    _tokenizer_command("evaluate", config_path, dry_run, force)


@tokenizer_app.command("pack")
def tokenizer_pack(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """모든 split을 동일 tokenizer의 memmap shard로 패킹합니다."""
    _tokenizer_command("pack", config_path, dry_run, force)


@data_app.command("download")
def data_download(
    config_path: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path | None, typer.Option("--output")] = None,
    metadata_only: Annotated[
        bool, typer.Option(help="dumpstatus와 checksum만 수집합니다.")
    ] = False,
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """날짜 고정 metadata를 수집하고 Range resume로 immutable raw를 받습니다."""

    try:
        config = _data_config(config_path)
        target = output or config.paths.data / "raw" / Path(str(config.dump.url)).name
        operation = _operation(
            "download", config, {"url": str(config.dump.url), "metadata_only": metadata_only}
        )
        if dry_run:
            typer.echo(
                json.dumps(
                    {"dry_run": True, "output": str(target), "fingerprint": fingerprint(operation)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        if metadata_only:
            base = str(config.dump.url).rsplit("/", 1)[0]
            result = fetch_metadata(
                base, Path(str(config.dump.url)).name, timeout=config.download.timeout_seconds
            )
            metadata_path = target.with_name("wikimedia-metadata.json")
            prepare_output(metadata_path, operation, force=force)
            write_json(metadata_path, result)
            typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return
        prepare_output(target, operation, force=force)
        result = download(
            str(config.dump.url),
            target,
            expected_sha256=config.dump.sha256,
            timeout=config.download.timeout_seconds,
            retries=config.download.retries,
            backoff=config.download.retry_backoff_seconds,
            disk_overhead_ratio=config.download.disk_overhead_ratio,
        )
        manifest = raw_manifest(config, target, result)
        write_json(target.with_name(target.name + ".manifest.json"), manifest)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


def _stage(
    command: str,
    config_path: Path,
    input_path: Path,
    output: Path,
    dry_run: bool,
    force: bool,
    max_documents: int | None = None,
) -> None:
    from collections import Counter

    try:
        config = _data_config(config_path)
        inputs: dict[str, object] = {"input": str(input_path), "sha256": sha256_file(input_path)}
        if max_documents is not None:
            inputs["max_documents"] = max_documents
        operation = _operation(command, config, inputs)
        if dry_run:
            typer.echo(
                json.dumps(
                    {"dry_run": True, "output": str(output), "fingerprint": fingerprint(operation)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        prepare_output(output, operation, force=force)
        stats: Counter[str] = Counter()
        if command == "extract":
            rows = extract_rows(config, input_path, max_documents=max_documents)
        elif command == "clean":
            rows = clean_rows(config, read_jsonl_zst(input_path), stats)
        elif command == "dedup":
            rows = dedup_rows(config, read_jsonl_zst(input_path), stats)
        elif command == "split":
            rows = split_rows(config, read_jsonl_zst(input_path), stats)
        else:
            raise AssertionError(command)
        count = write_jsonl_zst(output, rows)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(
        json.dumps(
            {"output": str(output), "documents": count, "stats": stats},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


@data_app.command("extract")
def data_extract(
    config_path: Annotated[Path, typer.Option("--config")],
    input_path: Annotated[Path, typer.Option("--input")],
    output: Annotated[Path, typer.Option("--output")],
    max_documents: Annotated[int | None, typer.Option("--max-documents", min=1)] = None,
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """namespace 0, 비 redirect, 최신 revision을 streaming 추출합니다."""
    _stage("extract", config_path, input_path, output, dry_run, force, max_documents)


@data_app.command("clean")
def data_clean(
    config_path: Annotated[Path, typer.Option("--config")],
    input_path: Annotated[Path, typer.Option("--input")],
    output: Annotated[Path, typer.Option("--output")],
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """markup 정책, Unicode 정규화와 품질 필터를 적용합니다."""
    _stage("clean", config_path, input_path, output, dry_run, force)


@data_app.command("dedup")
def data_dedup(
    config_path: Annotated[Path, typer.Option("--config")],
    input_path: Annotated[Path, typer.Option("--input")],
    output: Annotated[Path, typer.Option("--output")],
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """exact 및 선택적 MinHash near-dedup을 수행합니다."""
    _stage("dedup", config_path, input_path, output, dry_run, force)


@data_app.command("split")
def data_split(
    config_path: Annotated[Path, typer.Option("--config")],
    input_path: Annotated[Path, typer.Option("--input")],
    output: Annotated[Path, typer.Option("--output")],
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """document hash로 train/validation/test를 결정합니다."""
    _stage("split", config_path, input_path, output, dry_run, force)


@data_app.command("report")
def data_report(
    config_path: Annotated[Path, typer.Option("--config")],
    input_path: Annotated[Path, typer.Option("--input")],
    output: Annotated[Path, typer.Option("--output")],
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """schema/attribution/split을 검증하고 data manifest/report를 생성합니다."""
    try:
        config = _data_config(config_path)
        operation = _operation(
            "report", config, {"input": str(input_path), "sha256": sha256_file(input_path)}
        )
        if dry_run:
            typer.echo(
                json.dumps(
                    {"dry_run": True, "output": str(output), "fingerprint": fingerprint(operation)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        prepare_output(output, operation, force=force)
        from collections import Counter

        stats: Counter[str] = Counter()
        for row in read_jsonl_zst(input_path):
            from llmex.data.schema import Document

            document = Document.model_validate(row)
            document.attribution()
            stats["documents"] += 1
            stats[f"split_{document.split}"] += 1
        report = build_report(
            config, input_path, stats, input_fingerprint=sha256_file(input_path), max_documents=None
        )
        write_json(output, report)
        output.with_suffix(".md").write_text(report_markdown(report), encoding="utf-8")
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(report, ensure_ascii=False, sort_keys=True))


@data_app.command("sample-e2e")
def data_sample_e2e(
    config_path: Annotated[Path, typer.Option("--config")],
    input_path: Annotated[Path, typer.Option("--input")],
    output_dir: Annotated[Path, typer.Option("--output-dir")],
    max_documents: Annotated[int | None, typer.Option("--max-documents", min=1)] = None,
    dry_run: Annotated[bool, typer.Option()] = False,
    force: Annotated[bool, typer.Option()] = False,
) -> None:
    """전체 M1 단계를 실행하고 manifest/report/100건 감사 표본을 만듭니다."""
    try:
        config = _data_config(config_path)
        marker = output_dir / "data-manifest.json"
        operation = _operation(
            "sample-e2e",
            config,
            {
                "input": str(input_path),
                "sha256": sha256_file(input_path),
                "max_documents": max_documents,
            },
        )
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "output": str(output_dir),
                        "fingerprint": fingerprint(operation),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        prepare_output(marker, operation, force=force)
        report = run_e2e(config, input_path, output_dir, max_documents=max_documents)
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(report, ensure_ascii=False, sort_keys=True))


@data_app.command("multilingual-prompts")
def data_multilingual_prompts(
    output: Annotated[Path, typer.Option("--output")] = Path(
        "data/chat/multilingual-teacher-prompts-v1"
    ),
    train_rows_per_task: Annotated[int, typer.Option("--train-rows-per-task")] = 150,
    heldout_rows_per_task: Annotated[int, typer.Option("--heldout-rows-per-task")] = 30,
) -> None:
    """Qwen·Gemma용 영어·일본어 대화/번역 prompt inventory를 생성합니다."""
    try:
        from llmex.chat.multilingual import prepare_multilingual_prompts

        result = prepare_multilingual_prompts(
            output,
            train_rows_per_task=train_rows_per_task,
            heldout_rows_per_task=heldout_rows_per_task,
        )
    except LlmexError as error:
        _emit_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))
