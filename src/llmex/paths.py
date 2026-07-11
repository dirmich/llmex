"""저장소와 실행 경로 처리."""

import os
from pathlib import Path

MARKERS = ("pyproject.toml", ".git")


def project_root(start: Path | None = None) -> Path:
    """환경 변수 또는 상위 디렉터리 marker로 프로젝트 루트를 찾는다."""

    if configured := os.getenv("LLMEX_ROOT"):
        return Path(configured).expanduser().resolve()
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if all((candidate / marker).exists() for marker in MARKERS):
            return candidate
    raise RuntimeError("pyproject.toml과 .git이 있는 LLMEX 프로젝트 루트를 찾지 못했습니다")


def resolve_from_root(path: Path, root: Path | None = None) -> Path:
    """상대 경로를 프로젝트 루트 기준 절대 경로로 만든다."""

    if path.is_absolute():
        return path.resolve()
    return (root or project_root()) / path
