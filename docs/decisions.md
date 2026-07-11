# LLMEX 결정 기록

## ADR-001: 처음부터 학습하는 base LM

- 상태: 승인
- 결정: 기존 모델 RAG/파인튜닝이 아니라 한국어 Wikipedia로 decoder-only LM을 처음부터 학습한다.
- 이유: 기반 교재의 토크나이저, Attention, 사전학습을 end-to-end로 검증하는 것이 핵심이다.
- 결과: 상용 챗봇 품질은 비목표이며 모델 한계를 명확히 공개한다.

## ADR-002: 날짜 고정 Wikimedia dump

- 상태: 승인
- 결정: 탐색은 `latest`, 실험은 날짜 URL과 checksum을 사용한다.
- 이유: `latest`는 시간이 지나면 다른 데이터가 되어 재현성을 깨뜨린다.

## ADR-003: 문서 단위 split

- 상태: 승인
- 결정: 정규화된 page ID/title hash로 train/validation/test를 나눈다.
- 이유: 같은 문서의 chunk가 여러 split에 들어가는 누출을 방지한다.

## ADR-004: byte-level BPE

- 상태: 승인
- 결정: Hugging Face tokenizers 기반 byte-level BPE와 byte fallback을 쓴다.
- 이유: 임의 Unicode를 표현하고 한국어 corpus에 맞는 어휘를 학습한다.

## ADR-005: 소형 modern decoder

- 상태: 승인
- 결정: Pre-Norm RMSNorm, RoPE, GQA, SwiGLU, tied embeddings, causal LM을 기본으로 한다.
- 이유: 교재의 nano-GPT를 유지하면서 현대적 구조를 실험 가능한 최소 단위로 구현한다.

## ADR-006: 전체 표본보다 검증 게이트 우선

- 상태: 승인
- 결정: sample/smoke/baseline 프로파일을 분리하고 sample E2E 통과 전 전체 dump와 GPU 학습을 금지한다.
- 이유: 데이터·shape·resume 오류를 비싼 학습 전에 발견한다.

## ADR-007: DGX Spark ARM64 컨테이너 실행

- 상태: 승인
- 결정: 본학습과 재현 환경은 DGX Spark의 NVIDIA Container Runtime과 버전 고정 NGC PyTorch ARM64 호환 이미지를 사용한다.
- 이유: Grace Blackwell, CUDA, PyTorch 조합을 host Python에 임의 설치하는 것보다 재현성과 호환성이 높다.
- 결과: source, data, artifacts, runs는 host NVMe volume에 두고 container 삭제와 무관하게 보존한다.

## ADR-008: unified memory headroom

- 상태: 승인
- 결정: 128GB unified memory의 최대 80%를 정상 운용 상한의 출발점으로 삼고 pilot 실측 후 조정한다.
- 이유: GPU와 CPU, OS, dataloader, page cache가 같은 메모리를 공유하며 과도한 swap은 학습을 사실상 정지시킬 수 있다.
- 결과: RSS, available memory, swap, PyTorch peak memory를 동시에 관측한다.

## ADR-009: 엄격한 YAML과 JSON 구조화 로그

- 상태: 승인
- 결정: YAML은 Pydantic strict 모델로 검증하고 알 수 없는 키와 암묵적 타입 변환을 거부한다. CLI 로그는 stderr JSON Lines, 결과는 stdout으로 분리한다.
- 이유: 오타가 조용히 기본값으로 바뀌는 재현성 문제를 막고 자동화가 오류 코드를 안정적으로 판별하게 한다.
- 검증: 잘못된 타입·알 수 없는 키·형상 불변조건·CLI 종료 코드 테스트를 통과해야 한다.

## ADR-010: 표준 라이브러리 기반 보수적 MediaWiki parser

- 상태: 승인
- 배경: M1은 외부 네트워크 없이 fixture를 처리하고, 표·수식·목록·참조 정책과 제거량을 결정적으로 재현해야 한다. `mwparserfromhell`, `mwxml`, WikiExtractor를 비교했다.
- 결정: XML은 Python `bz2`와 `xml.etree.ElementTree.iterparse`로 streaming 처리하고, markup은 정책이 명시된 보수적 parser를 프로젝트 안에 구현한다. namespace 0, redirect 제외, 마지막 revision 선택을 추출 경계에서 강제한다.
- 대안: `mwxml`은 dump 순회 API가 좋지만 추가 의존성이 필요하고 markup을 정제하지 않는다. `mwparserfromhell`은 문법 범위가 넓지만 템플릿 확장 결과를 제공하지 않으며 추가 의존성과 버전 고정이 필요하다. WikiExtractor는 검증된 대규모 추출기지만 출력 정책을 세밀하게 통계화하고 schema attribution을 직접 보존하기 어렵다.
- 결과: 표와 참조는 제거하고, 수식·목록·내부 링크의 표시 텍스트는 보존한다. 템플릿은 확장하지 않고 제거한다. 이 parser는 MediaWiki 렌더러와 동등하지 않으므로 잔존 markup 비율 필터와 샘플 감사를 필수로 둔다.
- 검증: 확장 XML fixture의 최신 revision, namespace/redirect, 표·참조 제거, 수식·목록 보존 golden test와 결정적 E2E hash test를 통과해야 한다.

## ADR-011: 결정적 byte-level BPE와 문서 경계 shard

- 상태: 승인
- 배경: 한국어 완성형·자모·정규화 형식과 임의 Unicode를 손실 없이 처리하면서 토크나이저 학습 데이터 누출과 shard 경계 손실을 막아야 한다.
- 결정: Hugging Face `tokenizers` BPE에 ByteLevel pre-tokenizer/decoder, 전체 initial byte alphabet과 byte fallback을 사용한다. `<pad>`, `<bos>`, `<eos>`, `<unk>`는 각각 0, 1, 2, 3으로 고정하고 학습 iterator는 train split만 노출한다. 각 source 문서 뒤에 EOS를 붙인 뒤 연속 token stream을 고정 크기 little-endian memmap shard로 나눈다.
- 대안: 문자 토크나이저는 단순하지만 sequence가 길고, SentencePiece는 유효한 대안이나 M2의 Hugging Face artifact 계약과 맞지 않는다. 문서별 shard는 경계가 명확하지만 작은 파일이 지나치게 많아진다.
- 결과: 16k/32k 설정을 모두 제공하고 실제 vocab 최대 ID에 따라 `uint16` 또는 `uint32`를 자동 선택한다. tokenizer/corpus fingerprint, source 경계, checksum, token 수, 최소/최대 ID를 manifest에 기록한다.
- 검증: 특수 ID, UNK 0건, 임의 유효 Unicode round-trip, train-only fitting, split 누출 거부, EOS/next-token 정렬, 원자적 shard와 두 번 실행 checksum 동일성을 통과해야 한다.

## ADR 템플릿

```text
## ADR-NNN: 제목
- 상태: 제안/승인/폐기
- 배경:
- 결정:
- 대안:
- 결과:
- 검증:
```
