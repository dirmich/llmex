"""출처 split을 보존하는 logical request inventory v2 구성."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator
from typing import Any, cast

from pydantic import ValidationError

from llmex.chat.data import ChatRow, ResponseQualityContract
from llmex.config import DistillationConfig
from llmex.data.io import read_jsonl_zst
from llmex.errors import InputError, IntegrityError
from llmex.fingerprint import fingerprint

from .schema import LogicalRequest, SourceProvenance


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def response_quality_manifest(
    requests: list[LogicalRequest], quality_gate_version: str
) -> dict[str, Any]:
    """inventory에서 품질 계약 증거를 결정적으로 다시 계산한다."""

    contracts = [item.source.response_quality for item in requests]
    if quality_gate_version == "metadata-v1":
        if any(contract is None for contract in contracts):
            raise IntegrityError("metadata-v1 품질 gate에 필요한 response_quality 계약이 없습니다")
        contract_rows = [
            {
                "id": item.id,
                "contract": item.source.response_quality.model_dump(mode="json"),
            }
            for item in requests
            if item.source.response_quality is not None
        ]
        return {
            "quality_gate_version": quality_gate_version,
            "response_quality_contracts": len(contract_rows),
            "response_quality_fingerprint": fingerprint({"contracts": contract_rows}),
        }
    if any(contract is not None for contract in contracts):
        raise IntegrityError("response_quality 계약에는 metadata-v1 품질 gate가 필요합니다")
    return {}


def _request(prompt: str, source: SourceProvenance, heldout_basis_points: int) -> LogicalRequest:
    normalized = normalize_text(prompt)
    prompt_sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    hashed_split = (
        "heldout" if int(prompt_sha[:16], 16) % 10_000 < heldout_basis_points else "train"
    )
    split = "heldout" if source.source_split == "heldout" else hashed_split
    return LogicalRequest(
        schema_version=2,
        id=f"distill-{prompt_sha[:24]}",
        prompt=normalized,
        prompt_sha256=prompt_sha,
        split=split,
        source=source,
    )


def _chat_candidates(config: DistillationConfig) -> Iterator[LogicalRequest]:
    for path in config.source_chat_files:
        if not path.is_file():
            raise InputError(f"instruction JSONL 파일이 없습니다: {path}")
        try:
            with path.open(encoding="utf-8") as stream:
                for number, line in enumerate(stream, 1):
                    row = ChatRow.model_validate(json.loads(line))
                    users = [message.content for message in row.messages if message.role == "user"]
                    if not users:
                        raise IntegrityError(f"user turn이 없는 instruction 행: {path}:{number}")
                    metadata = dict(row.provenance.source_metadata or {})
                    if "upstream_split" in metadata:
                        raise IntegrityError(
                            f"예약된 upstream_split metadata가 있습니다: {path}:{number}"
                        )
                    source = SourceProvenance(
                        dataset=row.provenance.dataset,
                        source=row.provenance.source,
                        license=row.provenance.license,
                        collected_at=row.provenance.collected_at,
                        source_id=row.id,
                        source_sha256=row.sha256,
                        source_split=row.split,
                        metadata={**metadata, "upstream_split": row.split},
                        response_quality=_source_response_quality(metadata, users[-1])
                        or row.provenance.response_quality,
                    )
                    yield _request(users[-1], source, config.heldout_basis_points)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise IntegrityError(
                f"instruction JSONL schema가 손상되었습니다: {path}: {exc}"
            ) from exc


def _source_response_quality(
    metadata: dict[str, Any], prompt: str
) -> ResponseQualityContract | None:
    """오래 저장된 natural inventory에도 최신 품질 계약을 재결속한다."""
    profile = metadata.get("profile")
    task = metadata.get("task")
    if profile not in {"natural-v3", "natural-v4", "natural-v5"} or not isinstance(task, str):
        return None
    from llmex.chat.multilingual import response_quality_contract

    act = metadata.get("conversation_act")
    conversation_act = act if act in {"question", "suggestion"} else None
    return response_quality_contract(
        task,
        prompt,
        conversation_act=conversation_act,
        translation_contract="natural-v5" if profile == "natural-v5" else "base",
    )


def _wiki_candidates(config: DistillationConfig) -> Iterator[LogicalRequest]:
    if not config.corpus.is_file():
        raise InputError(f"Wikipedia corpus가 없습니다: {config.corpus}")
    for row in read_jsonl_zst(config.corpus):
        if row.get("split") != "train":
            continue
        title = row.get("title")
        source_url = row.get("source_url")
        license_name = row.get("license")
        page_id = row.get("page_id")
        revision_id = row.get("revision_id")
        dump_date = row.get("dump_date")
        if not all(isinstance(value, str) and value for value in (title, source_url, license_name)):
            raise IntegrityError("Wikipedia corpus provenance 문자열이 올바르지 않습니다")
        valid_page_id = (
            isinstance(page_id, int) and not isinstance(page_id, bool) and page_id > 0
        ) or (isinstance(page_id, str) and bool(page_id) and page_id.isdigit())
        valid_revision_id = (
            isinstance(revision_id, int) and not isinstance(revision_id, bool) and revision_id > 0
        ) or (isinstance(revision_id, str) and bool(revision_id) and revision_id.isdigit())
        if not valid_page_id or not valid_revision_id:
            raise IntegrityError("Wikipedia page/revision ID가 올바르지 않습니다")
        if not isinstance(dump_date, str) or re.fullmatch(r"\d{8}", dump_date) is None:
            raise IntegrityError("Wikipedia dump_date는 YYYYMMDD 8자리여야 합니다")
        normalized_page_id = cast(str | int, page_id)
        normalized_revision_id = cast(str | int, revision_id)
        source_sha = row.get("sha256")
        if not isinstance(source_sha, str) or len(source_sha) != 64:
            source_sha = fingerprint({"title": title, "source_url": source_url})
        source = SourceProvenance(
            dataset=f"kowiki-{dump_date}",
            source=cast(str, source_url),
            license=cast(str, license_name),
            collected_at=config.source_collected_at,
            source_id=f"page-{normalized_page_id}-revision-{normalized_revision_id}",
            source_sha256=source_sha,
            source_split="train",
            metadata={
                "page_id": normalized_page_id,
                "revision_id": normalized_revision_id,
                "dump_date": dump_date,
            },
        )
        yield _request(
            f"{title}에 대해 핵심 내용을 설명해 주세요.",
            source,
            config.heldout_basis_points,
        )


def build_inventory(config: DistillationConfig) -> tuple[list[LogicalRequest], dict[str, Any]]:
    chat_rows = list(_chat_candidates(config))
    unique: dict[str, LogicalRequest] = {}
    for item in chat_rows:
        previous = unique.get(item.prompt_sha256)
        if previous is None or (
            previous.source.source_split == "train" and item.source.source_split == "heldout"
        ):
            unique[item.prompt_sha256] = item
    chat_unique = len(unique)
    wiki_examined = 0
    if len(unique) < config.target_requests:
        for item in _wiki_candidates(config):
            wiki_examined += 1
            unique.setdefault(item.prompt_sha256, item)
            if len(unique) == config.target_requests:
                break
    if len(unique) < config.target_requests:
        raise IntegrityError(
            f"고유 logical request가 부족합니다: {len(unique)}/{config.target_requests}"
        )
    selected = sorted(unique.values(), key=lambda item: item.id)[: config.target_requests]
    quality_manifest = response_quality_manifest(selected, config.quality_gate_version)
    train_sources = {item.source.source_sha256 for item in selected if item.split == "train"}
    heldout_sources = {item.source.source_sha256 for item in selected if item.split == "heldout"}
    overlap = train_sources & heldout_sources
    if overlap:
        raise IntegrityError("distill train/heldout upstream source가 누출되었습니다")
    upstream_heldout = [item for item in selected if item.source.source_split == "heldout"]
    if any(item.split != "heldout" for item in upstream_heldout):
        raise IntegrityError("upstream heldout split 보존에 실패했습니다")
    split_counts = {
        name: sum(item.split == name for item in selected) for name in ("train", "heldout")
    }
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "target_requests": config.target_requests,
        "source_chat_rows": len(chat_rows),
        "source_chat_unique_prompts": chat_unique,
        "source_chat_duplicates": len(chat_rows) - chat_unique,
        "source_upstream_heldout": len(upstream_heldout),
        "wikipedia_rows_examined": wiki_examined,
        "requests": len(selected),
        "split_counts": split_counts,
        "prompt_overlap": 0,
        "upstream_source_overlap": 0,
        "inventory_fingerprint": fingerprint(
            {
                "schema_version": 2,
                "rows": [item.model_dump(mode="json", exclude_none=True) for item in selected],
            }
        ),
    }
    manifest.update(quality_manifest)
    return selected, manifest
