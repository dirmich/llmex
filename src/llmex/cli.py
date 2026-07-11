"""LLMEX 명령행 인터페이스."""

import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Never

import typer

from llmex import __version__
from llmex.config import (
    DataConfig,
    ModelConfig,
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
app.add_typer(config_app, name="config")
app.add_typer(fingerprint_app, name="fingerprint")
app.add_typer(run_app, name="run")
app.add_typer(data_app, name="data")
app.add_typer(tokenizer_app, name="tokenizer")
app.add_typer(model_app, name="model")
app.add_typer(train_app, name="train")


class ConfigKind(StrEnum):
    """지원하는 M0 설정 종류."""

    DATA = "data"
    MODEL = "model"
    TOKENIZER = "tokenizer"
    TRAINING = "training"


def _model(kind: ConfigKind) -> type[StrictModel]:
    if kind is ConfigKind.DATA:
        return DataConfig
    if kind is ConfigKind.TOKENIZER:
        return TokenizerConfig
    if kind is ConfigKind.TRAINING:
        return TrainingConfig
    return ModelConfig


def _emit_error(error: LlmexError) -> Never:
    logging.getLogger("llmex").error(str(error), extra={"fields": {"error_code": error.code.name}})
    raise typer.Exit(code=int(error.code))


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


@train_app.command("run")
def training_run(
    config_path: Annotated[Path, typer.Option("--config")],
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """새 학습 run을 시작합니다."""
    _training_command(config_path, None, dry_run)


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
