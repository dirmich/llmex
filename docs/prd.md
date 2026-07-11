# LLMEX 제품 요구사항 문서

## 1. 제품 정의

LLMEX는 한국어 Wikipedia의 최신 확정 덤프를 정제하고 한국어용 byte-level BPE 토크나이저와 decoder-only Transformer를 처음부터 학습하는 재현 가능한 교육·연구 프로젝트다. 기반 교재의 Ch 12 토크나이저, Ch 14–18 Attention/Transformer/GPT, Ch 19 사전학습, Ch 31 nano-GPT를 하나의 실제 파이프라인으로 연결한다.

LLMEX의 1차 결과는 상용 수준의 범용 LLM이 아니다. 제한된 단일 GPU에서도 데이터 수집부터 평가까지 검증할 수 있는 **소형 한국어 base language model**과 재현 가능한 학습 시스템이다.

## 2. 문제와 사용자

### 문제

- 교재의 장별 예제만으로는 실제 대규모 말뭉치 정제, 토크나이저 학습, 체크포인트 복구, 평가와 라이선스 추적을 경험하기 어렵다.
- 한국어는 조사·어미와 UTF-8 특성 때문에 영문 중심 토크나이저를 그대로 쓰면 토큰 효율이 낮을 수 있다.
- Wikipedia 학습은 데이터 버전, 원문 출처, 라이선스, 누출과 암기 위험을 함께 관리해야 한다.

### 주요 사용자

1. 교재를 끝낸 뒤 작은 GPT를 실제로 학습하려는 개발자
2. 한국어 토크나이저와 사전학습을 실험하려는 연구자
3. GPU 예산 안에서 재현 가능한 baseline이 필요한 학습자

## 3. 목표

- 주어진 dump date와 config로 동일한 데이터셋·토크나이저·모델을 재생성한다.
- 한국어 Wikipedia 본문을 정제해 문서 경계를 보존한 train/validation/test corpus를 만든다.
- byte-level BPE를 학습하고 한국어 토큰 효율과 round-trip을 검증한다.
- Pre-LN, RMSNorm, RoPE, GQA, SwiGLU 기반 causal decoder를 구현한다.
- CPU smoke와 단일 GPU baseline 학습을 모두 지원한다.
- loss, perplexity, throughput, MFU 근사치, 메모리, 생성 샘플을 기록한다.
- checkpoint 저장·재개가 결정적이며 중단 전후 학습이 이어진다.
- 학습 데이터 attribution과 라이선스 문서를 모델 배포물에 포함한다.
- 암기, 개인정보, 유해 출력과 알려진 한계를 model card에 기록한다.

## 4. 비목표

- Wikipedia 사실을 항상 정확히 답하는 production QA 서비스
- 웹 검색이나 RAG를 이용한 최신 정보 제공
- ChatGPT 수준의 대화 정렬, RLHF, DPO
- 수십억 파라미터 분산학습을 MVP 필수 범위로 포함
- Wikipedia 이미지, Commons 파일, 토론·사용자 페이지 학습
- 학습 모델의 무검토 상업 배포

## 5. 성공 지표

### 데이터

- dump checksum 검증 성공
- namespace 0 본문만 포함하고 redirect, 빈 문서, 목록성 잔해를 정책대로 처리
- 모든 샘플에 `page_id`, `title`, `revision_id`, `source_url`, `dump_date`, `license` 추적 가능
- exact duplicate 0건, near-duplicate 비율 보고
- 문서 단위 split로 한 문서가 여러 split에 나타나지 않음

### 토크나이저

- 임의 Unicode/한글 표본 10,000건 encode-decode round-trip 100%
- special token ID가 config와 일치
- test corpus의 UNK 0건(byte fallback)
- chars/token, bytes/token, tokens/word를 baseline과 비교 보고

### 모델과 학습

