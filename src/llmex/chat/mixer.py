"""공개·teacher ChatDataset을 split 비누출로 결정적 혼합한다."""

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from llmex.chat.data import ChatRow, final_user_prompt_sha256, provenance_source_key
from llmex.chat.template import render_chat, tokenize_chat
from llmex.config import SFTMixConfig
from llmex.errors import ConflictError, InputError, IntegrityError, LlmexError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.locking import exclusive_run_lock
from llmex.sensitive import (
    BUILTIN_SENSITIVE_OUTPUT_RULES,
    SENSITIVE_OUTPUT_LENGTH_RULE_NAME,
    matched_sensitive_output_rules,
)
from llmex.tokenizer.core import load_tokenizer

_INTERNAL_LICENSE = "LicenseRef-LLMEX-Internal-Distillation"


@dataclass(frozen=True)
class _Candidate:
    row: ChatRow
    origin: str
    prompt_sha256: str
    source_key: str


def _config_fingerprint(config: SFTMixConfig) -> str:
    return fingerprint(config.model_dump(mode="json"))


def _read_rows(
    path: Path, *, split: str, origin: str, allowed_licenses: set[str]
) -> tuple[list[_Candidate], dict[str, object]]:
    if not path.is_file():
        raise InputError(f"SFT mix 입력 파일이 없습니다: {path}")
    rows: list[_Candidate] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    raise IntegrityError(f"빈 JSONL 행은 허용하지 않습니다: {path}:{line_number}")
                row = ChatRow.model_validate(json.loads(line))
                if row.split != split:
                    raise IntegrityError(f"SFT mix split 불일치: {path}:{line_number}")
                if row.provenance.license not in allowed_licenses:
                    raise IntegrityError(
                        f"허가되지 않은 라이선스: {row.provenance.license}: {path}:{line_number}"
                    )
                prompt_sha = final_user_prompt_sha256(row.messages)
                source_key = provenance_source_key(row.provenance, fallback_sha256=row.sha256)
                rows.append(_Candidate(row, origin, prompt_sha, source_key))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise IntegrityError(f"SFT mix JSONL schema 검증 실패: {path}: {exc}") from exc
    if not rows:
        raise IntegrityError(f"SFT mix 입력이 비었습니다: {path}")
    return rows, {
        "path": str(path),
        "sha256": sha256_file(path),
        "rows": len(rows),
        "split": split,
        "origin": origin,
    }


def _teacher_manifest(
    config: SFTMixConfig, *, expected_counts: dict[str, int]
) -> dict[str, object]:
    try:
        manifest_sha256 = sha256_file(config.teacher_manifest)
        if manifest_sha256 != config.expected_teacher_manifest_sha256:
            raise ValueError("teacher manifest checksum")
        value = json.loads(config.teacher_manifest.read_text(encoding="utf-8"))
        hashes = value["sha256"]
        counts = value["counts"]
        core = {
            name: value[name]
            for name in (
                "config_fingerprint",
                "inventory_fingerprint",
                "accepted_spool_set_fingerprint",
            )
        }
        if (
            value.get("schema_version") != 2
            or value.get("teacher_output_license") != _INTERNAL_LICENSE
            or value.get("redistribution_allowed") is not False
            or value.get("release_gate") != "blocked"
            or hashes["train"] != sha256_file(config.teacher_train_data)
            or hashes["heldout"] != sha256_file(config.teacher_heldout_data)
            or counts != expected_counts
            or not all(
                isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item)
                for item in core.values()
            )
        ):
            raise ValueError("teacher manifest binding")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise IntegrityError("teacher export manifest 결속이 올바르지 않습니다") from exc
    return {
        "path": str(config.teacher_manifest),
        "sha256": manifest_sha256,
        "core": core,
        "redistribution_allowed": False,
        "release_gate": "blocked",
    }


def _serialized_row(candidate: _Candidate, split: str) -> dict[str, object]:
    identifier = (
        "mix-"
        + fingerprint(
            {
                "origin": candidate.origin,
                "row_sha256": candidate.row.sha256,
                "split": split,
            }
        )[:24]
    )
    messages = [message.model_dump() for message in candidate.row.messages]
    provenance = candidate.row.provenance.model_dump(exclude_none=True)
    if candidate.row.provenance.source_id is None:
        provenance["source_id"] = candidate.row.id
        if candidate.row.provenance.source_sha256 is None:
            provenance["source_sha256"] = candidate.row.sha256
    basis = {"id": identifier, "messages": messages, "provenance": provenance, "split": split}
    return {"schema_version": 1, **basis, "sha256": fingerprint(basis)}


