# LLMEX 개발 TODO

## 1.7.0 비누출 SFT mix 완료 및 정식 teacher 수집 진행

### 완료

- [x] Wikipedia dump `20260701` 고정 및 SHA-256 검증
- [x] extraction 753,081 → clean 747,718 → dedup 747,532(exact duplicates 186) → split 732,393/7,521/7,618
- [x] `data/processed/corpus-v1.jsonl.zst` 711,548,455 bytes 및 SHA-256 검증
- [x] `artifacts/tokenizers/bpe-16k` 실측: chars/token 1.990337, bytes/token 4.400516, tokens/word 2.346399, byte reduction 77.275394%, UNK 0, Unicode 10,000
- [x] CarrotAI revision `5c0e2c0180b50400e401dd0b296043f18fc6cb3f`, raw/dedup/split 7,040/6,853/6,204·649 실험
- [x] CarrotAI 50/500/1,000/2,000-step NLL·PPL 기록
- [x] qwen36mtp teacher 100건(100건 accepted, train/heldout 90/10, repetition 0.121885, 30,547 tokens)과 distill 100-step 결과 기록
- [x] 실행 성공·safety 통과와 repetition 0.96875/EOS 실패/newline 붕괴 기록
- [x] 87,804,672 unique parameters, 100,000 steps, 6,547,200,000 tokens의 GB10 CUDA bf16 baseline 학습 완료
- [x] `train audit`: 완료/latest step 100,000, best step 82,000, SHA-256·strict fingerprint·schema·필수 상태·NaN/Inf 통과
- [x] CUDA 1-batch baseline: validation PPL 17.4997869, test PPL 3.2870502, cloze 0.5
- [x] 고정 생성: repetition 0.21875, UTF-8 통과, EOS 미도달
- [x] SFT `auto`/`bf16`/`fp16`/`fp32` 정밀도와 gradient accumulation
- [x] 주기적 heldout validation과 validation loss 기준 `best.pt`/`latest.pt`
- [x] schema 2 모델·optimizer·scheduler·scaler·train/validation sampler·RNG·best 상태 완전 재개
- [x] validation sampler/optimizer/RNG/model finite 무결성 검사와 optimizer 경계 저장
- [x] 동일한 고정 heldout subset/order validation과 공정한 `best.pt` 비교
- [x] `max_steps` 연장 시 원 scheduler horizon 보존과 이후 `min_learning_rate` 유지
- [x] schema 1/2 `base_checkpoint` 가중치, immutable SHA-256와 원 학습 fingerprint provenance 결속
- [x] SFT 평가·생성 전 schema 2 전체 상태 strict 무결성 검사
- [x] 최종 전체 97 tests, Ruff, format, Pyright 검증
- [x] 동일한 split별 128 batch 평가: best val/test PPL 13.288556/14.080648, repetition 0.549716, EOS 2/6
- [x] 동일한 split별 128 batch 평가: latest val/test PPL 13.178043/13.952660, repetition 0.529836, EOS 3/6
- [x] 모든 측정 축이 우세한 100k `latest`를 SFT 시작점으로 선택하되 대화 품질 gate와 분리
- [x] full latest validation 4,223,967 token, loss 2.553663, PPL 12.854105와 test 3,976,401 token, loss 2.549981, PPL 12.806864
- [x] schema 2 `distill preflight/prepare/collect/resume/status/export/validate`
- [x] qwen36mtp 10k v3 inventory: raw/unique/duplicate 6,853/5,813/1,040, upstream heldout 630, Wikipedia 4,187
- [x] 10k train/heldout 8,445/1,555, prompt·upstream source overlap 0, inventory SHA-256·fingerprint 고정
- [x] 원자 spool, bounded concurrency/RPS/retry/body, progress/ETA, 중단 재개와 stale lock
- [x] current spool export 결속, provenance, 내부 전용 라이선스와 release blocked
- [x] redirect·환경 proxy·secret echo 차단과 strict teacher 응답 검증
- [x] 독립 리뷰 최초 9개와 추가 5개 지적 수정 후 승인
- [x] 최종 전체 123 tests, Ruff, format, Pyright, diff 검사
- [x] v3 초반 5건 accepted/rejected 1/4 확인 후 안전 중단과 산출물 보존
- [x] v4/v4b prompt 및 copy 오탐 교정, 정상 요약 허용과 20/50/79% 발췌·한 단어 변경 차단
- [x] 500자 응답 hard gate
- [x] v5 30건 prepare/preflight/collect/export/validate 실제 통과
- [x] v5 pilot accepted 28/30(93.3%), rejected length/finish reason 각 1건, failed/incomplete/duplicate 0
- [x] v5 pilot 122.0626초, 0.245775 RPS, 요청당 4.069초, 응답 길이 67/226.0/357자
- [x] v5 pilot export train/heldout 25/3, overlap 0, release blocked
- [x] 정식 v5 10k inventory·config fingerprint 고정과 preflight 통과
- [x] 공개 train/heldout canonical prompt overlap 152개 실측
- [x] 공개 train·teacher heldout overlap 658개와 영향 공개 train 879행 실측, 단순 concat 금지
- [x] `sft prepare-mix/preflight-mix/status-mix/validate-mix`와 `sft-mix` 설정 schema
- [x] teacher/source manifest SHA 고정, heldout prompt·원천 우선 격리와 결정적 중복 제거
- [x] tokenizer prompt+generation reserve·전체 chat 길이 gate와 runtime 전 데이터 truncation 실패-폐쇄
- [x] mix 배타 lock·staging·fsync·원자 publish, 부분 출력·변조 거부
- [x] 내부 teacher release blocked를 SFT checkpoint·평가에 계승하고 legacy resume 유지
- [x] 독립 리뷰 HIGH 3건+MEDIUM 및 추가 HIGH 수정 후 승인, 전체 133 tests·Ruff·Pyright 통과
- [x] 독립 재검토 승인과 최종 전체 129 tests, Ruff lint/format, Pyright, 참조 코드 checksum·diff 검사