- shape, causal mask, weight tying, RoPE, GQA, loss shift 단위 테스트 통과
- 128개 문서 overfit test에서 loss가 명확히 감소
- CPU smoke 50 step 완주
- validation loss가 무작위 초기값 대비 감소
- 동일 seed/config의 초기 20 step loss가 허용 오차 내 재현
- checkpoint 재개 후 step, optimizer, scheduler, scaler, RNG 상태 복원
- NaN/Inf 발생 시 실패하고 진단 artifact 생성

### 평가와 배포

- held-out perplexity와 Korean Wikipedia cloze benchmark 기록
- train/test contamination 검사 보고서 존재
- canary 문자열 암기 검사가 기준 이하 또는 위험 명시
- model card, data card, license/attribution, config, tokenizer, checkpoint manifest 포함

## 6. 사용자 시나리오

### S1. 로컬 smoke

개발자가 작은 샘플 덤프로 전처리하고 5M 이하 모델을 CPU/MPS에서 50 step 학습해 전체 파이프라인을 확인한다.

### S2. 단일 GPU baseline

연구자가 확정 날짜의 전체 한국어 Wikipedia를 내려받아 25M–120M 모델을 학습하고 W&B 없이도 로컬 JSONL 지표와 checkpoint를 얻는다.

### S3. 비교 실험

연구자가 vocab size, context length, GQA head 수, model width를 바꾸되 데이터 split과 평가셋을 고정해 결과를 비교한다.

### S4. 학습 재개

프로세스가 중단된 뒤 마지막 원자적 checkpoint에서 재개하고 데이터 순서와 scheduler가 올바르게 이어진다.

## 7. 기능 요구사항

### FR-1 설정

- 모든 실행은 YAML config와 CLI override를 받는다.
- config에는 seed, dump URL/date/hash, 정제 정책, tokenizer, model, optimizer, scheduler, precision, device, output path가 포함된다.
- 실행 시 resolved config와 Git commit을 run directory에 저장한다.

### FR-2 데이터 획득

- 기본 입력은 `kowiki-<date>-pages-articles-multistream.xml.bz2`다.
- `latest` URL은 탐색에만 쓰고 학습 run에는 날짜가 고정된 URL과 checksum을 기록한다.
- 이어받기 다운로드, timeout, 재시도, disk-space 사전 검사, checksum 검증을 제공한다.
- 덤프 원본은 immutable raw 영역에 둔다.

### FR-3 추출과 정제

- XML stream parser로 메모리를 제한한다.
- MediaWiki markup은 검증된 parser/extractor를 사용한다.
- namespace 0만 사용하고 redirect를 제외한다.
- 표, 수식, 목록, 참조를 무조건 삭제하지 않고 정책과 통계를 남긴다.
- Unicode NFC 정규화, 제어문자 제거, 공백 정리, 최소 길이 필터를 적용한다.
- 문서 경계와 attribution metadata를 보존한 JSONL.ZST/Parquet을 만든다.
- deterministic document-hash split을 사용한다.

### FR-4 중복·품질 필터

- 정규화된 본문의 exact hash dedup을 수행한다.
- MinHash/LSH near-dedup은 선택 기능으로 두고 제거 통계를 남긴다.
- 짧은 문서, 비한국어 비율, 반복 문자, markup 잔존 비율을 측정한다.
- 필터 전후 문서·문자·byte 수와 사유별 제거량을 data report에 기록한다.

### FR-5 토크나이저

- Hugging Face `tokenizers`의 byte-level BPE를 기본으로 한다.
- `<pad>`, `<bos>`, `<eos>`, `<unk>` ID를 고정한다.
- tokenizer 학습 corpus는 train split만 사용한다.
- vocab size 16k/32k 비교가 가능하다.
- tokenizer artifact, vocab, merges, config, corpus fingerprint를 저장한다.

### FR-6 packing

- 각 문서 끝에 EOS를 넣고 문서 경계를 기록한다.
- token ID를 memory-mapped shard로 저장한다.
- shard별 token count, checksum, 최소/최대 ID를 manifest에 기록한다.
- validation/test는 train과 동일한 tokenizer를 사용한다.

### FR-7 모델

