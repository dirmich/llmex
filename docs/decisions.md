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
- 결정: 정규화된 문서 본문의 SHA-256 hash로 train/validation/test를 나눈다.
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

## ADR-012: 독립 구현한 modern decoder와 SDPA 기준 경계

- 상태: 승인
- 배경: M3는 교재의 설명용 nano-GPT를 production dependency로 사용하지 않으면서 causal mask, RoPE offset, GQA와 mixed precision에서 일관된 동작을 제공해야 한다.
- 결정: bias 없는 Pre-Norm RMSNorm/RoPE/GQA/SwiGLU decoder를 typed PyTorch 모듈로 독립 구현한다. 기본 attention은 PyTorch SDPA를 사용하고 명시적 절대 위치 causal boolean mask를 전달한다. 수치 검증용 eager 구현은 같은 projection과 mask를 공유한다. embedding/LM head는 동일 Parameter를 사용하고 residual output projection에는 `1/sqrt(2L)` 초기화 scale을 적용한다.
- 대안: 교재 notebook class를 직접 옮기면 빠르지만 독립 구현·typing·cache 계약을 충족하지 못한다. `is_causal=True`만 사용하면 KV cache offset query에서 mask 의미가 모호해질 수 있다. 별도 LM head 복사는 저장공간과 파라미터를 불필요하게 늘린다.
- 결과: eager correctness를 기준으로 CPU에서 항상 검증할 수 있고, SDPA가 실행 환경에 맞는 backend를 선택한다. KV cache는 v1.1 공개 CLI보다 먼저 내부 API로 제공하되 cache 없는 forward와 동일 logits/생성 결과를 유지한다.
- 검증: 수식 tensor, SDPA/eager parity, 미래 token leakage 0, cache parity, finite gradient, state dict round-trip, 128문서 overfit과 inspect artifact를 통과해야 한다.

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

## ADR-013: 상태 완전 복구형 단일 프로세스 trainer

- 상태: 승인
- 배경: optimizer와 모델만 저장하면 재개 직후 데이터 순서, dropout, scheduler와 mixed precision scale이 달라져 동일한 학습으로 볼 수 없다.
- 결정: token shard의 전역 연속 window를 epoch별 결정적 순열로 표본화하고 epoch/cursor를 저장한다. checkpoint에는 모델, AdamW, scheduler step, scaler, Python·NumPy·CPU/CUDA PyTorch RNG, train/validation sampler, best validation과 입력 fingerprint를 함께 저장한다. 보존형 step 파일과 `latest.pt`, `best.pt`는 임시 파일을 `fsync`한 뒤 atomic rename한다.
- 대안: PyTorch DataLoader의 일반 shuffle은 worker prefetch 상태까지 재현하기 어렵다. 문서별 무작위 표본화는 짧은 문서 편향과 shard 경계 계약을 복잡하게 한다. 외부 실험 추적기는 오프라인·로컬 재현 요구에 맞지 않는다.
- 결과: 기본 경로는 worker 0인 단일 프로세스이며 checkpoint 직후 재개가 CPU에서 bitwise 동일하다. bf16은 scaler를 사용하지 않고 fp16 CUDA만 GradScaler를 사용한다. config/corpus/tokenizer/model/shard fingerprint가 하나라도 다르면 재개를 거부한다.
- 검증: shard 경계 window, sampler 복구, accumulation 동등성, LR 경계, CPU 50-step overfit, bitwise 중단·재개, 손상 checkpoint/shard와 NaN 오류주입, CLI train/resume/smoke를 자동 검사한다.

## ADR-014: 검증 가능한 KV cache와 fingerprint 봉인 평가 artifact

- 상태: 승인
- 배경: 추론 최적화가 cache 없는 모델의 수치 의미를 바꾸거나, 서로 다른 checkpoint·tokenizer·shard를 섞은 평가가 정상 결과처럼 저장되면 비교 실험을 신뢰할 수 없다.
- 결정: prompt 전체 prefill 뒤 layer별 RoPE 적용 K/V를 저장하고 이후 token의 절대 position offset을 누적한다. 명시적 causal mask를 cache/no-cache 양쪽에 공유한다. 평가 runtime은 학습 config, model, corpus, tokenizer, shard fingerprint와 checkpoint checksum을 모두 확인한다. JSON/Markdown은 payload fingerprint와 별도 checksum manifest로 봉인한다.
- 대안: `is_causal=True`와 동적 cache 구현은 간단하지만 offset query mask 의미를 backend에 맡긴다. checkpoint만 읽고 모델 YAML을 사용하면 tokenizer·데이터 혼합을 탐지하지 못한다. 외부 평가 framework는 범위가 크고 현재 오프라인·한국어 artifact 계약을 직접 충족하지 않는다.
- 결과: cache/no-cache logits와 greedy 생성이 동등하며 sampling seed, EOS, 문맥 제한이 명시적으로 재현된다. artifact 비교 시 입력과 파일 무결성을 함께 확인할 수 있다.
- 검증: CPU logits/생성 parity, top-k/top-p/temperature/seed/repetition, EOS/max token/context, checksum 변조·fingerprint 불일치, CLI E2E와 가능한 CUDA latency-memory smoke를 통과해야 한다.