### 후속 전체 평가 대기

- [ ] canary provenance와 corpus 경로를 설정한 canary exposure·contamination·long train match
- [ ] 전체 validation/test 및 생성·암기·오염·수동 평가
- [ ] conversation 검증

### 다음 계획

1. [x] SFT engine 강화
2. [ ] 정식 v5 run에서 teacher 10k collect/resume 완료 여부를 `distill status`로 확인
3. [ ] current spool export/validate 뒤 teacher manifest SHA-256 고정
4. [ ] 실제 export 경로를 사용하는 mix config와 pilot/full SFT config 작성
5. [ ] preflight-mix → prepare-mix → validate-mix와 별도 pilot 실행
6. [ ] pilot gate 통과 뒤 fresh full SFT와 best/latest 비교
7. [ ] 대화/EOS/repetition/safety/manual gate
8. [ ] semantic paraphrase contamination·수동 감사와 step-0 loss 평가 설계
9. [ ] GGUF 변환과 llama.cpp parity

## G003 한국어 대화 학습 경로 (1.5.0)

- [x] JSONL provenance/license/행·파일 hash 검증
- [x] assistant-only SFT masking, base checkpoint 재사용과 원자 재개
- [x] SFT CLI, heldout safety/repetition/EOS 평가, chat 생성, 합성 CPU 테스트
- [x] 전체 Wikipedia 100k baseline 학습 완료
- [ ] 전체 baseline 평가, 독립 안전·법무·공개 승인(별도 gate)

## 1.4.0 차단 해제

- [x] external stage별 암호학적 nonce/challenge 실행 직전 생성과 환경 계약 전달
- [x] nonce/run-id/stage/예산/commit/config fingerprint 서명 subject 결속
- [x] stage 시작 이후 발급 및 현재 만료 유효성 검증
- [x] 서로 다른 유효 과거 telemetry replay 회귀 차단
- [x] 후속 stage 종료 뒤 최종 권위 telemetry 전체 재검증과 TOCTOU 회귀 차단
- [ ] 실제 보호 environment에서 1.4.0 공개 승인 artifact 발급(외부 대기)

## 1.3.0 architect 차단 해제

- [x] external stage 실행 후 새 final telemetry의 freshness·서명·대상·예산 사후 gate
- [x] pinned root가 서명한 policy와 issuer Ed25519 공개키의 2단계 검증
- [x] verifier 비밀 환경변수 제거와 명시적 테스트 root 인자 경계
- [x] 결합 tokenization offset 기반 cloze/canary BPE 경계 점수화
- [ ] 실제 보호 environment에서 1.3.0 공개 승인 artifact 발급(외부 대기)


> 다음 세션은 위에서 아래로 진행한다. `[ ]`를 구현 전에 `[~]`, 검증 후 `[x]`로 바꾼다. 각 milestone 종료 시 명령과 artifact 경로를 아래 실행 기록에 남긴다.