- decoder-only causal LM
- token embedding과 LM head weight tying
- Pre-Norm RMSNorm
- RoPE positional encoding
- GQA(MHA로 설정 가능)
- SwiGLU FFN
- dropout configurable
- PyTorch SDPA 사용, CPU fallback 제공
- parameter count와 메모리 예측 출력

### FR-8 학습

- AdamW, decoupled weight decay, warmup + cosine decay
- gradient accumulation, gradient clipping
- bf16 우선, 지원하지 않으면 fp16/float32 fallback
- deterministic seed와 dataloader state 관리
- 주기적 validation, sample generation, metric JSONL
- 원자적 `latest`와 보존형 step checkpoint
- graceful SIGTERM checkpoint
- MPS는 smoke 지원, 본학습은 CUDA 기준

### FR-9 평가

- token-level NLL/perplexity
- 고정 Korean Wikipedia cloze set
- spacing, 조사·어미, 고유명사, 숫자·날짜가 포함된 generation prompt set
- repetition, distinct-n, invalid Unicode, stop behavior
- exact/near train contamination
- canary exposure 및 긴 구절 암기 검사
- baseline(작은 모델/빈도 모델)과 비교

### FR-10 추론

- CLI prompt 입력, temperature, top-k, top-p, max-new-tokens, seed
- KV cache는 v1.1 목표이며 MVP에서는 없어도 됨
- 생성 결과에 모델/checkpoint/tokenizer ID 기록

### FR-11 문서화·배포

- data card, model card, training report, evaluation report 자동 초안
- Wikipedia 텍스트의 CC BY-SA/GFDL 재사용 조건과 attribution을 명시
- 모델 가중치의 라이선스는 법률 검토 없이 자동 단정하지 않음
- 원 데이터는 패키지에 재배포하지 않고 다운로드·재현 스크립트 제공

## 8. 비기능 요구사항

- Python 3.11+, PyTorch 2.x
- `src/` layout, typed public functions, Ruff/Pyright/Pytest
- 단계별 idempotent CLI와 `--dry-run`
- raw/interim/processed/artifact/run 디렉터리 분리
- secret을 config와 Git에 저장하지 않음
- 네트워크가 필요한 단계와 오프라인 단계를 분리
- 모든 큰 파일은 Git에서 제외하고 manifest만 추적
- 단위 테스트는 외부 네트워크와 GPU 없이 실행

## 9. 데이터와 라이선스

- 공식 덤프: `https://dumps.wikimedia.org/kowiki/<YYYYMMDD>/`
- 대상 파일: `kowiki-<date>-pages-articles-multistream.xml.bz2`
- 2026-03 dump 기준 결합 파일은 약 1.34GB이므로 저장공간은 원본·추출·토큰·checkpoint를 합쳐 최소 수십 GB를 사전 확보한다.
- multistream은 여러 bzip2 stream을 연결한 형식이다. 호환되지 않는 오래된 해제 도구를 사용하지 않는다.
- Wikipedia 텍스트의 라이선스와 attribution 의무는 재배포 형태에 따라 검토한다. source URL, title, revision ID, dump date를 보존한다.
- 개인정보·명예훼손·저작권 침해 가능성이 있는 문장이 덤프에 존재할 수 있음을 data/model card에 명시한다.

## 10. MVP 모델 프로파일

| 프로파일 | 용도 | layers | d_model | heads/kv | context | 대략 규모 |
|---|---|---:|---:|---:|---:|---:|
| smoke | CPU/MPS E2E | 4 | 128 | 4/2 | 256 | <5M + vocab |
| baseline | 단일 GPU | 12 | 768 | 12/4 | 1024 | 약 100M |
| medium | 후속 실험 | 16–24 | 1024 | 16/4 | 2048 | 자원 검토 후 |

정확한 파라미터 수와 VRAM은 구현된 vocab/FFN/weight tying 기준으로 계산한다. baseline은 GPU 메모리에 따라 `d_model=512` 또는 context를 낮출 수 있지만 변경 이유를 run manifest에 기록한다.

### 확정 실행 환경: NVIDIA DGX Spark

