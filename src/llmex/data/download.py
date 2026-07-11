"""날짜 고정 Wikimedia metadata와 복구 가능한 downloader."""

import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from llmex.errors import InputError, IntegrityError
from llmex.fingerprint import sha256_file


def fetch_metadata(base_url: str, filename: str, *, timeout: float) -> dict[str, Any]:
    """dumpstatus와 SHA256SUMS를 수집하고 대상 파일 상태/checksum을 반환한다."""

    def read(name: str) -> bytes:
        with urllib.request.urlopen(base_url.rstrip("/") + "/" + name, timeout=timeout) as response:
            return response.read()

    status = json.loads(read("dumpstatus.json"))
    sums = read("SHA256SUMS").decode("utf-8")
    matches = [
        line.split()[0] for line in sums.splitlines() if line.split()[-1].lstrip("*") == filename
    ]
    if len(matches) != 1 or len(matches[0]) != 64:
        raise IntegrityError(f"SHA256SUMS에서 대상을 찾지 못했습니다: {filename}")
    return {
        "schema_version": 1,
        "base_url": base_url,
        "filename": filename,
        "sha256": matches[0],
        "status": status,
    }


def download(
    url: str,
    destination: Path,
    *,
    expected_sha256: str,
    timeout: float,
    retries: int,
    backoff: float,
    disk_overhead_ratio: float,
) -> dict[str, Any]:
    """HTTP Range로 `.part`를 이어받고 checksum 후 immutable raw 파일로 승격한다."""

    if destination.exists():
        actual = sha256_file(destination)
        if actual != expected_sha256:
            raise IntegrityError(f"immutable raw checksum 불일치: {destination}")
        return {
            "path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": actual,
            "resumed_from": 0,
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    resumed_from = partial.stat().st_size if partial.exists() else 0
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            headers = {"Range": f"bytes={partial.stat().st_size}-"} if partial.exists() else {}
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                current = partial.stat().st_size if partial.exists() else 0
                append = current > 0 and response.status == 206
                if current > 0 and not append:
                    current = 0
                length = int(response.headers.get("Content-Length", "0"))
                required = int((current + length) * disk_overhead_ratio)
                if shutil.disk_usage(destination.parent).free < required:
                    raise InputError(f"다운로드 저장공간이 부족합니다: 필요 {required} bytes")
                with partial.open("ab" if append else "wb") as stream:
                    shutil.copyfileobj(response, stream, length=1024 * 1024)
            break
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt == retries:
                raise InputError(f"다운로드 재시도 소진: {url}: {exc}") from exc
            time.sleep(backoff * (2**attempt))
    if last_error is not None and not partial.exists():
        raise InputError(f"다운로드 실패: {last_error}")
    actual = sha256_file(partial)
    if actual != expected_sha256:
        raise IntegrityError(f"다운로드 checksum 불일치: 기대 {expected_sha256}, 실제 {actual}")
    partial.replace(destination)
    destination.chmod(0o444)
    return {
        "path": str(destination),
        "bytes": destination.stat().st_size,
        "sha256": actual,
        "resumed_from": resumed_from,
    }
