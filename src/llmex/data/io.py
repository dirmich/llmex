"""원자적 JSON/JSONL.ZST 입출력과 fingerprint 충돌 보호."""

import json
import os
import shutil
import subprocess
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from llmex.errors import ConflictError, InputError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """파일과 디렉터리를 fsync한 뒤 원자적으로 교체한다."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_output(path: Path, operation: Mapping[str, Any], *, force: bool) -> str:
    """동일 fingerprint만 재사용하며 다른 작업의 덮어쓰기를 거부한다."""

    value = fingerprint(operation)
    sidecar = path.with_suffix(path.suffix + ".fingerprint.json")
    if path.exists():
        if not sidecar.exists():
            raise ConflictError(f"fingerprint가 없는 기존 출력을 덮어쓸 수 없습니다: {path}")
        previous = json.loads(sidecar.read_text(encoding="utf-8"))
        if previous.get("fingerprint") != value:
            raise ConflictError(f"기존 출력과 fingerprint가 충돌합니다: {path}")
        if not force:
            raise ConflictError(f"출력이 이미 존재합니다(--force로 동일 작업 재생성): {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(
        sidecar,
        (
            json.dumps(
                {"schema_version": 1, "fingerprint": value, "operation": operation},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
    )
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write_bytes(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def verify_artifact_contract(path: Path, sidecar: Path) -> None:
    """artifact/sidecar의 schema, fingerprint, checksum 결속을 검증한다."""

    try:
        value = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"artifact sidecar를 검증할 수 없습니다: {sidecar}") from exc
    if value.get("schema_version") != 1 or value.get("sha256") != sha256_file(path):
        raise IntegrityError(f"artifact sidecar 계약 불일치: {path}")


def write_jsonl_zst(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    """외부 Python 의존성 없이 시스템 zstd로 결정적 JSONL.ZST를 쓴다."""

    executable = shutil.which("zstd")
    if executable is None:
        raise InputError("JSONL.ZST 기록에 zstd 실행 파일이 필요합니다")
    temporary = path.with_suffix(path.suffix + ".tmp")
    process = subprocess.Popen(
        [executable, "-q", "-f", "-T1", "-3", "-o", str(temporary)],
        stdin=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdin is not None
    count = 0
    try:
        for row in rows:
            process.stdin.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            )
            count += 1
        process.stdin.close()
        if process.wait() != 0:
            raise IntegrityError(f"zstd 기록에 실패했습니다: {path}")
    except BaseException:
        process.kill()
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(path)
    return count


def read_jsonl_zst(path: Path) -> Iterator[dict[str, Any]]:
    executable = shutil.which("zstd")
    if executable is None:
        raise InputError("JSONL.ZST 읽기에 zstd 실행 파일이 필요합니다")
    process = subprocess.Popen(
        [executable, "-q", "-d", "-c", str(path)],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    for line in process.stdout:
        value = json.loads(line)
        if not isinstance(value, dict):
            process.kill()
            raise IntegrityError(f"JSONL 행이 객체가 아닙니다: {path}")
        yield value
    if process.wait() != 0:
        raise IntegrityError(f"zstd 읽기에 실패했습니다: {path}")
