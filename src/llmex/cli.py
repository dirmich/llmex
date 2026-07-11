"""LLMEX 명령행 인터페이스."""

import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Never

import typer

from llmex import __version__
from llmex.config import DataConfig, ModelConfig, StrictModel, load_yaml
from llmex.errors import ExitCode, LlmexError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.logging import configure_logging
from llmex.paths import project_root
from llmex.run import create_run

app = typer.Typer(
    name="llmex",
    help="한국어 Wikipedia 기반 소형 언어 모델 실험 도구",
    no_args_is_help=True,
    invoke_without_command=True,
)
config_app = typer.Typer(help="YAML 설정을 검증합니다.", no_args_is_help=True)
fingerprint_app = typer.Typer(help="입력 fingerprint를 계산합니다.", no_args_is_help=True)
run_app = typer.Typer(help="재현 가능한 실행 디렉터리를 관리합니다.", no_args_is_help=True)
app.add_typer(config_app, name="config")
app.add_typer(fingerprint_app, name="fingerprint")
app.add_typer(run_app, name="run")


class ConfigKind(StrEnum):
    """지원하는 M0 설정 종류."""

    DATA = "data"
    MODEL = "model"


def _model(kind: ConfigKind) -> type[StrictModel]:
    return DataConfig if kind is ConfigKind.DATA else ModelConfig


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
