# M1 Wikipedia 데이터 리포트

## 데이터 계약

- 입력은 날짜가 URL에 포함된 `kowiki-<YYYYMMDD>-pages-articles-multistream.xml.bz2`와 SHA-256이다.
- raw 파일은 checksum 검증 뒤 읽기 전용으로 승격하고 `*.manifest.json`에 URL, 날짜, 기대/실제 checksum, byte 수를 기록한다.
- 출력은 schema v1 JSONL.ZST이며 page/revision ID, 제목, 본문, source/dump URL, dump 날짜, 라이선스 고지, 본문 SHA-256, 품질 통계, split을 보존한다.
- split은 seed와 document SHA-256의 hash로 train 98%, validation 1%, test 1%를 결정한다.

## 정제 및 필터 정책

| 항목 | 정책 | 통계 키 |
|---|---|---|
| 표 | `{| ... |}` 블록 제거 | `policy_tables_dropped` |
| 참조 | `<ref>` 본문과 self-closing tag 제거 | `policy_references_dropped` |
| 수식 | `<math>` tag만 제거하고 식 문자열 보존 | `policy_math_as_text` |
| 목록 | marker를 제거하고 항목 텍스트 보존 | `policy_list_items_kept` |
| 내부/외부 링크 | URL을 제거하고 표시 문자열 보존 | `policy_links_kept`, `policy_external_links_kept` |
| 템플릿 | 확장하지 않고 중첩 안쪽부터 제거 | `policy_templates_dropped` |
| Unicode | NFC, 제어/format 문자 제거, 공백과 빈 줄 정리 | 품질 수치에 반영 |

최소 문자 수, 한글 비율 하한, 단일 문자 반복 비율 상한, markup 잔존 비율 상한을 적용한다. 정규화 본문의 SHA-256 exact dedup은 항상 켜진다. 선택적 near-dedup은 외부 의존성 없이 문자 n-gram shingle과 seed 0–63의 SHA-256 MinHash signature를 사용한다. 입력 순서, shingle 크기, threshold가 같으면 결정적이지만 LSH index가 아닌 선형 비교이므로 전체 dump에서는 비용을 측정한 뒤 활성화한다.

## CLI 실행

```bash
uv run llmex data download --config configs/data/sample.yaml --dry-run
uv run llmex data extract --config configs/data/sample.yaml --input data/raw/<dump>.xml.bz2 --output data/interim/extracted.jsonl.zst --max-documents 1000
uv run llmex data clean --config configs/data/sample.yaml --input data/interim/extracted.jsonl.zst --output data/interim/cleaned.jsonl.zst
uv run llmex data dedup --config configs/data/sample.yaml --input data/interim/cleaned.jsonl.zst --output data/interim/deduplicated.jsonl.zst
uv run llmex data split --config configs/data/sample.yaml --input data/interim/deduplicated.jsonl.zst --output data/processed/corpus-v1.jsonl.zst
uv run llmex data report --config configs/data/sample.yaml --input data/processed/corpus-v1.jsonl.zst --output data/processed/data-manifest.json
```

실제 날짜 고정 dump의 1,000문서 canary와 100건 감사 초안은 다음 한 명령으로 만든다.

```bash
uv run llmex data sample-e2e --config configs/data/sample.yaml \
  --input data/raw/kowiki-20260701-pages-articles-multistream.xml.bz2 \
  --output-dir data/processed/canary-1000 --max-documents 1000
```

`audit-sample.json`에는 최대 100건의 본문 preview와 품질/attribution, 빈 수동 판정 필드가 들어가며 `audit-sample.md`는 검토 표다. 문서가 100건보다 적으면 존재하는 문서만 기록한다. 모든 명령은 `--dry-run`, `--force`를 지원하며, `--force`도 다른 입력·설정 fingerprint의 기존 출력은 덮어쓰지 않는다.

## 현재 검증 범위

- 완료: 외부 네트워크 없는 확장 fixture smoke, 손상 checksum, local HTTP Range resume, namespace/redirect/latest revision, markup golden, 품질 필터, attribution, exact/near dedup, split 상호 배타성, schema v1 ZST round-trip, deterministic E2E corpus hash.
- 실제 실행: 2026-07-11에 `20260701` dump 1,398,909,939 bytes를 다운로드했다. 공식 SHA-1과 일치했고 로컬 SHA-256은 `991b26eb4588d2eddafd472a3b7dd2a8503740fb3e6c46d14baeef60d83e5582`다. 1,000문서 canary에서 997문서가 통과했고 exact 중복 0, train/validation/test 978/10/9였다. 자동 감사 100건 artifact는 생성했으나 사람 판정은 미완료다.
- 미실행: 전체 dump의 모든 문서 정제와 100건 사람 검토.
