#!/usr/bin/env python3
"""교재 tokenizer→pretrain→eval용 결정적 3-split 합성 corpus를 만든다."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from llmex.data.clean import quality
from llmex.data.io import read_jsonl_zst, write_json, write_jsonl_zst
from llmex.data.schema import Document
from llmex.fingerprint import fingerprint, sha256_file

SPLITS = ("train", "validation", "test")
TOPICS = (
    "도시 철도",
    "산림 생태",
    "해양 관측",
    "전통 건축",
    "공공 도서관",
    "천문 관측",
    "지역 축제",
    "재생 에너지",
    "농업 기술",
    "기상 예보",
    "문화재 보존",
    "수자원 관리",
    "수어 교육",
    "응급 의료",
    "디지털 기록",
    "생활 체육",
    "식품 안전",
    "과학 교육",
)
ASPECTS = (
    "역사와 배경",
    "현장 조사",
    "자료 수집",
    "측정 기준",
    "운영 절차",
    "안전 원칙",
    "시민 참여",
    "환경 영향",
    "예산 계획",
    "교육 활용",
    "기술 변화",
    "품질 점검",
    "장기 보존",
    "지역 협력",
    "위험 대응",
    "성과 해석",
)
VERBS = (
    "비교한다",
    "기록한다",
    "검증한다",
    "설명한다",
    "분류한다",
    "관찰한다",
    "조정한다",
    "공개한다",
)
CONTEXTS = (
    "계절과 지역에 따른 차이",
    "관측 장비의 오차 범위",
    "이용자의 실제 요구",
    "법적 책임과 접근성",
    "장기 자료의 변화 추세",
    "현장 담당자의 점검 기록",
    "예상하지 못한 장애 상황",
    "공개 자료의 재현 가능성",
)
GUIDES = (
    "서로 다른 시기의 자료를 같은 단위로 환산하고 원본 값도 보존한다.",
    "현장 메모에는 날씨와 위치, 관찰자의 역할을 빠짐없이 적는다.",
    "수집 장치의 모델과 보정 날짜를 결과 표 옆에 표시한다.",
    "기준을 바꾼 경우 이전 판정과 새 판정을 나란히 비교한다.",
    "작업 순서마다 책임자와 완료 조건을 분리해 기록한다.",
    "위험 신호가 나타나면 중단 기준을 먼저 적용하고 원인을 조사한다.",
    "참여자의 의견은 익명화하고 반대 사례도 같은 비중으로 남긴다.",
    "환경 변화는 짧은 관찰과 장기 추세를 구분해 해석한다.",
    "예산 항목은 고정 비용과 변동 비용으로 나눠 예상 오차를 적는다.",
    "학습 자료에는 정답뿐 아니라 판단 과정과 흔한 실수를 포함한다.",
    "새 기술의 효과는 기존 방식과 같은 조건에서 비교한다.",
    "품질 점검자는 작성자와 독립적으로 표본을 다시 계산한다.",
    "보존 사본은 형식과 checksum, 복구 시험 날짜를 함께 관리한다.",
    "협력 기관 사이의 용어 차이를 표준 용어표로 조정한다.",
    "비상 대응은 연락망, 대체 절차, 복구 우선순위를 미리 연습한다.",
    "성과 보고에는 긍정적 결과와 한계, 미확인 가정을 함께 공개한다.",
)


def synthetic_term(value: int) -> str:
    """16k BPE vocab을 항상 채울 수 있는 고유한 한글 어휘 reservoir를 만든다."""

    syllables: list[str] = []
    for _ in range(4):
        syllables.append(chr(0xAC00 + value % 11_172))
        value //= 11_172
    return "".join(reversed(syllables))


def document_text(topic: str, document_index: int) -> str:
    """문서마다 다른 관점·어휘 순서를 사용해 충분히 긴 한국어 본문을 만든다."""

    sentences = [
        f"{topic} 문서는 작은 언어 모델의 결정적 실행을 검증하기 위한 합성 자료이다. "
        f"{topic} 사례는 실제 인물이나 비공개 기록을 인용하지 않고 절차와 관찰 방법을 "
        "중심으로 구성한다."
    ]
    for index, aspect in enumerate(ASPECTS):
        verb = VERBS[(document_index * 3 + index) % len(VERBS)]
        context = CONTEXTS[(document_index * 5 + index) % len(CONTEXTS)]
        guide = GUIDES[(document_index * 7 + index) % len(GUIDES)]
        sentences.append(
            f"{index + 1}번째 절에서는 {topic}의 {aspect}을 다룬다. 담당자는 {context}을 고려해 "
            f"입력 자료와 결과를 {verb}. {topic} 기록 원칙에 따라 {guide}"
        )
    sentences.append(
        f"마지막으로 {topic} 사례의 결론은 단일 수치로 과장하지 않는다. 관측된 증거와 해석, "
        "아직 확인하지 못한 조건, 다음 점검에서 바꿀 변수를 구분해 기록한다."
    )
    first = document_index * 3_000
    vocabulary = " ".join(synthetic_term(first + offset) for offset in range(3_000))
    sentences.append(
        f"{topic}의 tokenizer smoke 전용 합성 어휘 목록이다. 다음 항목은 자연어 지식이 아니라 "
        f"요청 vocab 크기를 결정적으로 채우기 위한 고유 한글 표본이다.\n{vocabulary}"
    )
    return "\n\n".join(sentences)


def build_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for document_index, topic in enumerate(TOPICS):
        split = SPLITS[document_index // 6]
        text = document_text(topic, document_index)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        identifier = document_index + 1
        document = Document(
            page_id=900_000 + identifier,
            revision_id=1_900_000 + identifier,
            title=f"LLMEX 결정적 smoke 문서: {topic}",
            text=text,
            source_url=f"https://example.invalid/llmex-smoke/{identifier}",
            dump_url="repo://docs/book/examples/build-smoke-corpus.py",
            dump_date="20260718",
            license="CC0-1.0; LLMEX 교재용 합성 문서",
            sha256=digest,
            quality=quality(text, {"synthetic_smoke_document": 1}),
            split=split,
        )
        rows.append(document.json_row())
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/book/smoke-corpus/corpus-v1.jsonl.zst"),
    )
    args = parser.parse_args()
    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = build_rows()
    write_jsonl_zst(output, rows)
    restored = [Document.model_validate(row) for row in read_jsonl_zst(output)]
    if [row.json_row() for row in restored] != rows:
        raise RuntimeError("기록한 corpus를 동일한 schema 행으로 복원하지 못했습니다")

    split_counts = {split: sum(row.split == split for row in restored) for split in SPLITS}
    if split_counts != {split: 6 for split in SPLITS}:
        raise RuntimeError(f"split 문서 수 계약 위반: {split_counts}")
    row_hashes = [row.sha256 for row in restored]
    if len(row_hashes) != len(set(row_hashes)):
        raise RuntimeError("split 사이에 중복 문서 hash가 있습니다")

    manifest = {
        "schema_version": 1,
        "generator": "docs/book/examples/build-smoke-corpus.py",
        "documents": len(restored),
        "splits": split_counts,
        "rows_fingerprint": fingerprint({"row_sha256": row_hashes}),
        "corpus_sha256": sha256_file(output),
    }
    manifest["fingerprint"] = fingerprint(manifest)
    manifest_path = output.with_name("corpus-v1.manifest.json")
    write_json(manifest_path, manifest)
    print(f"corpus={output} sha256={manifest['corpus_sha256']} splits={split_counts}")


if __name__ == "__main__":
    main()