## 1.2.0 외부 신뢰 경계

- [x] release subject repository/canonical commit 결속과 gate별 exact role 검증
- [x] Git 봉인 보호 CI policy와 일반 env self-signing 권위 분리
- [x] pipeline evidence 서명·role/kind·시각·commit/config/artifact 검증
- [x] 외부 stage 최종 token/energy telemetry 부재·변조 실패-폐쇄
- [x] canary/atomic/contamination 문서 계약 동기화
- [ ] 실제 보호 environment 공개 승인 artifact 발급(1.3.0으로 이월)

## 1.1.1 정리

- [x] `acf2841..45bd4ff` 변경 코드·테스트의 52개 regression 동작 잠금
- [x] fallback inventory/classification 및 masking fallback 부재 확인
- [x] dead code, duplication, naming/error handling, tests 순서의 smell별 검토
- [x] 미사용 helper 삭제와 원자적 Markdown 쓰기 중복 제거
- [x] 전체 pytest/Ruff/format/Pyright/release audit 검증

## M0 저장소와 개발 환경

- [x] Git 저장소 초기화 및 `AGENTS.md` 작성
- [x] `0.ref/README.md`를 읽고 `SHA256SUMS` 무결성 검사
- [x] 구현 코드에서 `0.ref` import를 금지하는 경계 확인
- [x] DGX Spark의 DGX OS, ARM64, driver, CUDA, NVMe 용량 기록
- [x] `nvidia-smi`의 iGPU memory 표시 한계 확인
- [x] NVIDIA Container Runtime GPU smoke test
- [x] ARM64 호환 NGC PyTorch image 선택 및 digest 고정
- [x] Dockerfile과 `docker-compose.yml` 작성
- [x] source/data/artifacts/runs host bind mount 구성
- [x] container PyTorch CUDA bf16 matmul smoke test
- [x] `docs/environment.md`에 재현 환경 기록
- [x] `uv init --package`에 준하는 Python 3.11+ 패키지 생성
- [x] runtime/dev 의존성 그룹과 lockfile 생성
- [x] `.gitignore`, `.env.example`, `README.md`, `Makefile` 작성
- [x] `src/llmex` layout과 Typer root CLI 생성
- [x] YAML 로더와 Pydantic config 모델 작성
- [x] 공통 path/run/fingerprint 유틸리티 작성
- [x] 구조화 로그와 오류 코드 규칙 작성
- [x] `configs/data/sample.yaml`, `configs/model/smoke.yaml` 작성
- [x] 외부 네트워크 없는 XML fixture 추가
- [x] Ruff, Pyright, Pytest 설정
- [x] GitHub Actions 또는 로컬 CI 스크립트 작성
- [x] `uv run llmex --help`, lint, typecheck, test 통과

## M1 Wikipedia 데이터

- [x] 날짜 고정 dump config와 URL validation
- [x] Wikimedia status/checksum metadata 수집기
- [x] disk-space 검사, timeout, retry, resume downloader
- [x] 다운로드 후 checksum 검증과 raw manifest
- [x] 표준 라이브러리 bzip2/XML streaming extractor(ADR-010에서 `mwxml` 대안 비교)
- [x] namespace 0, redirect 필터
- [x] page/revision/source/dump/license metadata 보존
- [x] MediaWiki markup parser 후보 비교 및 ADR 작성
- [x] Unicode NFC, 제어문자, 공백 정규화
- [x] 표·수식·목록·참조 처리 정책과 golden tests
- [x] 최소 길이, 한글 비율, 반복, markup 잔존 필터
- [x] exact SHA-256 dedup
- [x] 선택적 결정적 MinHash near-dedup 설계/구현
- [x] document hash 기반 train/validation/test split
- [x] schema v1 JSONL.ZST writer/reader
- [x] 필터 사유별 통계와 `docs/data-report.md`
- [x] fixture E2E hash 재현 테스트
- [x] 실제 입력용 `--max-documents 1000` canary와 100건 감사 JSON/Markdown 생성 기능
- [x] 실제 날짜 고정 dump 1,000문서 canary 실행(1,000 입력/997 통과)
- [ ] 100건 사람 검토

## M2 토크나이저와 token shards

