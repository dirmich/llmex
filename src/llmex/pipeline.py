"""M6 재개 가능한 파이프라인, 자원·외부 증거 게이트와 보고서."""

import json
import platform
import resource
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from llmex.config import PipelineConfig
from llmex.data.io import write_json
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file


def _memory() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0]) * 1024
    except OSError:
        pass
    return {
        "total_bytes": values.get("MemTotal", 0),
        "available_bytes": values.get("MemAvailable", 0),
        "swap_total_bytes": values.get("SwapTotal", 0),
        "swap_free_bytes": values.get("SwapFree", 0),
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }


def preflight(config: PipelineConfig) -> dict[str, Any]:
    disk = shutil.disk_usage(config.run_dir.parent)
    memory = _memory()
    gib = 1024**3
    checks = {
        "disk": disk.free >= config.budget.minimum_free_disk_gib * gib,
        "memory": memory["available_bytes"] >= config.budget.minimum_available_memory_gib * gib,
        "parameter_cap": config.baseline_parameters <= config.budget.maximum_parameters,
        "large_model_blocked": config.budget.maximum_parameters <= 120_000_000,
    }
    return {
        "schema_version": 1,
        "판정": "통과" if all(checks.values()) else "실패",
        "검사": checks,
        "환경": {"architecture": platform.machine(), "platform": platform.platform()},
        "저장공간": {"free_bytes": disk.free, "total_bytes": disk.total},
        "메모리": memory,
        "예산": config.budget.model_dump(mode="json"),
    }


def _state_path(config: PipelineConfig) -> Path:
    return config.run_dir / "pipeline-status.json"


def _read_state(config: PipelineConfig) -> dict[str, Any]:
    path = _state_path(config)
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("config_fingerprint") != fingerprint(config.model_dump(mode="json")):
            raise IntegrityError("기존 pipeline 상태와 설정 fingerprint가 다릅니다")
        return value
    return {
        "schema_version": 1,
        "config_fingerprint": fingerprint(config.model_dump(mode="json")),
        "상태": "대기",
        "단계": {},
    }


def _evidence(config: PipelineConfig) -> list[dict[str, Any]]:
    return [
        {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in config.required_evidence
        if path.is_file()
    ]


def run(config: PipelineConfig, *, allow_external: bool = False) -> dict[str, Any]:
    config.run_dir.mkdir(parents=True, exist_ok=True)
    check = preflight(config)
    write_json(config.run_dir / "preflight.json", check)
    if check["판정"] != "통과":
        raise IntegrityError("자원 preflight가 실패했습니다")
    missing = [str(path) for path in config.required_evidence if not path.is_file()]
    state = _read_state(config)
    state["상태"] = "실행 중"
    state["외부_증거_누락"] = missing
    write_json(_state_path(config), state)
    started = time.monotonic()
    for stage in config.stages:
        previous = state["단계"].get(stage.name, {})
        if previous.get("상태") == "통과" and all(path.exists() for path in stage.outputs):
            continue
        if stage.external and (not allow_external or missing):
            state["단계"][stage.name] = {"상태": "외부 게이트 대기", "명령": stage.command}
            continue
        before = time.monotonic()
        completed = subprocess.run(
            stage.command, text=True, capture_output=True, timeout=stage.timeout_seconds
        )
        record: dict[str, Any] = {
            "상태": "통과" if completed.returncode == 0 else "실패",
            "returncode": completed.returncode,
            "elapsed_seconds": time.monotonic() - before,
            "명령": stage.command,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
        if completed.returncode == 0:
            absent = [str(path) for path in stage.outputs if not path.exists()]
            if absent:
                record["상태"] = "실패"
                record["누락_출력"] = absent
        state["단계"][stage.name] = record
        write_json(_state_path(config), state)
        if record["상태"] == "실패":
            state["상태"] = "실패"
            write_json(_state_path(config), state)
            raise IntegrityError(f"pipeline 단계가 실패했습니다: {stage.name}")
        if (time.monotonic() - started) / 3600 > config.budget.maximum_hours:
            raise IntegrityError("pipeline 실행 시간이 승인 예산을 초과했습니다")
    waiting = any(item["상태"] == "외부 게이트 대기" for item in state["단계"].values())
    state["상태"] = "외부 게이트 대기" if waiting else "완료"
    state["증거"] = _evidence(config)
    state["재개_명령"] = "uv run llmex pipeline run --config <동일-config.yaml>"
    write_json(_state_path(config), state)
    manifest = {
        "schema_version": 1,
        "config": config.model_dump(mode="json"),
        "config_fingerprint": state["config_fingerprint"],
        "status_sha256": sha256_file(_state_path(config)),
        "증거": state["증거"],
        "완료": state["상태"] == "완료",
    }
    manifest["fingerprint"] = fingerprint(manifest)
    write_json(config.run_dir / "run-manifest.json", manifest)
    immutable_path = config.run_dir / f"run-manifest-{manifest['fingerprint']}.json"
    if immutable_path.exists():
        previous = json.loads(immutable_path.read_text(encoding="utf-8"))
        if previous != manifest:
            raise IntegrityError("불변 run manifest fingerprint 충돌이 발생했습니다")
    else:
        write_json(immutable_path, manifest)
    return state


def export(config: PipelineConfig) -> dict[str, Any]:
    state = _read_state(config)
    metrics: list[dict[str, Any]] = []
    for path in config.run_dir.rglob("metrics.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            metrics.append(json.loads(line))
    payload = {"상태": state, "metrics": metrics, "metrics_count": len(metrics)}
    write_json(config.run_dir / "dashboard.json", payload)
    rows = [
        "# M6 실행 대시보드",
        "",
        f"- 전체 상태: **{state['상태']}**",
        "",
        "| 단계 | 상태 |",
        "|---|---|",
    ]
    rows.extend(f"| {name} | {item['상태']} |" for name, item in state["단계"].items())
    (config.run_dir / "dashboard.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return payload


def recovery_drill(config: PipelineConfig) -> dict[str, Any]:
    state = _read_state(config)
    before = fingerprint(state)
    temporary = config.run_dir / ".recovery-drill.tmp"
    temporary.write_text("의도적 중단", encoding="utf-8")
    temporary.unlink()
    after = fingerprint(_read_state(config))
    result = {"판정": "통과" if before == after else "실패", "상태_fingerprint": after}
    write_json(config.run_dir / "recovery-drill.json", result)
    return result
