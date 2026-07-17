"""출력 디렉터리 단위의 회수 가능한 배타 lock."""

import fcntl
import json
import os
import socket
from collections.abc import Generator, Mapping
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmex.errors import ConflictError, IntegrityError


def _write_lock(descriptor: int, value: Mapping[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    os.write(descriptor, payload)
    os.fsync(descriptor)


def _pid_is_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


@contextmanager
def exclusive_run_lock(
    directory: Path, *, filename: str, label: str
) -> Generator[None, None, None]:
    """같은 host의 종료된 PID lock만 회수하고 나머지는 실패 폐쇄한다."""

    path = directory / filename
    local_host = socket.gethostname()
    descriptor = -1
    created = False
    try:
        directory.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            created = True
        except FileExistsError:
            descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            raw = os.read(descriptor, 16_384)
            previous = json.loads(raw)
            previous_pid = previous.get("pid")
            previous_host = previous.get("host")
            if (
                previous.get("schema_version") != 2
                or not isinstance(previous_pid, int)
                or previous_pid <= 0
                or not isinstance(previous_host, str)
                or previous_host != local_host
                or _pid_is_live(previous_pid)
            ):
                raise ConflictError(f"live 또는 회수 불가 {label} lock: {directory}") from None
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.read(descriptor, 16_384) != raw:
                raise ConflictError(f"{label} lock이 검사 중 변경되었습니다: {directory}") from None
        if created:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _write_lock(
            descriptor,
            {
                "schema_version": 2,
                "pid": os.getpid(),
                "host": local_host,
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
    except ConflictError:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise ConflictError(f"회수할 수 없는 {label} lock: {directory}") from exc

    try:
        yield
    finally:
        try:
            current = os.stat(path, follow_symlinks=False)
            held = os.fstat(descriptor)
            if current.st_dev == held.st_dev and current.st_ino == held.st_ino:
                path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise IntegrityError(f"{label} lock 정리에 실패했습니다: {directory}") from exc
        finally:
            try:
                os.close(descriptor)
            except OSError as exc:
                raise IntegrityError(f"{label} lock 닫기에 실패했습니다: {directory}") from exc