- [x] train split 전용 streaming iterator
- [x] byte-level BPE trainer
- [x] special token와 ID 고정
- [x] vocab 16k/32k smoke config
- [x] tokenizer artifact/manifest/checksum
- [x] Unicode property-based round-trip test와 고정 10,000표본
- [x] 한국어 chars/token, bytes/token, tokens/word 평가
- [x] raw byte baseline 비교 보고서
- [x] 문서 끝 EOS 삽입 packer와 source 경계 manifest
- [x] `uint16`/`uint32` 범위 validation
- [x] memmap shard writer와 atomic manifest
- [x] shard checksum, token count, 최소/최대 ID 검증
- [x] split 간 source 문서 누출 검사와 동일 tokenizer 검증

## M3 decoder-only 모델

- [x] `ModelConfig` 불변조건 validation
- [x] RMSNorm 구현과 reference test
- [x] RoPE 구현, cache, position offset test
- [x] GQA/MHA attention 구현
- [x] causal leakage test
- [x] SDPA와 eager reference 결과 비교
- [x] SwiGLU 구현
- [x] Pre-Norm decoder block
- [x] token embedding/LM head weight tying
- [x] shifted causal loss
- [x] parameter count와 VRAM estimate
- [x] forward/backward shape/property tests
- [x] state_dict round-trip test
- [x] 128문서 overfit test

## M4 학습 시스템

- [x] deterministic memmap dataset/sampler
- [x] document boundary와 context sampling 정책
- [x] AdamW decay/no-decay parameter groups
- [x] warmup + cosine scheduler
- [x] gradient accumulation과 clipping
- [x] bf16/fp16/fp32 device capability 선택
- [x] JSONL metric logger
- [x] 고정 prompt sample logger
- [x] validation loop
- [x] 원자적 checkpoint writer
- [x] model/optimizer/scheduler/scaler/RNG/data cursor 저장
- [x] strict fingerprint checkpoint resume
- [x] SIGTERM graceful checkpoint
- [x] NaN/Inf fail-fast diagnostic
- [x] CPU smoke 50 step
- [x] 중단·재개 동일성 integration test

## M5 평가와 추론

- [x] NLL/perplexity evaluator
- [x] Korean Wikipedia cloze schema와 provenance
- [x] generation prompt suite 동결
- [x] temperature/top-k/top-p generation CLI
- [x] repetition, distinct-n, Unicode validity
- [x] exact contamination 검사
- [x] 정규화 문자 5-gram Jaccard contamination 검사(MinHash 아님)
- [x] canary exposure test
- [x] 긴 문자열 train match/암기 검사
- [x] 평가 JSON 및 Markdown renderer
- [x] KV cache 설계 ADR(v1.1)
- [x] validation/test checkpoint loss, token NLL/perplexity
- [x] byte 정규화 NLL, bits/byte, byte perplexity
- [x] 고정 prompt suite와 greedy/top-k/top-p/temperature/seed
- [x] sign-aware repetition penalty, distinct-n, Unicode 유효성
- [x] cache/no-cache logits 수치 동등성과 greedy 생성 완전 동등성
- [x] 배치별 EOS, max-new-token, 문맥 제한 종료
- [x] checkpoint/model/tokenizer/shard 엄격 호환성 및 checksum 검증
- [x] 평가·생성·benchmark JSON/Markdown/fingerprint/checksum artifact
- [x] 한국어 eval/generate/benchmark CLI, 오류 코드와 dry-run
- [x] CPU CLI E2E와 GB10 CUDA smoke/latency-memory benchmark

## M6 전체 데이터와 baseline

- [x] DGX Spark unified memory/시간/전력 예산 기록 및 87.8M model profile 확정
- [x] 87.8M 100-step tokens/s와 peak memory 기능 microbenchmark(context 256)
- [ ] context, gradient checkpointing, dataloader workers 비교
- [x] system available memory, RSS, swap 수집 및 PyTorch peak 외부 gate 정의
- [x] 장기 run의 systemd/container restart와 원자적 checkpoint 방식 확정
- [x] 100M baseline 완료 전 120M 초과 설정 거부 확인
- [x] 날짜 고정 전체 dump URL/checksum 승인(공식 SHA-1 일치·로컬 SHA-256)
- [x] raw 저장공간과 예상 artifact 용량 preflight
- [x] 전체 extract/clean/dedup/split report 승인
- [x] tokenizer 16k 실제 측정 및 선택
- [x] baseline parameter/token budget 확정
- [x] 1% token pilot
- [x] throughput, memory, loss, checkpoint 복구 검토
- [~] baseline 학습 실행
- [ ] best/final checkpoint 평가
- [ ] 실패·중단 포함 training report 작성