## ADR-015: M6 로컬 완료와 외부 baseline 완료의 분리

- 상태: 승인
- 배경: 전체 dump 처리, 100건 사람 판정, 100-step DGX benchmark와 장기 학습은 코드 구현 완료 여부와 달리 네트워크·장비·시간 승인이 필요하다.
- 결정: `llmex pipeline`이 로컬 단계, 자원 예산, 외부 증거 목록, 단계 상태와 재개 명령을 fingerprint로 봉인한다. 외부 단계는 `required_evidence`가 모두 존재하고 `--allow-external`을 명시한 경우에만 실행한다.
- 결과: 외부 작업을 실행하지 않고 완료로 표시할 수 없다. 120M 초과 모델은 100M baseline 완료 전 설정 검증에서 거부한다.
- 검증: fixture E2E에서 외부 증거 누락 대기, 승인 후 재개, 출력 확인, 실패 복구 drill과 JSON/Markdown export를 검사한다.

## ADR-016: 87.8M·16k baseline 선택

- 상태: 승인
- 결정: 12층, 폭 768, GQA 12/4, context 1024, SwiGLU 2048, vocab 16k의 정확히 87,804,672 파라미터 프로파일을 첫 baseline으로 고정한다. token budget은 최대 6,553,600,000개다.
- 이유: 16k는 embedding 비용을 낮추고 기존 byte fallback/UNK 0 계약을 유지한다. 32k가 실제 전체 corpus에서 유의미한 sequence 감소를 증명하면 별도 ADR로 변경한다.
- 검증: 두 tokenizer의 동일 10,000문서 효율 JSON이 없으면 선택 gate는 대기 상태다. 현재 선택은 예산상 기본값이지 실제 비교 승인이 아니다.

## ADR-017: 1.0 도구 릴리스와 외부 공개 결정 분리

- 상태: 승인
- 배경: 코드·문서·패키지의 로컬 완료와 전체 데이터 장기 학습, 법적 해석, 공개 배포 권한은 서로 다른 증거와 책임자를 요구한다.
- 결정: 1.0.0은 재현 가능한 도구와 실패-폐쇄 gate의 안정 릴리스로 정의한다. 법무 검토, 장기 baseline, 공개 배포 결정은 승인자·시각·근거를 가진 외부 승인 없이는 통과하지 않는다.
- 대안: 문서 체크박스만 두는 방식은 자동 배포가 미승인 상태를 우회할 수 있어 폐기했다. 가중치 라이선스를 프로젝트가 임의 지정하는 방식도 법률 검토 전에는 채택하지 않는다.
- 결과: 로컬 acceptance와 외부 공개 acceptance를 명확히 분리하며 현재 공개 판정은 금지다. checksum, SBOM, provenance는 공급망 증거이지 법률·안전 승인을 대체하지 않는다.
- 검증: 누락·빈·부분 승인 JSON이 종료 코드 5로 실패하고 세 완전 승인만 통과해야 한다. `0.ref`, raw data, checkpoint는 wheel 경계 밖이어야 한다.

## ADR-018 — 1.1.0 artifact·split hash 단일 계약

- **결정:** 문서 split 식별자는 정규화된 문서 본문의 SHA-256(`document_sha256`)이며 page ID/title hash가 아니다. 구현과 `docs/data-report.md`의 계약을 이 정의로 고정한다.
- **결정:** JSON/artifact와 sidecar는 임시 파일 fsync → 원자 rename → 디렉터리 fsync 순서를 공유한다. 재개 상태에는 출력 SHA-256·byte 크기·JSON schema version을 봉인하고 재개 전에 다시 계산한다.
- **결정:** ADR 계약 변경은 구현·회귀 테스트·이 문서를 한 버전에서 함께 변경해야 하며 불일치는 무결성 실패다.

## ADR-019 — 1.2.0 보호 CI 신뢰 경계

- **결정:** release와 pipeline 외부 진술은 approval 파일 경로가 아니라 명시 Git 최상위
  subject repository와 canonical HEAD commit에 결속한다.
- **권위:** HEAD에 byte 단위로 봉인되고 group/other 쓰기가 금지된
  `.llmex/trust-policy.json`만 issuer key digest, exact role과 kind를 정한다. 프로세스 환경은
  policy digest에 맞는 보호 signing material을 운반할 뿐 policy를 새로 정의하지 못한다.
- **실패-폐쇄:** 잘못된 Git root/commit, role/kind/시각/config/artifact/서명, 만료와 변조를
  거부한다. 외부 stage의 최종 서명 token/energy telemetry가 없으면 실행하지 않는다.
- **평가·원자 계약:** 평가 near contamination은 문자 5-gram Jaccard이며 MinHash가 아니다.
  canary provenance 부재는 미실행/실패다. JSONL.ZST와 dashboard Markdown도 file/directory
  fsync 뒤 atomic replace한다.