def _payload(rows: list[dict[str, object]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def _distribution(candidates: list[_Candidate]) -> dict[str, object]:
    total = len(candidates)
    origins = Counter(item.origin for item in candidates)
    licenses = Counter(item.row.provenance.license for item in candidates)
    datasets = Counter(item.row.provenance.dataset for item in candidates)

    def values(counter: Counter[str]) -> dict[str, dict[str, float | int]]:
        return {
            name: {"count": count, "ratio": count / total}
            for name, count in sorted(counter.items())
        }

    return {
        "total": total,
        "origins": values(origins),
        "licenses": values(licenses),
        "datasets": values(datasets),
    }


def _material(config: SFTMixConfig) -> tuple[bytes, bytes, dict[str, object]]:
    allowed = set(config.allowed_licenses)
    specifications = [
        (config.public_train_data, "train", "public-train"),
        (config.public_heldout_data, "heldout", "public-heldout"),
        (config.teacher_train_data, "train", "teacher-train"),
        (config.teacher_heldout_data, "heldout", "teacher-heldout"),
    ]
    candidates: list[_Candidate] = []
    inputs: dict[str, object] = {}
    for path, split, origin in specifications:
        rows, binding = _read_rows(path, split=split, origin=origin, allowed_licenses=allowed)
        candidates.extend(rows)
        inputs[origin] = binding
    teacher = _teacher_manifest(
        config,
        expected_counts={
            "train": cast(int, cast(dict[str, object], inputs["teacher-train"])["rows"]),
            "heldout": cast(int, cast(dict[str, object], inputs["teacher-heldout"])["rows"]),
        },
    )
    tokenizer = load_tokenizer(config.tokenizer_dir)
    tokenizer_manifest = config.tokenizer_dir / "tokenizer-manifest.json"
    if not tokenizer_manifest.is_file():
        raise InputError("tokenizer manifest가 없습니다")

    excluded: Counter[str] = Counter()
    sensitive_by_source: Counter[str] = Counter({"public": 0, "teacher": 0})
    sensitive_by_split: Counter[str] = Counter({"train": 0, "heldout": 0})
    sensitive_by_rule: Counter[str] = Counter(
        {rule.name: 0 for rule in BUILTIN_SENSITIVE_OUTPUT_RULES}
    )
    sensitive_by_rule[SENSITIVE_OUTPUT_LENGTH_RULE_NAME] = 0
    sensitive_by_rule.update({rule.name: 0 for rule in config.extra_sensitive_output_patterns})
    extra_sensitive_rules = tuple(
        (rule.name, rule.pattern) for rule in config.extra_sensitive_output_patterns
    )
    sensitive_valid: list[_Candidate] = []
    for candidate in candidates:
        matched: set[str] = set()
        for message in candidate.row.messages:
            if message.role == "assistant":
                matched.update(
                    matched_sensitive_output_rules(message.content, extra_sensitive_rules)
                )
        if matched:
            excluded["sensitive_assistant_output"] += 1
            sensitive_by_source[candidate.origin.split("-", maxsplit=1)[0]] += 1
            sensitive_by_split[candidate.row.split] += 1
            sensitive_by_rule.update(matched)
        else:
            sensitive_valid.append(candidate)

    valid: list[_Candidate] = []
    for candidate in sensitive_valid:
        messages = tuple(candidate.row.messages)
        prompt_tokens = len(
            tokenizer.encode(render_chat(messages[:-1], add_generation_prompt=True)).ids
        )
        full_tokens = len(tokenize_chat(tokenizer, messages, max_length=10**9).input_ids)
        if prompt_tokens + config.generation_reserve_tokens > config.max_seq_len:
            excluded["prompt_too_long"] += 1
        elif full_tokens > config.max_seq_len:
            excluded["sequence_too_long"] += 1
        else:
            valid.append(candidate)

    all_heldout_prompts = {
        item.prompt_sha256 for item in sensitive_valid if item.row.split == "heldout"
    }
    all_heldout_sources = {
        item.source_key for item in sensitive_valid if item.row.split == "heldout"
    }
    heldout_by_prompt: dict[str, list[_Candidate]] = {}
    for candidate in valid:
        if candidate.row.split == "heldout":
            heldout_by_prompt.setdefault(candidate.prompt_sha256, []).append(candidate)
    selected_heldout: list[_Candidate] = []
    for _prompt_sha, group in sorted(heldout_by_prompt.items()):
        ordered = sorted(group, key=lambda item: (item.source_key, item.row.sha256, item.origin))
        selected_heldout.append(ordered[0])
        excluded["heldout_prompt_duplicate"] += len(ordered) - 1
    selected_train: list[_Candidate] = []
    seen_source_prompt: set[tuple[str, str]] = set()
    for candidate in sorted(
        (item for item in valid if item.row.split == "train"),
        key=lambda item: (item.prompt_sha256, item.source_key, item.row.sha256, item.origin),
    ):
        if candidate.prompt_sha256 in all_heldout_prompts:
            excluded["heldout_prompt_from_train"] += 1
            continue
        if candidate.source_key in all_heldout_sources:
            excluded["heldout_source_from_train"] += 1
            continue
        key = (candidate.source_key, candidate.prompt_sha256)
        if key in seen_source_prompt:
            excluded["duplicate_source_prompt"] += 1
            continue
        seen_source_prompt.add(key)
        selected_train.append(candidate)

    train_prompts = {item.prompt_sha256 for item in selected_train}
    heldout_prompts = {item.prompt_sha256 for item in selected_heldout}
    train_sources = {item.source_key for item in selected_train}
    final_heldout_sources = {item.source_key for item in selected_heldout}
    if train_prompts & heldout_prompts or train_sources & final_heldout_sources:
        raise IntegrityError("SFT mix 최종 split overlap이 0이 아닙니다")

    train_rows = [_serialized_row(item, "train") for item in selected_train]
    heldout_rows = [_serialized_row(item, "heldout") for item in selected_heldout]
    if not train_rows or not heldout_rows:
        raise IntegrityError("SFT mix 결과 train/heldout 중 하나가 비었습니다")
    train_bytes, heldout_bytes = _payload(train_rows), _payload(heldout_rows)
    selected = selected_train + selected_heldout
    internal = any(item.row.provenance.license == _INTERNAL_LICENSE for item in candidates)
    outputs = {
        "train": {
            "path": str(config.output_dir / "train.jsonl"),
            "rows": len(train_rows),
            "sha256": hashlib.sha256(train_bytes).hexdigest(),
            "fingerprint": fingerprint(
                {"split": "train", "rows": [row["sha256"] for row in train_rows]}
            ),
        },
        "heldout": {
            "path": str(config.output_dir / "heldout.jsonl"),
            "rows": len(heldout_rows),
            "sha256": hashlib.sha256(heldout_bytes).hexdigest(),
            "fingerprint": fingerprint(
                {"split": "heldout", "rows": [row["sha256"] for row in heldout_rows]}
            ),
        },
    }
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": "sft-public-teacher-mix",
        "config_fingerprint": _config_fingerprint(config),
        "inputs": inputs,
        "teacher_manifest": teacher,
        "tokenizer_manifest_sha256": sha256_file(tokenizer_manifest),
        "length_gate": {
            "max_seq_len": config.max_seq_len,
            "generation_reserve_tokens": config.generation_reserve_tokens,
            "policy": "no_training_truncation_and_prompt_plus_generation_reserve",
        },
        "selection": {
            "input_rows": len(candidates),
            "selected_train": len(train_rows),
            "selected_heldout": len(heldout_rows),
            "excluded": dict(sorted(excluded.items())),
        },
        "sensitive_output_filter": {
            "total": excluded["sensitive_assistant_output"],
            "by_source": dict(sorted(sensitive_by_source.items())),
            "by_split": dict(sorted(sensitive_by_split.items())),
            "by_rule": dict(sorted(sensitive_by_rule.items())),
        },
        "distribution": _distribution(selected),
        "outputs": outputs,
        "prompt_overlap": 0,
        "source_sha256_overlap": 0,
        "redistribution_allowed": not internal,
        "release_gate": "blocked" if internal else "not_blocked",
    }
    manifest["fingerprint"] = fingerprint(manifest)
    return train_bytes, heldout_bytes, manifest


def _paths(config: SFTMixConfig) -> tuple[Path, Path, Path]:
    return (
        config.output_dir / "train.jsonl",
        config.output_dir / "heldout.jsonl",
        config.output_dir / "manifest.json",
    )


def _publish_names(config: SFTMixConfig) -> tuple[str, str]:
    identity = fingerprint({"output_dir": str(config.output_dir.resolve(strict=False))})[:24]
    return f".sft-mix-{identity}.lock", f".sft-mix-{identity}-staging-"


def _safe_material(config: SFTMixConfig) -> tuple[bytes, bytes, dict[str, object]]:
    try:
        return _material(config)
    except LlmexError:
        raise
    except OSError as exc:
        raise IntegrityError("SFT mix 입력을 안정적으로 읽을 수 없습니다") from exc


def validate_mix(config: SFTMixConfig) -> dict[str, object]:
    train_path, heldout_path, manifest_path = _paths(config)
    if not all(path.is_file() for path in (train_path, heldout_path, manifest_path)):
        raise InputError("완료된 SFT mix 출력을 찾을 수 없습니다")
    expected_train, expected_heldout, expected_manifest = _safe_material(config)
    try:
        actual_manifest_bytes = manifest_path.read_bytes()
        actual_manifest = json.loads(actual_manifest_bytes)
        actual_train = train_path.read_bytes()
        actual_heldout = heldout_path.read_bytes()
        actual_manifest_sha256 = hashlib.sha256(actual_manifest_bytes).hexdigest()
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError("SFT mix manifest가 손상되었습니다") from exc
    if (
        actual_train != expected_train
        or actual_heldout != expected_heldout
        or actual_manifest != expected_manifest
        or actual_manifest_sha256
        != hashlib.sha256(
            (
                json.dumps(expected_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
        ).hexdigest()
    ):
        raise IntegrityError("SFT mix 출력이 현재 입력/config와 다릅니다")
    return {
        "schema_version": 1,
        "status": "ok",
        "outputs": expected_manifest["outputs"],
        "redistribution_allowed": expected_manifest["redistribution_allowed"],
        "release_gate": expected_manifest["release_gate"],
        "fingerprint": expected_manifest["fingerprint"],
    }


def prepare_mix(config: SFTMixConfig) -> dict[str, object]:
    parent = config.output_dir.parent
    lock_name, staging_prefix = _publish_names(config)
    try:
        with exclusive_run_lock(parent, filename=lock_name, label="SFT mix"):
            train_path, heldout_path, manifest_path = _paths(config)
            if config.output_dir.exists():
                if not config.output_dir.is_dir():
                    raise ConflictError("SFT mix 출력 경로가 디렉터리가 아닙니다")
                existing = [path.exists() for path in (train_path, heldout_path, manifest_path)]
                if not all(existing):
                    raise ConflictError("부분 SFT mix 출력은 자동 덮어쓸 수 없습니다")
                return {**validate_mix(config), "reused": True}
            if any(parent.glob(f"{staging_prefix}*")):
                raise ConflictError("미완료 SFT mix staging이 발견되었습니다")

            staging = Path(tempfile.mkdtemp(prefix=staging_prefix, dir=parent))
            try:
                train_bytes, heldout_bytes, manifest = _safe_material(config)
                staged_train = staging / "train.jsonl"
                staged_heldout = staging / "heldout.jsonl"
                staged_manifest = staging / "manifest.json"
                staged_train.write_bytes(train_bytes)
                staged_heldout.write_bytes(heldout_bytes)
                staged_manifest.write_bytes(
                    (
                        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                    ).encode("utf-8")
                )
                for path in (staged_train, staged_heldout, staged_manifest):
                    with path.open("rb") as stream:
                        os.fsync(stream.fileno())
                staging_descriptor = os.open(staging, os.O_RDONLY)
                try:
                    os.fsync(staging_descriptor)
                finally:
                    os.close(staging_descriptor)
                os.replace(staging, config.output_dir)
                parent_descriptor = os.open(parent, os.O_RDONLY)
                try:
                    os.fsync(parent_descriptor)
                finally:
                    os.close(parent_descriptor)
                return {**validate_mix(config), "reused": False}
            finally:
                shutil.rmtree(staging, ignore_errors=True)
    except (ConflictError, IntegrityError, InputError):
        raise
    except OSError as exc:
        raise IntegrityError("SFT mix materialize 또는 publish에 실패했습니다") from exc


def preflight_mix(config: SFTMixConfig) -> dict[str, object]:
    _, _, manifest = _safe_material(config)
    return {
        "schema_version": 1,
        "status": "ok",
        "selection": manifest["selection"],
        "sensitive_output_filter": manifest["sensitive_output_filter"],
        "redistribution_allowed": manifest["redistribution_allowed"],
        "release_gate": manifest["release_gate"],
    }


def status_mix(config: SFTMixConfig) -> dict[str, object]:
    train_path, heldout_path, manifest_path = _paths(config)
    existing = [path.exists() for path in (train_path, heldout_path, manifest_path)]
    if not any(existing):
        return {
            "schema_version": 1,
            "status": "pending",
            "config_fingerprint": _config_fingerprint(config),
        }
    if not all(existing):
        raise ConflictError("부분 SFT mix 출력이 발견되었습니다")
    return {**validate_mix(config), "status": "ready"}
