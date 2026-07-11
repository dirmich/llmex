# LLMEX 개발 TODO

> 다음 세션은 위에서 아래로 진행한다. `[ ]`를 구현 전에 `[~]`, 검증 후 `[x]`로 바꾼다. 각 milestone 종료 시 명령과 artifact 경로를 아래 실행 기록에 남긴다.

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
- [ ] 실제 날짜 고정 dump 1,000문서 canary 실행 및 100건 사람 검토

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
- [x] MinHash contamination 검사
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

- [ ] DGX Spark unified memory/시간/전력 예산 기록 및 model profile 확정
- [ ] 100M 100-step tokens/s와 peak memory microbenchmark
- [ ] context, gradient checkpointing, dataloader workers 비교
- [ ] system available memory, RSS, swap, PyTorch peak metric 수집
- [ ] 장기 run의 tmux/systemd/container restart 방식 확정
- [ ] 100M baseline 완료 전 300M 이상 실행 금지 확인
- [ ] 날짜 고정 전체 dump URL/checksum 승인
- [ ] raw 저장공간과 예상 artifact 용량 확인
- [ ] 전체 extract/clean/dedup/split report 승인
- [ ] tokenizer 16k/32k 비교 후 선택
- [ ] baseline parameter/token budget 확정
- [ ] 1% token pilot
- [ ] throughput, memory, loss, checkpoint 복구 검토
- [ ] baseline 학습 실행
- [ ] best/final checkpoint 평가
- [ ] 실패·중단 포함 training report 작성

## M7 공개 준비

- [ ] `docs/data-card.md` 완성
- [ ] `docs/model-card.md` 완성
- [ ] Wikipedia attribution 파일 생성
- [ ] page/revision/source 추적 검증
- [ ] 라이선스와 가중치 배포 조건 검토
- [ ] 개인정보·명예훼손·암기 위험 검토
- [ ] artifact checksum manifest
- [ ] clean-room 재현 테스트
- [ ] 독립 코드 리뷰
- [ ] 독립 데이터·안전 리뷰
- [ ] 공개/비공개 결정 ADR

## 실행 기록

| 날짜 | milestone | commit/run | 검증 명령 | 결과/artifact | 다음 작업 |
|---|---|---|---|---|---|
| 2026-07-11 | M0 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff lint/format; Pyright; Pytest; CLI help; ref checksum; `docker compose config`; `git diff --check`; DGX Spark CUDA smoke | `14 passed`; GB10/CUDA 13.0/bf16 `finite=true`; NGC 25.10 digest 고정 | M1 Wikipedia 데이터 |
| 2026-07-11 | M1 fixture smoke | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright; Pytest; `llmex data sample-e2e --max-documents 1000`; `git diff --check` | 외부 네트워크 없는 확장 fixture, local HTTP resume, checksum/filter/attribution/split/E2E hash 검증; 실제 dump canary 미실행 | 실제 dump canary 후 M2 토크나이저 |
| 2026-07-11 | M2 fixture tokenizer | 미커밋 작업 트리 | `uv sync`; Ruff format/check; Pyright; Pytest; fixture `tokenizer train/evaluate/pack` 2회; manifest 비교; `git diff --check` | 16k byte-level BPE, Unicode 10,000표본/속성, train-only, EOS/memmap/checksum 재현성 검증 | 실제 corpus 16k/32k 비교 후 M3 |
| 2026-07-11 | M3 decoder-only 모델 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; `llmex model inspect`; GB10 CUDA forward/backward; ref checksum; `git diff --check` | `36 passed`; strict 오류 0건; 2,835,584 parameters; CUDA finite loss; RMSNorm/RoPE/GQA/SDPA/SwiGLU/tied LM/loss/generation/KV cache와 128문서 overfit 검증 | M4 학습 시스템 |
| 2026-07-11 | M4 학습 엔진 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; train CLI E2E; CPU 50-step; CUDA bf16 smoke; `git diff --check` | `42 passed`; strict 오류 0건; CPU 50-step/bitwise resume/오류주입 및 GB10 CUDA bf16 2-step 통과 | M5 평가·추론 |
| 2026-07-11 | M5 평가·추론 | 미커밋 작업 트리 | `uv sync --frozen`; Ruff format/check; Pyright strict; 전체 Pytest; eval/generate/benchmark CLI E2E; cache parity; 가능한 CUDA benchmark; `git diff --check` | checkpoint 호환성, token/byte 지표, sampling/EOS/context, contamination/암기, JSON/Markdown/checksum artifact 검증 | M6 전체 데이터·baseline |

## 즉시 중단 조건

- dump checksum 불일치
- attribution metadata 손실
- train/validation/test 문서 누출
- tokenizer round-trip 실패 또는 ID overflow
- causal leakage test 실패
- 반복 NaN/Inf 또는 checkpoint 복구 실패
- 예상 비용/시간이 승인값의 120% 초과
- 라이선스·개인정보 문제가 해결되지 않은 상태의 공개 시도