- Grace Blackwell GB10, ARM64 CPU 20-core
- CPU와 GPU가 공유하는 128GB LPDDR5x unified memory
- 메모리 대역폭 273GB/s
- 1TB 또는 4TB NVMe이므로 실제 장비 용량을 M0에서 기록
- DGX OS, CUDA, Docker와 NVIDIA Container Runtime 사용

DGX Spark는 전용 VRAM과 시스템 RAM이 분리된 일반 GPU 서버가 아니다. 따라서 `nvidia-smi`의 framebuffer memory 수치만으로 가용 메모리를 판단하지 않고 프로세스 RSS, system available memory, PyTorch peak allocation, swap을 함께 기록한다. 128GB를 전부 모델에 할당하지 않으며 OS, dataloader, page cache와 checkpoint 저장을 위한 headroom을 둔다.

MVP는 100M baseline을 먼저 완료한다. 이후 pilot 실측에서 안정적이면 300M–500M 프로파일을 추가한다. 128GB에 들어간다는 이유만으로 학습 시간과 데이터 token budget을 검증하지 않은 대형 모델을 시작하지 않는다.

## 11. 단계별 출시 기준

### MVP-0 파이프라인

샘플 XML에서 `download -> extract -> clean -> split -> tokenize -> pack`이 재현되고 data tests가 통과한다.

### MVP-1 모델

smoke 모델이 overfit test와 CPU 50-step 학습, checkpoint resume를 통과한다.

### MVP-2 baseline

고정 Wikipedia snapshot에서 단일 GPU baseline이 학습되고 validation/evaluation report가 생성된다.

### MVP-3 공개 후보

라이선스·attribution·data/model card·암기/안전 평가와 독립 리뷰를 통과한다.

## 12. 위험과 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| “LLM” 기대와 소형 모델 품질 차이 | 목표 실패 오해 | base LM/교육용 범위를 UI와 model card에 명시 |
| Wikipedia만 사용한 도메인 편향 | 대화·일상문 약함 | 평가에서 명시, 후속 corpus 혼합은 별도 실험 |
| markup 정제 손실 | 문맥 훼손 | 원문/정제 샘플 diff와 필터 통계 |
| 데이터 누출 | 평가 과대평가 | 문서 hash split, contamination 검사 |
| 암기와 개인정보 | 배포 위험 | canary/long-match 검사, 공개 전 수동 검토 |
| GPU OOM/비용 | 학습 중단 | dry-run 메모리 예측, smoke, grad accumulation, checkpoint |
| 라이선스 해석 오류 | 배포 위험 | attribution 보존, 법률 검토 전 가중치 라이선스 단정 금지 |
| latest dump 변경 | 재현 불가 | 날짜 URL과 checksum 고정 |

## 13. 미해결 결정

- 실제 GPU 종류와 학습 예산
- baseline 목표 token 수
- 모델 가중치 공개 여부와 라이선스 검토
- 전체 덤프 near-dedup 적용 비용
- 후속 instruction tuning 데이터의 출처

이 항목은 구현을 막지 않는다. M0–M2는 smoke profile로 진행하고, baseline 실행 전에 자원 ADR을 확정한다.

## 14. 공식 근거

- [한국어 Wikipedia 공식 dump](https://dumps.wikimedia.org/kowiki/latest/)
- [Wikimedia dump 형식](https://meta.wikimedia.org/wiki/Data_dumps/Dump_format)
- [다운로드 가능한 dump 종류](https://meta.wikimedia.org/wiki/Data_dumps/What%27s_available_for_download)
- [Wikimedia 이용 및 라이선스 조건](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)
- [NVIDIA DGX Spark 시스템 개요](https://docs.nvidia.com/dgx/dgx-spark/system-overview.html)
- [NVIDIA DGX Spark 하드웨어 사양](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)
- [NVIDIA Container Runtime](https://docs.nvidia.com/dgx/dgx-spark/nvidia-container-runtime-for-docker.html)
- [DGX Spark 알려진 이슈](https://docs.nvidia.com/dgx/dgx-spark/known-issues.html)
