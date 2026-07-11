"""파일과 직렬화 가능한 값의 결정적 fingerprint."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from llmex.errors import InputError


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """파일을 스트리밍하며 SHA-256을 계산한다."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(chunk_size):
                digest.update(chunk)
    except OSError as exc:
        raise InputError(f"입력 파일을 읽을 수 없습니다: {path}: {exc}") from exc
    return digest.hexdigest()


def fingerprint(value: Mapping[str, Any]) -> str:
    """키 순서를 정규화한 JSON 값의 SHA-256을 계산한다."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()
