# 03. Wikipedia ingest, extract, clean, dedup, split

## 학습 목표

- 날짜·checksum이 고정된 dump를 안전하게 받는다.
- XML page를 문서 schema로 추출하고 attribution을 보존한다.
- 정제·중복 제거·문서 hash split을 결정적으로 수행한다.

## 선행지식

iterator, 압축 스트림, Unicode normalization과 hash가 필요하다.

## 관련 실제 파일

- [download](../../src/llmex/data/download.py), [extract](../../src/llmex/data/extract.py), [clean](../../src/llmex/data/clean.py)
- [dedup](../../src/llmex/data/dedup.py), [split](../../src/llmex/data/split.py), [pipeline](../../src/llmex/data/pipeline.py), [atomic IO](../../src/llmex/data/io.py)
- [데이터 테스트](../../tests/test_m1_data.py), [sample 설정](../../configs/data/sample.yaml), [데이터 보고서](../data-report.md)

## 핵심 개념과 수식

문서 split은 행 순서가 아니라 문서 내용 hash와 seed로 정한다. 예를 들어 `u = int(H(seed || document_hash)[:8],16)/2^32`로 균일값을 만든 뒤 임계값으로 train/validation/test를 선택한다. exact dedup은 normalized content hash, 선택적 near dedup은 character shingle MinHash/Jaccard를 쓴다.

\[
J(A,B)=\frac{|A\cap B|}{|A\cup B|}
\]

## 단계별 구현

1. metadata에서 dump 파일명·크기·checksum을 읽고 날짜 고정 URL인지 확인한다.
2. 임시 파일로 streaming download한 뒤 크기·SHA를 검증하고 원자 rename한다.
3. MediaWiki XML을 `iterparse`해 namespace 0·비 redirect page의 page/revision ID, title, text를 추출한다.
4. markup 정책을 적용하고 NFC, 공백, Hangul/markup/repetition 비율을 계산한다.
5. normalized text SHA로 exact dedup하고 필요할 때만 bounded near dedup을 수행한다.
6. document hash split 후 JSONL.ZST와 manifest/report/audit sample을 원자 publish한다.

```python
for event, elem in ET.iterparse(stream, events=("end",)):
    if local_name(elem.tag) == "page":
        row = extract_page(elem)
        if row and not row.redirect:
            yield clean_page(row)
        elem.clear()
```

## 실제 명령

```bash
uv run llmex data download --config configs/data/sample.yaml --dry-run
uv run llmex data sample-e2e --config configs/data/sample.yaml \
  --input tests/fixtures/kowiki-sample.xml.bz2 \
  --output-dir data/book/sample-corpus --max-documents 1000
uv run llmex data report --config configs/data/sample.yaml \
  --input data/book/sample-corpus/corpus-v1.jsonl.zst \
  --output data/book/sample-corpus/report.json
uv run pytest -q tests/test_m1_data.py
```

정식 실행 명령과 경로는 [실행 가이드](../run-guide.md)의 1~3절에서 현재 CLI 도움말과 함께 확인한다.

## 예상 산출물

fixture 실습은 `data/book/sample-corpus/` 아래에 단계별 compressed JSONL, `corpus-v1.jsonl.zst`, `data-manifest.json`, Markdown report와 audit sample을 만든다. 다만 현재 XML fixture는 M1의 변환·provenance·split 계약을 검증하기 위한 아주 작은 입력이라 유효 문서가 하나뿐이고 train split만 생길 수 있다. 따라서 256-token validation/test window가 필요한 04→07→08 capstone 입력으로 사용하지 않는다.

교재의 실행 가능한 학습 흐름은 [결정적 smoke corpus 생성기](examples/build-smoke-corpus.py)를 사용한다. 생성기는 완전한 `Document` schema와 provenance를 가진 서로 다른 합성 문서 18개를 train/validation/test에 6개씩 고정 배치하고, 원자적 JSONL.ZST와 corpus SHA manifest를 `data/book/smoke-corpus/`에 만든다. 정식 학습에서는 별도로 `data/processed/corpus-v1.jsonl.zst`를 사용한다.

## 검증 테스트

- checksum 오류·중간 download·공간 부족을 publish 전에 거부한다.
- redirect와 namespace 정책, markup 제거, NFC round-trip을 fixture로 확인한다.
- 입력 순서를 섞어도 문서 split이 같다.
- train/validation/test document hash 교집합이 0이다.
- capstone smoke corpus는 각 split이 256-token window보다 충분히 길다.
- 같은 fingerprint 출력은 재사용하고 다른 출력은 `--force`여도 덮지 않는다.

## 흔한 실패와 해결

- `latest` URL 사용: 실행 날짜에 따라 corpus가 바뀐다. 날짜 경로와 SHA를 pin한다.
- 문장 단위 random split: 같은 문서가 여러 split에 누출된다. 문서 hash 단위로 바꾼다.
- 정제 후 attribution 유실: 변환 전 provenance를 immutable 필드로 운반한다.
- 전체 XML 메모리 적재: streaming parse와 `elem.clear()`를 사용한다.

## 체크리스트

- [ ] dump date·URL·SHA가 고정됐다.
- [ ] attribution이 모든 최종 문서에 남는다.
- [ ] exact/near dedup 정책과 통계가 기록된다.
- [ ] split 교집합이 0이고 입력 순서에 독립적이다.
- [ ] manifest/report/audit sample이 현재 corpus에 결속된다.

## 연습문제

1. XML fixture에 redirect와 오래된 revision을 추가해 parser 동작을 고정하라.
2. near-dedup threshold 0.9의 오탐/미탐 예시를 만들어라.
3. split seed가 바뀌면 어떤 artifact fingerprint가 달라져야 하는지 나열하라.
