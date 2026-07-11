"""토크나이저 효율과 Unicode 안전성 평가."""

import random
import re
from collections.abc import Iterator
from typing import Any

from llmex.config import TokenizerConfig
from llmex.data.io import prepare_output, write_json
from llmex.fingerprint import fingerprint, sha256_file
from llmex.tokenizer.core import (
    SPECIAL_IDS,
    corpus_fingerprint,
    iter_documents,
    load_tokenizer,
    verify_round_trip,
)


def fixed_unicode_samples(count: int, seed: int) -> Iterator[str]:
    """플랫폼과 실행 순서에 무관한 유효 Unicode 표본을 만든다."""

    randomizer = random.Random(seed)
    ranges = ((0x20, 0xD7FF), (0xE000, 0x10FFFF))
    required = [
        "한글 완성형",
        "ㅎㅏㄴㄱㅡㄹ",
        "한글\u1100\u1161",
        "👨‍👩‍👧‍👦",
        "漢字",
        "ASCII",
        "e\u0301",
        "A\u0327\u0301",
    ]
    yield from required[:count]
    for _ in range(max(0, count - len(required))):
        length = randomizer.randint(0, 24)
        chars: list[str] = []
        for _ in range(length):
            start, end = ranges[randomizer.randrange(len(ranges))]
            chars.append(chr(randomizer.randint(start, end)))
        yield "".join(chars)


def evaluate(config: TokenizerConfig, *, force: bool = False) -> dict[str, Any]:
    tokenizer = load_tokenizer(config.output_dir)
    corpus = corpus_fingerprint(config.corpus)
    operation = {
        "command": "tokenizer evaluate",
        "config": config.model_dump(mode="json"),
        "corpus": corpus,
    }
    report_path = config.output_dir / "evaluation.json"
    prepare_output(report_path, operation, force=force)
    totals = {
        "characters": 0,
        "utf8_bytes": 0,
        "tokens": 0,
        "words": 0,
        "unk_tokens": 0,
        "documents": 0,
    }
    by_split: dict[str, dict[str, int]] = {}
    for row in iter_documents(config.corpus):
        text = str(row["text"])
        ids = tokenizer.encode(text).ids
        split = str(row["split"])
        values = by_split.setdefault(split, {key: 0 for key in totals})
        measurements = {
            "characters": len(text),
            "utf8_bytes": len(text.encode("utf-8")),
            "tokens": len(ids),
            "words": len(re.findall(r"\S+", text)),
            "unk_tokens": ids.count(SPECIAL_IDS["<unk>"]),
            "documents": 1,
        }
        for key, value in measurements.items():
            totals[key] += value
            values[key] += value
    token_count = max(1, totals["tokens"])
    word_count = max(1, totals["words"])
    samples = verify_round_trip(
        tokenizer, fixed_unicode_samples(config.evaluation_samples, config.seed)
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "corpus": corpus,
        "tokenizer_sha256": sha256_file(config.output_dir / "tokenizer.json"),
        "totals": totals,
        "by_split": by_split,
        "metrics": {
            "chars_per_token": totals["characters"] / token_count,
            "bytes_per_token": totals["utf8_bytes"] / token_count,
            "tokens_per_word": totals["tokens"] / word_count,
            "byte_baseline_tokens": totals["utf8_bytes"],
            "token_reduction_vs_byte_baseline": 1 - totals["tokens"] / max(1, totals["utf8_bytes"]),
        },
        "unicode_fixed_samples": samples,
        "unk_tokens": totals["unk_tokens"],
    }
    report["fingerprint"] = fingerprint(report)
    write_json(report_path, report)
    metrics = report["metrics"]
    markdown = (
        "# 토크나이저 평가 보고서\n\n"
        f"- 문자/토큰: {metrics['chars_per_token']:.6f}\n"
        f"- 바이트/토큰: {metrics['bytes_per_token']:.6f}\n"
        f"- 단어당 토큰: {metrics['tokens_per_word']:.6f}\n"
        f"- byte baseline 토큰: {metrics['byte_baseline_tokens']}\n"
        f"- byte baseline 대비 토큰 감소율: {metrics['token_reduction_vs_byte_baseline']:.6%}\n"
        f"- UNK: {totals['unk_tokens']}\n- 고정 Unicode round-trip 표본: {samples}\n"
    )
    (config.output_dir / "evaluation.md").write_text(markdown, encoding="utf-8")
    return report
