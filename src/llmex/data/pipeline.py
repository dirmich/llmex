"""단계별 M1 파이프라인과 manifest/report 생성."""

import random
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from llmex.config import DataConfig
from llmex.data.clean import clean_page
from llmex.data.dedup import deduplicate
from llmex.data.extract import stream_pages
from llmex.data.io import read_jsonl_zst, write_json, write_jsonl_zst
from llmex.data.schema import Document
from llmex.data.split import split_for
from llmex.fingerprint import fingerprint, sha256_file


def raw_manifest(
    config: DataConfig, path: Path, download_result: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "immutable": True,
        "dump_date": config.dump.date,
        "dump_url": str(config.dump.url),
        "expected_sha256": config.dump.sha256,
        "actual_sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "download": dict(download_result),
    }


def extract_rows(
    config: DataConfig, raw_path: Path, *, max_documents: int | None
) -> Iterable[dict[str, Any]]:
    for page in stream_pages(raw_path, max_documents=max_documents):
        yield dict(page)


def clean_rows(
    config: DataConfig, rows: Iterable[Mapping[str, Any]], stats: Counter[str]
) -> Iterable[dict[str, Any]]:
    for row in rows:
        stats["documents_before"] += 1
        stats["chars_before"] += len(str(row["text"]))
        result = clean_page(
            dict(row),
            dump_url=str(config.dump.url),
            dump_date=config.dump.date,
            config=config.cleaning,
        )
        if result.document is None:
            stats[f"filtered_{result.reason}"] += 1
            continue
        stats["documents_after"] += 1
        stats["chars_after"] += result.document.quality.chars
        stats["bytes_after"] += result.document.quality.bytes
        stats.update(
            {f"policy_{key}": value for key, value in result.document.quality.policy_stats.items()}
        )
        yield result.document.json_row()


def dedup_rows(
    config: DataConfig, rows: Iterable[Mapping[str, Any]], stats: Counter[str]
) -> Iterable[dict[str, Any]]:
    documents = (Document.model_validate(row) for row in rows)
    unique, dedup_stats = deduplicate(
        documents,
        near=config.cleaning.near_dedup,
        threshold=config.cleaning.near_dedup_threshold,
        shingle_size=config.cleaning.shingle_size,
    )
    for document in unique:
        stats["documents_unique"] += 1
        yield document.json_row()
    stats.update(dedup_stats)


def split_rows(
    config: DataConfig, rows: Iterable[Mapping[str, Any]], stats: Counter[str]
) -> Iterable[dict[str, Any]]:
    for row in rows:
        document = Document.model_validate(row)
        document.split = split_for(document.sha256, seed=config.seed)  # type: ignore[reportAttributeAccessIssue]
        stats[f"split_{document.split}"] += 1
        yield document.json_row()


def build_report(
    config: DataConfig,
    corpus_path: Path,
    stats: Mapping[str, int],
    *,
    input_fingerprint: str,
    max_documents: int | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "pipeline_fingerprint": fingerprint(
            {
                "config": config.model_dump(mode="json"),
                "input": input_fingerprint,
                "max_documents": max_documents,
            }
        ),
        "corpus": {
            "path": str(corpus_path),
            "sha256": sha256_file(corpus_path),
            "bytes": corpus_path.stat().st_size,
        },
        "dump": {
            "date": config.dump.date,
            "url": str(config.dump.url),
            "sha256": config.dump.sha256,
        },
        "policy": config.cleaning.model_dump(mode="json"),
        "stats": dict(sorted(stats.items())),
        "canary": {
            "requested_max_documents": max_documents,
            "is_1000_document_run": max_documents == 1000,
        },
    }


def report_markdown(report: Mapping[str, Any]) -> str:
    raw_stats = report["stats"]
    assert isinstance(raw_stats, dict)
    stats = cast(dict[str, object], raw_stats)
    lines = [
        "# Wikipedia 데이터 리포트",
        "",
        f"- 파이프라인 fingerprint: `{report['pipeline_fingerprint']}`",
        f"- corpus SHA-256: `{report['corpus']['sha256']}`",
        f"- dump 날짜: `{report['dump']['date']}`",
        "",
        "## 통계",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(stats.items()))
    lines.extend(
        [
            "",
            "## 정책",
            "",
            "표와 참조는 제거하고, 수식과 목록의 표시 텍스트는 보존한다. "
            "exact SHA-256 중복 제거는 항상 적용하며 MinHash near-dedup은 선택 사항이다.",
            "",
            "## 해석 제한",
            "",
            "Wikipedia 원문에는 개인정보·명예훼손·저작권 문제가 있을 수 있다. "
            "라이선스 및 문서별 고지를 별도로 검토해야 한다.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_sample(
    corpus_path: Path, output_json: Path, output_md: Path, *, count: int, seed: int
) -> int:
    documents = [Document.model_validate(row) for row in read_jsonl_zst(corpus_path)]
    randomizer = random.Random(seed)
    selected = randomizer.sample(documents, min(count, len(documents)))
    rows = [
        {
            "page_id": item.page_id,
            "revision_id": item.revision_id,
            "title": item.title,
            "source_url": item.source_url,
            "sha256": item.sha256,
            "split": item.split,
            "quality": item.quality.model_dump(mode="json"),
            "text_preview": item.text[:500],
            "review": {"markup_ok": None, "language_ok": None, "attribution_ok": None, "note": ""},
        }
        for item in selected
    ]
    write_json(
        output_json,
        {"schema_version": 1, "requested": count, "sampled": len(rows), "documents": rows},
    )
    lines = [
        "# Canary 샘플 감사",
        "",
        f"- 요청: {count}건",
        f"- 생성: {len(rows)}건",
        "",
        "| page_id | 제목 | split | markup | 언어 | attribution | 메모 |",
        "|---:|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {row['page_id']} | {row['title']} | {row['split']} |  |  |  |  |" for row in rows
    )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def run_e2e(
    config: DataConfig, raw_path: Path, output_dir: Path, *, max_documents: int | None
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter()
    extracted = output_dir / "extracted.jsonl.zst"
    cleaned = output_dir / "cleaned.jsonl.zst"
    unique = output_dir / "deduplicated.jsonl.zst"
    corpus = output_dir / "corpus-v1.jsonl.zst"
    write_jsonl_zst(extracted, extract_rows(config, raw_path, max_documents=max_documents))
    write_jsonl_zst(cleaned, clean_rows(config, read_jsonl_zst(extracted), stats))
    write_jsonl_zst(unique, dedup_rows(config, read_jsonl_zst(cleaned), stats))
    write_jsonl_zst(corpus, split_rows(config, read_jsonl_zst(unique), stats))
    report = build_report(
        config, corpus, stats, input_fingerprint=sha256_file(raw_path), max_documents=max_documents
    )
    write_json(output_dir / "data-manifest.json", report)
    (output_dir / "data-report.md").write_text(report_markdown(report), encoding="utf-8")
    audit_sample(
        corpus,
        output_dir / "audit-sample.json",
        output_dir / "audit-sample.md",
        count=100,
        seed=config.seed,
    )
    return report
