"""M6 재개 가능한 파이프라인, 자원·외부 증거·예산 게이트."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
import platform
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

from llmex.config import PipelineConfig, PipelineStageConfig
from llmex.data.io import atomic_write_bytes, write_json
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.trust import CANONICAL_COMMIT, repository_commit, verify_statement


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
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IntegrityError("pipeline 상태가 손상되었습니다") from exc
        if not isinstance(value, dict) or value.get("schema_version") != 2:
            raise IntegrityError("pipeline 상태 schema가 손상되었습니다")
        if value.get("config_fingerprint") != fingerprint(config.model_dump(mode="json")):
            raise IntegrityError("기존 pipeline 상태와 설정 fingerprint가 다릅니다")
        return value
    return {
        "schema_version": 2,
        "config_fingerprint": fingerprint(config.model_dump(mode="json")),
        "상태": "대기",
        "단계": {},
    }


def _validate_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"JSON evidence/output이 손상되었습니다: {path}") from exc
    if not isinstance(value, dict) or not value:
        raise IntegrityError(f"빈 JSON object는 evidence/output이 아닙니다: {path}")
    return value


def _validate_evidence(path: Path, config_fp: str, repository: Path, commit: str) -> dict[str, Any]:
    value = _validate_json(path)
    required = {
        "schema_version",
        "kind",
        "issuer",
        "role",
        "issued_at",
        "expires_at",
        "subject",
        "artifact",
        "signature",
    }
    if value.get("schema_version") != 1 or not required.issubset(value):
        raise IntegrityError(f"구조화 evidence schema/필드 누락: {path}")
    subject, artifact = value["subject"], value["artifact"]
    if (
        not isinstance(subject, dict)
        or subject.get("config_fingerprint") != config_fp
        or subject.get("git_commit") != commit
        or not CANONICAL_COMMIT.fullmatch(str(subject.get("git_commit", "")))
    ):
        raise IntegrityError(f"evidence commit/config fingerprint 불일치: {path}")
    if not isinstance(artifact, dict):
        raise IntegrityError(f"evidence artifact 누락: {path}")
    target = path.parent / str(artifact.get("path", ""))
    if not target.is_file() or artifact.get("sha256") != sha256_file(target):
        raise IntegrityError(f"evidence artifact checksum 불일치: {path}")
    if not isinstance(artifact.get("sha256"), str) or not isinstance(artifact.get("path"), str):
        raise IntegrityError(f"evidence artifact schema 불일치: {path}")
    verify_statement(
        value,
        repository=repository,
        expected_role="baseline",
        expected_kind="baseline-evidence",
        signed_payload={key: item for key, item in value.items() if key != "signature"},
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "kind": value["kind"],
        "artifact_sha256": artifact["sha256"],
    }


def _output_records(stage: PipelineStageConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in stage.outputs:
        if not path.is_file() or path.stat().st_size == 0:
            raise IntegrityError(f"pipeline 출력 누락/빈 파일: {path}")
        schema: int | None = None
        if path.suffix == ".json":
            value = _validate_json(path)
            raw_schema = value.get("schema_version")
            if not isinstance(raw_schema, int):
                raise IntegrityError(f"stage JSON output schema_version 누락: {path}")
            schema = raw_schema
        records.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "schema_version": schema,
            }
        )
    return records


def _outputs_valid(stage: PipelineStageConfig, previous: dict[str, Any]) -> bool:
    try:
        return previous.get("outputs") == _output_records(stage)
    except IntegrityError:
        return False


def _usage(
    config: PipelineConfig,
    *,
    authoritative: bool = False,
    repository: Path | None = None,
    commit: str | None = None,
    config_fp: str | None = None,
) -> dict[str, float]:
    path = config.run_dir / "resource-usage.json"
    if not path.is_file():
        if authoritative:
            raise IntegrityError("외부 stage의 최종 서명 resource telemetry가 없습니다")
        return {"tokens": 0.0, "energy_kwh": 0.0}
    value = _validate_json(path)
    try:
        usage = {"tokens": float(value["tokens"]), "energy_kwh": float(value["energy_kwh"])}
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrityError("resource usage telemetry가 유효하지 않습니다") from exc
    if authoritative:
        subject = value.get("subject")
        if (
            value.get("schema_version") != 1
            or value.get("final") is not True
            or not isinstance(subject, dict)
            or subject.get("git_commit") != commit
            or subject.get("config_fingerprint") != config_fp
            or repository is None
        ):
            raise IntegrityError("외부 stage telemetry schema/최종성/대상 결속이 유효하지 않습니다")
        verify_statement(
            value,
            repository=repository,
            expected_role="baseline",
            expected_kind="resource-usage",
            signed_payload={key: item for key, item in value.items() if key != "signature"},
        )
    return usage


def _execute(
    stage: PipelineStageConfig, config: PipelineConfig, deadline: float
) -> tuple[subprocess.Popen[str], float]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise IntegrityError("pipeline 시간 예산이 소진되었습니다")
    process = subprocess.Popen(
        stage.command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    started = time.monotonic()
    while process.poll() is None:
        usage = _usage(config)
        if (
            usage["tokens"] > config.budget.token_budget
            or usage["energy_kwh"] > config.budget.maximum_energy_kwh
        ):
            process.terminate()
            process.wait(timeout=5)
            raise IntegrityError("pipeline token/energy 예산을 실행 중 초과했습니다")
        if (
            time.monotonic() - started > min(stage.timeout_seconds, remaining)
            or time.monotonic() >= deadline
        ):
            process.terminate()
            process.wait(timeout=5)
            raise IntegrityError("pipeline stage/time 예산을 실행 중 초과했습니다")
        time.sleep(0.02)
    return process, time.monotonic() - started


def run(config: PipelineConfig, *, allow_external: bool = False) -> dict[str, Any]:
    config.run_dir.mkdir(parents=True, exist_ok=True)
    check = preflight(config)
    write_json(config.run_dir / "preflight.json", check)
    if check["판정"] != "통과":
        raise IntegrityError("자원 preflight가 실패했습니다")
    state = _read_state(config)
    config_fp = cast(str, state["config_fingerprint"])
    repository, commit = repository_commit(config.subject_repository)
    evidence: list[dict[str, Any]] = []
    evidence_errors: list[str] = []
    for path in config.required_evidence:
        try:
            evidence.append(_validate_evidence(path, config_fp, repository, commit))
        except IntegrityError as exc:
            evidence_errors.append(str(exc))
    state.update({"상태": "실행 중", "외부_증거_오류": evidence_errors})
    write_json(_state_path(config), state)
    deadline = time.monotonic() + config.budget.maximum_hours * 3600
    for stage in config.stages:
        previous = cast(dict[str, Any], state["단계"].get(stage.name, {}))
        telemetry_error: str | None = None
        if stage.external:
            try:
                _usage(
                    config,
                    authoritative=True,
                    repository=repository,
                    commit=commit,
                    config_fp=config_fp,
                )
            except IntegrityError as exc:
                telemetry_error = str(exc)
        if stage.external and (
            not allow_external
            or evidence_errors
            or len(evidence) != len(config.required_evidence)
            or telemetry_error is not None
        ):
            state["단계"][stage.name] = {
                "상태": "외부 게이트 대기",
                "명령": stage.command,
                "telemetry_error": telemetry_error,
            }
            continue
        if previous.get("상태") == "통과" and _outputs_valid(stage, previous):
            continue
        process, elapsed = _execute(stage, config, deadline)
        stdout, stderr = process.communicate()
        record: dict[str, Any] = {
            "상태": "통과" if process.returncode == 0 else "실패",
            "returncode": process.returncode,
            "elapsed_seconds": elapsed,
            "명령": stage.command,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-4000:],
        }
        if process.returncode == 0:
            try:
                record["outputs"] = _output_records(stage)
            except IntegrityError as exc:
                record.update({"상태": "실패", "output_error": str(exc)})
        state["단계"][stage.name] = record
        write_json(_state_path(config), state)
        if record["상태"] == "실패":
            state["상태"] = "실패"
            write_json(_state_path(config), state)
            raise IntegrityError(f"pipeline 단계가 실패했습니다: {stage.name}")
    waiting = any(item["상태"] == "외부 게이트 대기" for item in state["단계"].values())
    state.update(
        {
            "상태": "외부 게이트 대기" if waiting else "완료",
            "증거": evidence,
            "resource_usage": _usage(config),
            "재개_명령": "uv run llmex pipeline run --config <동일-config.yaml>",
        }
    )
    write_json(_state_path(config), state)
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "config": config.model_dump(mode="json"),
        "config_fingerprint": config_fp,
        "status_sha256": sha256_file(_state_path(config)),
        "증거": evidence,
        "완료": state["상태"] == "완료",
    }
    manifest["fingerprint"] = fingerprint(manifest)
    write_json(config.run_dir / "run-manifest.json", manifest)
    write_json(config.run_dir / f"run-manifest-{manifest['fingerprint']}.json", manifest)
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
    atomic_write_bytes(config.run_dir / "dashboard.md", ("\n".join(rows) + "\n").encode())
    return payload


def recovery_drill(config: PipelineConfig) -> dict[str, Any]:
    """실제 subprocess 중단, partial 손상, 정리와 재개를 검증한다."""
    drill = config.run_dir / ".recovery-drill"
    drill.mkdir(parents=True, exist_ok=True)
    partial, final = drill / "partial.json", drill / "final.json"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"import pathlib,time; pathlib.Path({str(partial)!r}).write_text('{{'); time.sleep(30)",
        ]
    )
    for _ in range(100):
        if partial.exists():
            break
        time.sleep(0.01)
    process.terminate()
    process.wait(timeout=5)
    interrupted = process.returncode != 0 and partial.exists()
    try:
        json.loads(partial.read_text())
    except (json.JSONDecodeError, OSError):
        corrupted = True
    else:
        corrupted = False
    partial.unlink(missing_ok=True)
    resumed = (
        subprocess.run(
            [
                sys.executable,
                "-c",
                f"import json,pathlib; pathlib.Path({str(final)!r}).write_text(json.dumps({{'schema_version':1,'resumed':True}}))",  # noqa: E501
            ],
            check=False,
        ).returncode
        == 0
    )
    verified = _validate_json(final).get("resumed") is True
    result = {
        "schema_version": 1,
        "판정": "통과" if interrupted and corrupted and resumed and verified else "실패",
        "중단": interrupted,
        "손상_탐지": corrupted,
        "partial_정리": not partial.exists(),
        "재개": resumed and verified,
        "final_sha256": sha256_file(final),
    }
    write_json(config.run_dir / "recovery-drill.json", result)
    return result
