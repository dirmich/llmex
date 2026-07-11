"""재현 가능한 실행 디렉터리와 manifest 생성."""

import json
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from llmex.errors import ConflictError
from llmex.fingerprint import fingerprint


@dataclass(frozen=True)
class RunInfo:
    """생성된 실행 디렉터리 정보."""

    path: Path
    fingerprint: str


def _git_revision(root: Path) -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        return {"commit": revision, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def create_run(
    *, name: str, config: dict[str, Any], runs_dir: Path, root: Path, force: bool = False
) -> RunInfo:
    """resolved config, 환경, Git 정보를 원자 충돌 규칙에 따라 기록한다."""

    config_fingerprint = fingerprint(config)
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{name}-{config_fingerprint[:8]}"
    path = runs_dir / run_id
    if path.exists() and not force:
        raise ConflictError(f"실행 디렉터리가 이미 존재합니다: {path}")
    path.mkdir(parents=True, exist_ok=force)
    (path / "resolved-config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "pid": os.getpid(),
        "config_fingerprint": config_fingerprint,
    }
    (path / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (path / "git.json").write_text(
        json.dumps(_git_revision(root), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RunInfo(path=path, fingerprint=config_fingerprint)