### M6 로컬 계약·외부 검증표

| 요구사항 | 로컬 자동화 | 실제 증거 | 판정 |
|---|---|---|---|
| 전체 pipeline orchestration/재개 | `pipeline run/status` | fixture E2E | 통과 |
| 자원·120M 상한 | `pipeline preflight` | DGX Spark 실측 | 통과 |
| 실제 dump 1,000문서 | `data sample-e2e` 단계 | dump/checksum/canary | 외부 대기 |
| 사람 감사 100건 | 필수 evidence gate | 감사자 승인 JSON | 외부 대기 |
| tokenizer 16k/32k | 비교 evidence gate | 동일 corpus 비교 JSON | 외부 대기 |
| 100-step/1% pilot/장기 학습 | timeout·예산·재개 gate | DGX metric/checkpoint | 외부 대기 |
| provenance/license | schema 검증·필수 gate | 승인 artifact | 외부 대기 |
| contamination/암기 | M5 evaluator | best/final 평가 artifact | 외부 대기 |
| 실패 복구 | `pipeline drill`, M4 SIGTERM | 로컬 drill | 통과 |
| report/dashboard | `pipeline export` | JSON/Markdown | 통과 |

## M7 공개 준비

- [x] data/model/tokenizer card와 한국어 사용자 문서 완성
- [x] `NOTICE.md`의 Wikipedia 귀속·참조·가중치 법적 경계
- [x] page/revision/source/dump/license 추적 계약과 자동 테스트
- [x] 보안·개인정보·위협 모델·failure mode·운영 runbook
- [x] artifact SHA-256 manifest, CycloneDX SBOM, SLSA provenance 생성기
- [x] sdist/wheel build와 새 venv install/smoke 검증 계약
- [x] CI release audit/bundle/build/install/reference-boundary 확대
- [x] API/CLI, reproducibility, migration, changelog와 examples
- [x] clean-room `0.ref` import·배포 경계 자동 감사
- [x] ADR-017 공개/비공개 결정과 최종 acceptance matrix
- [ ] 외부 법무 검토 승인(자동 gate, 명시 승인 없이는 실패)
- [ ] 전체 장기 baseline·독립 데이터/안전 리뷰(자동 gate, 장기 증거 없이는 실패)
- [ ] 공개 배포 책임자 결정(자동 gate, 명시 승인 없이는 실패)

### M7 및 전체 검증표

| 요구사항 | 명령/증거 | 현재 판정 |
|---|---|---|
| frozen 환경 | `uv sync --frozen` | 통과 |
| format/lint/type/test | Ruff, Pyright strict, `49 passed` | 통과 |
| source/wheel | `uv build`, 새 venv install/version/help | 통과 |
| CLI/pipeline | 전체 help와 M6/M7 fixture E2E | 통과 |
| 공급망 | release bundle checksum/SBOM/provenance | 통과 |
| 보안·비밀·license | `release audit`, NOTICE/LICENSE | 통과 |
| 참조 경계 | source import, sdist/wheel member 검사 | 통과 |
| 법무 | 외부 승인 JSON | 대기·공개 금지 |
| 장기 baseline | M6 전체 evidence | 대기·공개 금지 |
| 공개 결정 | 책임자 승인 JSON | 대기·공개 금지 |

### 1.0.1 최종 cleanup 검증표

| 점검 항목 | 근거 | 판정 |
|---|---|---|
| 동작 잠금 | 수정 전 `49 passed` | 통과 |
| fallback-like 분류 | masking 1건 삭제, grounded fail-safe 4종 보존 | 통과 |
| dead code | downloader 도달 불가능 분기 삭제 | 통과 |
| duplication | 고신뢰 중복 후보 없음 | 변경 없음 |
| naming/error handling | 공개 계약을 유지할 최소 후보 없음 | 변경 없음 |
| 불필요 abstraction | 제거 가능한 단일 전달 계층 없음 | 변경 없음 |
| 회귀 보강 | 재시도 소진과 원인 보존 테스트 추가 | 통과 |
| 버전·lock | 1.0.1 및 `uv.lock` 동기화 | 통과 |
| 전체 품질 | Ruff, Pyright strict, `50 passed` | 통과 |
| 릴리스 | audit, sdist/wheel, 120개 파일 bundle | 통과 |
| diff 위생 | `git diff --check` | 통과 |

