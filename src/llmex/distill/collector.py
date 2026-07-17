"""재개 가능한 teacher 수집, 강결속 export와 상태 schema v2."""

import hashlib
import json
import threading
import time
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from llmex.chat.data import load_chat_jsonl
from llmex.config import DistillationConfig
from llmex.data.io import atomic_write_bytes, write_json
from llmex.errors import ConflictError, InputError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.locking import exclusive_run_lock

from .client import (
    HttpFailure,
    completion,
    preflight_model,
    request_body,
    response_contains_secret,
)
from .filters import SAFETY_FILTER_SCOPE, canonical_response, filter_response
from .prompts import build_inventory
from .schema import LogicalRequest, SpoolRecord


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _config_fingerprint(config: DistillationConfig) -> str:
    return fingerprint(config.model_dump(mode="json"))


def _run_lock(run_dir: Path):
    return exclusive_run_lock(run_dir, filename=".distill.lock", label="distill")


def _manifest_path(config: DistillationConfig) -> Path:
    return config.run_dir / "run-manifest.json"


def _state_path(config: DistillationConfig) -> Path:
    return config.run_dir / "state.json"


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "started_at": None,
        "updated_at": None,
        "elapsed_seconds": 0.0,
        "last_success_at": None,
        "last_error_at": None,
    }


def _load_state(config: DistillationConfig) -> dict[str, Any]:
    path = _state_path(config)
    if not path.exists():
        return _empty_state()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("distill state가 손상되었습니다") from exc
    if value.get("schema_version") != 2:
        raise IntegrityError("distill state schema가 올바르지 않습니다")
    return value


def _save_state(config: DistillationConfig, value: Mapping[str, Any]) -> None:
    write_json(_state_path(config), value)


def _load_manifest(config: DistillationConfig) -> dict[str, Any]:
    path = _manifest_path(config)
    if not path.is_file():
        raise InputError("distill prepare를 먼저 실행해야 합니다")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("distill run manifest가 손상되었습니다") from exc
    if value.get("schema_version") != 2:
        raise ConflictError("distill run manifest schema가 v2가 아닙니다")
    if value.get("config_fingerprint") != _config_fingerprint(config):
        raise ConflictError("distill config fingerprint가 기존 실행과 다릅니다")
    inventory = config.run_dir / "inventory.jsonl"
    if not inventory.is_file() or value.get("inventory_sha256") != sha256_file(inventory):
        raise IntegrityError("distill inventory checksum이 다릅니다")
    return value


def _inventory(config: DistillationConfig) -> list[LogicalRequest]:
    manifest = _load_manifest(config)
    path = config.run_dir / "inventory.jsonl"
    values: list[LogicalRequest] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                values.append(LogicalRequest.model_validate(json.loads(line)))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise IntegrityError("distill inventory v2 schema가 손상되었습니다") from exc
    if len(values) != config.target_requests or len({item.id for item in values}) != len(values):
        raise IntegrityError("distill inventory 개수 또는 ID가 올바르지 않습니다")
    if len({item.prompt_sha256 for item in values}) != len(values):
        raise IntegrityError("distill inventory에 중복 prompt가 있습니다")
    expected_fingerprint = fingerprint(
        {"schema_version": 2, "rows": [item.model_dump(mode="json") for item in values]}
    )
    if manifest.get("inventory_fingerprint") != expected_fingerprint:
        raise IntegrityError("distill inventory fingerprint가 다릅니다")
    return values


def preflight(config: DistillationConfig) -> dict[str, Any]:
    return {**preflight_model(config), "schema_version": 2}