## 실행 기록

| 날짜 | milestone | commit/run | 검증 명령 | 결과/artifact | 다음 작업 |
|---|---|---|---|---|---|
| 2026-07-11 | M0 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff lint/format; Pyright; Pytest; CLI help; ref checksum; `docker compose config`; `git diff --check`; DGX Spark CUDA smoke | `14 passed`; GB10/CUDA 13.0/bf16 `finite=true`; NGC 25.10 digest 고정 | M1 Wikipedia 데이터 |
| 2026-07-11 | M1 fixture smoke | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright; Pytest; `llmex data sample-e2e --max-documents 1000`; `git diff --check` | 외부 네트워크 없는 확장 fixture, local HTTP resume, checksum/filter/attribution/split/E2E hash 검증; 실제 dump canary 미실행 | 실제 dump canary 후 M2 토크나이저 |
| 2026-07-11 | M2 fixture tokenizer | 미커밋 작업 트리 | `uv sync`; Ruff format/check; Pyright; Pytest; fixture `tokenizer train/evaluate/pack` 2회; manifest 비교; `git diff --check` | 16k byte-level BPE, Unicode 10,000표본/속성, train-only, EOS/memmap/checksum 재현성 검증 | 실제 corpus 16k/32k 비교 후 M3 |
| 2026-07-11 | M3 decoder-only 모델 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; `llmex model inspect`; GB10 CUDA forward/backward; ref checksum; `git diff --check` | `36 passed`; strict 오류 0건; 2,835,584 parameters; CUDA finite loss; RMSNorm/RoPE/GQA/SDPA/SwiGLU/tied LM/loss/generation/KV cache와 128문서 overfit 검증 | M4 학습 시스템 |
| 2026-07-11 | M4 학습 엔진 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; train CLI E2E; CPU 50-step; CUDA bf16 smoke; `git diff --check` | `42 passed`; strict 오류 0건; CPU 50-step/bitwise resume/오류주입 및 GB10 CUDA bf16 2-step 통과 | M5 평가·추론 |
| 2026-07-11 | M5 평가·추론 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; eval/generate/benchmark CLI E2E; cache parity; 가능한 CUDA benchmark; `git diff --check` | checkpoint 호환성, token/byte 지표, sampling/EOS/context, contamination/암기, JSON/Markdown/checksum artifact 검증 | M6 전체 데이터·baseline |
| 2026-07-11 | M6 로컬 계약 | 미커밋 작업 트리 | `pipeline preflight/run/status/drill/export`; model inspect; Wikimedia network 시도; 전체 품질 게이트 | 87,804,672 parameters, preflight 통과, 외부 증거 없는 단계는 엄격히 대기; 전체 dump/사람 감사/장기 학습 미완료 | 증거 생성 뒤 `--allow-external` 재개 |
| 2026-07-11 | M7/1.0.0 로컬 릴리스 | 미커밋 작업 트리 | frozen sync; Ruff; Pyright; pytest; build/install E2E; CLI/pipeline; release audit/bundle; ref checksum; diff check | 로컬 acceptance 완료 목표, 세 외부 gate는 실패 상태 유지 | 법무·장기 baseline·공개 결정 독립 승인 |

## 즉시 중단 조건

- dump checksum 불일치
- attribution metadata 손실
- train/validation/test 문서 누출
- tokenizer round-trip 실패 또는 ID overflow
- causal leakage test 실패
- 반복 NaN/Inf 또는 checkpoint 복구 실패
- 예상 비용/시간이 승인값의 120% 초과
- 라이선스·개인정보 문제가 해결되지 않은 상태의 공개 시도

## 1.1.0 최종 리뷰 차단 해소

- [x] 신뢰 저장소 서명 외부 승인과 대상/evidence 결속
- [x] 구조화 pipeline evidence 및 빈 JSON 실패-폐쇄
- [x] 안전 checkpoint 로드와 악성 pickle 비실행 회귀
- [x] 실제 cloze/canary 계측과 유계 contamination
- [x] runtime 예산 강제, stage 재개 무결성, session delta 처리량
- [x] wheel/sdist 기반 SBOM/provenance와 recovery drill
- [x] 원자적 artifact/sidecar 및 ADR hash 계약 정합화
- [ ] 외부 법무·장기 baseline·공개 책임자 승인(실제 보호 CI 서명 필요)