def prepare(config: DistillationConfig) -> dict[str, Any]:
    with _run_lock(config.run_dir):
        fingerprint_value = _config_fingerprint(config)
        if _manifest_path(config).exists():
            previous = _load_manifest(config)
            return {**previous, "reused": True}
        requests, summary = build_inventory(config)
        payload = "".join(
            json.dumps(
                item.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for item in requests
        ).encode("utf-8")
        inventory_path = config.run_dir / "inventory.jsonl"
        atomic_write_bytes(inventory_path, payload)
        manifest: dict[str, Any] = {
            **summary,
            "config_fingerprint": fingerprint_value,
            "inventory_sha256": sha256_file(inventory_path),
            "teacher": {"endpoint": config.endpoint, "model": config.model},
            "teacher_output_license": config.teacher_output_license,
            "redistribution_allowed": False,
            "release_gate": "blocked",
        }
        write_json(_manifest_path(config), manifest)
        _save_state(config, _empty_state())
        return manifest


def _spool_path(config: DistillationConfig, request_id: str) -> Path:
    return config.run_dir / "spool" / f"{request_id}.json"


def _record(value: Mapping[str, Any]) -> SpoolRecord:
    basis = dict(value)
    basis["record_sha256"] = fingerprint(basis)
    return SpoolRecord.model_validate(basis)


def _validate_spool_binding(
    record: SpoolRecord,
    item: LogicalRequest,
    config: DistillationConfig,
    config_fp: str,
) -> None:
    if record.config_fingerprint != config_fp:
        raise ConflictError("distill spool config fingerprint가 다릅니다")
    if record.request_id != item.id:
        raise IntegrityError("spool request ID가 logical request와 다릅니다")
    expected_request = hashlib.sha256(request_body(config, item.prompt)).hexdigest()
    if record.request_sha256 != expected_request:
        raise IntegrityError("spool request SHA가 logical request payload와 다릅니다")
    if record.attempts > config.max_attempts:
        raise IntegrityError("spool attempts가 max_attempts를 초과합니다")
    if record.response is not None:
        if record.response != record.response.strip():
            raise IntegrityError("spool response가 정규화되지 않았습니다")
        expected_response = hashlib.sha256(record.response.encode("utf-8")).hexdigest()
        if record.response_sha256 != expected_response or record.raw_response_sha256 is None:
            raise IntegrityError("spool response hash 조합이 올바르지 않습니다")
    elif record.response_sha256 is not None or record.raw_response_sha256 is not None:
        raise IntegrityError("응답 없는 spool에 response hash가 있습니다")
    if record.status == "accepted":
        if record.reason is not None or record.response is None:
            raise IntegrityError("accepted spool 조합이 올바르지 않습니다")
        if filter_response(item.prompt, record.response, config) is not None:
            raise IntegrityError("accepted spool이 현재 필터를 통과하지 못합니다")
    elif record.status == "rejected":
        if not record.reason:
            raise IntegrityError("rejected spool에 reason이 없습니다")
        if record.response is not None:
            expected_reason = filter_response(item.prompt, record.response, config)
            if expected_reason != record.reason:
                raise IntegrityError("rejected spool reason이 현재 필터와 다릅니다")
    elif not (
        record.reason == "retry_exhausted"
        and record.response is None
        and record.attempts == config.max_attempts
    ):
        raise IntegrityError("failed spool 조합이 올바르지 않습니다")


def _read_spool(
    path: Path, item: LogicalRequest, config: DistillationConfig, config_fp: str
) -> SpoolRecord:
    try:
        record = SpoolRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise IntegrityError(f"distill spool이 손상되었습니다: {path}") from exc
    _validate_spool_binding(record, item, config, config_fp)
    return record


def _write_spool(path: Path, record: SpoolRecord) -> None:
    atomic_write_bytes(
        path,
        (
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8"),
    )


class _RateLimiter:
    def __init__(self, requests_per_second: float, stop_event: threading.Event) -> None:
        self.interval = 1.0 / requests_per_second
        self.next_time = 0.0
        self.lock = threading.Lock()
        self.stop_event = stop_event

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next_time - now)
            self.next_time = max(now, self.next_time) + self.interval
        if delay and self.stop_event.wait(delay):
            raise InterruptedError("distill collection interrupted")


_RETRYABLE = {408, 409, 425, 429, *range(500, 600)}


def _jitter(identifier: str, attempt: int) -> float:
    digest = hashlib.sha256(f"{identifier}:{attempt}".encode()).digest()
    return int.from_bytes(digest[:2], "big") / 65535.0


def _collect_one(
    config: DistillationConfig,
    item: LogicalRequest,
    limiter: _RateLimiter,
    config_fp: str,
) -> SpoolRecord:
    body = request_body(config, item.prompt)
    request_sha = hashlib.sha256(body).hexdigest()
    for attempt in range(1, config.max_attempts + 1):
        limiter.wait()
        try:
            sent, response, raw = completion(config, item.prompt)
            if sent != body:
                raise IntegrityError("request payload가 실행 중 변경되었습니다")
            if response_contains_secret(config, response):
                return _record(
                    {
                        "schema_version": 2,
                        "request_id": item.id,
                        "config_fingerprint": config_fp,
                        "status": "rejected",
                        "reason": "secret_leak",
                        "attempts": attempt,
                        "request_sha256": request_sha,
                        "raw_response_sha256": None,
                        "response_sha256": None,
                        "response": None,
                    }
                )
            reason = filter_response(item.prompt, response, config)
            normalized = response.strip()
            return _record(
                {
                    "schema_version": 2,
                    "request_id": item.id,
                    "config_fingerprint": config_fp,
                    "status": "rejected" if reason else "accepted",
                    "reason": reason,
                    "attempts": attempt,
                    "request_sha256": request_sha,
                    "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
                    "response_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                    "response": normalized,
                }
            )
        except HttpFailure as exc:
            retryable = exc.status is None or exc.status in _RETRYABLE
            if not retryable:
                return _record(
                    {
                        "schema_version": 2,
                        "request_id": item.id,
                        "config_fingerprint": config_fp,
                        "status": "rejected",
                        "reason": f"http_{exc.status}",
                        "attempts": attempt,
                        "request_sha256": request_sha,
                        "raw_response_sha256": None,
                        "response_sha256": None,
                        "response": None,
                    }
                )
            if attempt < config.max_attempts:
                if exc.retry_after is None:
                    delay = config.retry_backoff_seconds * (2 ** (attempt - 1))
                    delay *= 0.5 + _jitter(item.id, attempt)
                else:
                    delay = exc.retry_after
                delay = min(delay, config.max_retry_delay_seconds)
                if limiter.stop_event.wait(delay):
                    raise InterruptedError("distill collection interrupted") from None
                continue
        except IntegrityError as exc:
            return _record(
                {
                    "schema_version": 2,
                    "request_id": item.id,
                    "config_fingerprint": config_fp,
                    "status": "rejected",
                    "reason": str(exc),
                    "attempts": attempt,
                    "request_sha256": request_sha,
                    "raw_response_sha256": None,
                    "response_sha256": None,
                    "response": None,
                }
            )
    return _record(
        {
            "schema_version": 2,
            "request_id": item.id,
            "config_fingerprint": config_fp,
            "status": "failed",
            "reason": "retry_exhausted",
            "attempts": config.max_attempts,
            "request_sha256": request_sha,
            "raw_response_sha256": None,
            "response_sha256": None,
            "response": None,
        }
    )


def _update_collection_state(
    config: DistillationConfig,
    state: dict[str, Any],
    session_start: float,
    previous_elapsed: float,
    record: SpoolRecord | None = None,
) -> None:
    current = _now()
    state["updated_at"] = current
    state["elapsed_seconds"] = previous_elapsed + time.monotonic() - session_start
    if record is not None:
        if record.status == "accepted":
            state["last_success_at"] = current
        elif record.status in {"rejected", "failed"}:
            state["last_error_at"] = current
    _save_state(config, state)


def _drain_completed(
    futures: Mapping[Future[SpoolRecord], LogicalRequest],
    config: DistillationConfig,
    written: set[Future[SpoolRecord]],
) -> None:
    for future, item in futures.items():
        if future in written or not future.done() or future.cancelled():
            continue
        try:
            record = future.result()
        except BaseException:
            continue
        _write_spool(_spool_path(config, item.id), record)
        written.add(future)


def collect(config: DistillationConfig) -> dict[str, Any]:
    with _run_lock(config.run_dir):
        requests = _inventory(config)
        config_fp = _config_fingerprint(config)
        pending: list[LogicalRequest] = []
        for item in requests:
            path = _spool_path(config, item.id)
            if path.exists():
                record = _read_spool(path, item, config, config_fp)
                if record.status != "failed":
                    continue
            pending.append(item)
        state = _load_state(config)
        previous_elapsed = float(state.get("elapsed_seconds", 0.0))
        session_start = time.monotonic()
        if state.get("started_at") is None:
            state["started_at"] = _now()
        _update_collection_state(config, state, session_start, previous_elapsed)
        stop_event = threading.Event()
        limiter = _RateLimiter(config.requests_per_second, stop_event)
        executor = ThreadPoolExecutor(max_workers=config.concurrency)
        iterator = iter(pending)
        futures: dict[Future[SpoolRecord], LogicalRequest] = {}
        written: set[Future[SpoolRecord]] = set()

        def submit_next() -> bool:
            try:
                item = next(iterator)
            except StopIteration:
                return False
            future = executor.submit(_collect_one, config, item, limiter, config_fp)
            futures[future] = item
            return True

        for _ in range(min(config.concurrency, len(pending))):
            submit_next()
        try:
            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    item = futures.pop(future)
                    record = future.result()
                    _write_spool(_spool_path(config, item.id), record)
                    written.add(future)
                    _update_collection_state(config, state, session_start, previous_elapsed, record)
                    submit_next()
        except BaseException:
            stop_event.set()
            for future in futures:
                future.cancel()
            _drain_completed(futures, config, written)
            executor.shutdown(wait=True, cancel_futures=True)
            _update_collection_state(config, state, session_start, previous_elapsed)
            raise
        else:
            executor.shutdown(wait=True, cancel_futures=True)
            _update_collection_state(config, state, session_start, previous_elapsed)
        result = status(config)
        return {**result, "called": len(pending), "skipped": len(requests) - len(pending)}


def _records(config: DistillationConfig, requests: list[LogicalRequest]) -> dict[str, SpoolRecord]:
    config_fp = _config_fingerprint(config)
    expected = {item.id: item for item in requests}
    spool_dir = config.run_dir / "spool"
    if spool_dir.exists():
        unexpected = {path.stem for path in spool_dir.glob("*.json")} - set(expected)
        if unexpected:
            raise IntegrityError("inventory에 없는 distill spool 파일이 있습니다")
    result: dict[str, SpoolRecord] = {}
    for item in requests:
        path = _spool_path(config, item.id)
        if path.exists():
            result[item.id] = _read_spool(path, item, config, config_fp)
    return result


def status(config: DistillationConfig) -> dict[str, Any]:
    requests = _inventory(config)
    records = _records(config, requests)
    counts: Counter[str] = Counter(record.status for record in records.values())
    reasons: Counter[str] = Counter(
        record.reason for record in records.values() if record.reason is not None
    )
    counts["pending"] = len(requests) - len(records)
    completed = sum(record.status != "failed" for record in records.values())
    state = _load_state(config)
    elapsed = float(state.get("elapsed_seconds", 0.0))
    processed = len(records)
    effective_rps = processed / elapsed if elapsed > 0 else 0.0
    remaining = counts["pending"] + counts["failed"]
    eta = remaining / effective_rps if effective_rps > 0 else None
    return {
        "schema_version": 2,
        "total": len(requests),
        "completed": completed,
        "progress": completed / len(requests),
        "counts": dict(sorted(counts.items())),
        "reasons": dict(sorted(reasons.items())),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
        "elapsed_seconds": elapsed,
        "effective_rps": effective_rps,
        "eta_seconds": eta,
        "last_success_at": state.get("last_success_at"),
        "last_error_at": state.get("last_error_at"),
    }


def _chat_row(
    config: DistillationConfig, item: LogicalRequest, record: SpoolRecord
) -> dict[str, Any]:
    assert record.response is not None
    provenance = {
        "dataset": f"llmex-{config.model}-distillation",
        "source": item.source.source,
        "license": config.teacher_output_license,
        "collected_at": config.source_collected_at,
        "source_dataset": item.source.dataset,
        "source_license": item.source.license,
        "teacher_model": config.model,
        "teacher_output_license": config.teacher_output_license,
        "request_sha256": record.request_sha256,
        "response_sha256": record.response_sha256,
        "raw_response_sha256": record.raw_response_sha256,
        "source_id": item.source.source_id,
        "source_sha256": item.source.source_sha256,
        "source_collected_at": item.source.collected_at,
        "source_metadata": item.source.metadata,
    }
    messages = [
        {"role": "user", "content": item.prompt},
        {"role": "assistant", "content": record.response},
    ]
    basis = {"id": item.id, "messages": messages, "provenance": provenance, "split": item.split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _export_material(
    config: DistillationConfig,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    run_manifest = _load_manifest(config)
    requests = _inventory(config)
    records = _records(config, requests)
    rows: dict[str, list[dict[str, Any]]] = {"train": [], "heldout": []}
    seen_responses: set[str] = set()
    duplicate_responses = 0
    rejected = 0
    incomplete = 0
    accepted_bindings: list[dict[str, str]] = []
    for item in requests:
        record = records.get(item.id)
        if record is None or record.status == "failed":
            incomplete += 1
            continue
        if record.status != "accepted" or record.response is None:
            rejected += 1
            continue
        accepted_bindings.append(
            {
                "id": item.id,
                "record_sha256": record.record_sha256,
                "request_sha256": record.request_sha256,
                "response_sha256": str(record.response_sha256),
                "raw_response_sha256": str(record.raw_response_sha256),
            }
        )
        canonical = canonical_response(record.response)
        if canonical in seen_responses:
            duplicate_responses += 1
            continue
        seen_responses.add(canonical)
        rows[item.split].append(_chat_row(config, item, record))
    payloads = {
        split: "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for value in values
        ).encode("utf-8")
        for split, values in rows.items()
    }
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "config_fingerprint": _config_fingerprint(config),
        "inventory_sha256": run_manifest["inventory_sha256"],
        "inventory_fingerprint": run_manifest["inventory_fingerprint"],
        "counts": {name: len(values) for name, values in rows.items()},
        "rejected": rejected,
        "incomplete": incomplete,
        "canonical_response_duplicates": duplicate_responses,
        "sha256": {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()},
        "accepted_spools": accepted_bindings,
        "accepted_spool_set_fingerprint": fingerprint({"accepted": accepted_bindings}),
        "source_licenses": sorted({item.source.license for item in requests}),
        "teacher_output_license": config.teacher_output_license,
        "redistribution_allowed": False,
        "release_gate": "blocked",
        "safety_filter_scope": SAFETY_FILTER_SCOPE,
    }
    return rows, manifest


def export(config: DistillationConfig) -> dict[str, Any]:
    with _run_lock(config.run_dir):
        rows, manifest = _export_material(config)
        output_dir = config.run_dir / "export"
        output_dir.mkdir(parents=True, exist_ok=True)
        for split, values in rows.items():
            payload = "".join(
                json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                for value in values
            ).encode("utf-8")
            atomic_write_bytes(output_dir / f"{split}.jsonl", payload)
        write_json(output_dir / "manifest.json", manifest)
        return manifest


def validate(config: DistillationConfig) -> dict[str, Any]:
    requests = _inventory(config)
    state = status(config)
    if state["completed"] != len(requests):
        raise IntegrityError("완료되지 않은 distill request가 있습니다")
    output_dir = config.run_dir / "export"
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise InputError("distill export를 먼저 실행해야 합니다")
    try:
        actual_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("distill export manifest가 손상되었습니다") from exc
    expected_rows, expected_manifest = _export_material(config)
    if actual_manifest != expected_manifest:
        raise IntegrityError("distill export가 current inventory/spool set과 일치하지 않습니다")
    if not (
        actual_manifest.get("redistribution_allowed") is False
        and actual_manifest.get("release_gate") == "blocked"
        and actual_manifest.get("teacher_output_license")
        == "LicenseRef-LLMEX-Internal-Distillation"
    ):
        raise IntegrityError("distill 내부 전용 라이선스/release gate가 손상되었습니다")
    for split in ("train", "heldout"):
        path = output_dir / f"{split}.jsonl"
        expected_payload = "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for value in expected_rows[split]
        ).encode("utf-8")
        try:
            actual_payload = path.read_bytes()
        except OSError as exc:
            raise IntegrityError("distill export JSONL을 읽을 수 없습니다") from exc
        if (
            actual_payload != expected_payload
            or sha256_file(path) != expected_manifest["sha256"][split]
        ):
            raise IntegrityError("distill export row가 current spool 파생값과 다릅니다")
        load_chat_jsonl(path, split=split, allowed_licenses={config.teacher_output_license})
    train_sources = {item.source.source_sha256 for item in requests if item.split == "train"}
    heldout_sources = {item.source.source_sha256 for item in requests if item.split == "heldout"}
    if train_sources & heldout_sources:
        raise IntegrityError("distill train/heldout upstream source가 누출되었습니다")
    return {
        "schema_version": 2,
        "status": "ok",
        "requests": len(requests),
        "prompt_overlap": 0,
        "upstream_source_overlap": 0,
        "export_sha256": expected_manifest["sha256"],
        "redistribution_allowed": False,
        "release_gate": "blocked",
        "safety_filter_scope": SAFETY_FILTER_SCOPE,
    }
