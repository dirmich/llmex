# LLMEX 개발 TODO

> 다음 세션은 위에서 아래로 진행한다. `[ ]`를 구현 전에 `[~]`, 검증 후 `[x]`로 바꾼다. 각 milestone 종료 시 명령과 artifact 경로를 아래 실행 기록에 남긴다.

## M0 저장소와 개발 환경

- [ ] Git 저장소 초기화 및 `AGENTS.md` 작성
- [ ] `0.ref/README.md`를 읽고 `SHA256SUMS` 무결성 검사
- [ ] 구현 코드에서 `0.ref` import를 금지하는 경계 확인
- [ ] DGX Spark의 DGX OS, ARM64, driver, CUDA, NVMe 용량 기록
- [ ] `nvidia-smi`의 iGPU memory 표시 한계 확인
- [ ] NVIDIA Container Runtime GPU smoke test
- [ ] ARM64 호환 NGC PyTorch image 선택 및 digest 고정
- [ ] Dockerfile과 `docker-compose.yml` 작성
- [ ] source/data/artifacts/runs host bind mount 구성
- [ ] container PyTorch CUDA bf16 matmul smoke test
- [ ] `docs/environment.md`에 재현 환경 기록
- [ ] `uv init --package`로 Python 3.11+ 패키지 생성
- [ ] runtime/dev 의존성 그룹과 lockfile 생성
- [ ] `.gitignore`, `.env.example`, `README.md`, `Makefile` 작성
- [ ] `src/llmex` layout과 Typer root CLI 생성
- [ ] YAML 로더와 Pydantic config 모델 작성
- [ ] 공통 path/run/fingerprint 유틸리티 작성
- [ ] 구조화 로그와 오류 코드 규칙 작성
- [ ] `configs/data/sample.yaml`, `configs/model/smoke.yaml` 작성
- [ ] 외부 네트워크 없는 XML fixture 추가
- [ ] Ruff, Pyright, Pytest 설정
- [ ] GitHub Actions 또는 로컬 CI 스크립트 작성
- [ ] `uv run llmex --help`, lint, typecheck, test 통과

## M1 Wikipedia 데이터

- [ ] 날짜 고정 dump config와 URL validation
- [ ] Wikimedia status/checksum metadata 수집기
- [ ] disk-space 검사, timeout, retry, resume downloader
- [ ] 다운로드 후 checksum 검증과 raw manifest
- [ ] `mwxml` streaming extractor
- [ ] namespace 0, redirect 필터
- [ ] page/revision/source/license metadata 보존
- [ ] MediaWiki markup parser 후보 비교 및 ADR 작성
- [ ] Unicode NFC, 제어문자, 공백 정규화
- [ ] 표·수식·목록·참조 처리 정책과 golden tests
- [ ] 최소 길이, 한글 비율, 반복, markup 잔존 필터
- [ ] exact SHA-256 dedup
- [ ] 선택적 MinHash near-dedup 설계
- [ ] document hash 기반 train/val/test split
- [ ] JSONL.ZST writer와 schema version
- [ ] 필터 사유별 통계와 `data-report.md`
- [ ] fixture E2E hash 재현 테스트
- [ ] 1,000문서 canary run 및 수동 샘플 100건 검토

## M2 토크나이저와 token shards

- [ ] train split 전용 streaming iterator
- [ ] byte-level BPE trainer
- [ ] special token와 ID 고정
- [ ] vocab 16k smoke config
- [ ] tokenizer artifact/manifest/checksum
- [ ] Unicode property-based round-trip test
- [ ] 한국어 chars/token, bytes/token, tokens/word 평가
- [ ] baseline tokenizer 비교 보고서
- [ ] 문서 끝 EOS 삽입 packer
- [ ] `uint16`/`uint32` 범위 validation
- [ ] memmap shard writer와 atomic manifest
- [ ] shard checksum과 token count 검증
- [ ] split 간 문서·token source 누출 검사

## M3 decoder-only 모델

- [ ] `ModelConfig` 불변조건 validation
- [ ] RMSNorm 구현과 reference test
- [ ] RoPE 구현, cache, position offset test
- [ ] GQA/MHA attention 구현
- [ ] causal leakage test
- [ ] SDPA와 eager reference 결과 비교
- [ ] SwiGLU 구현
- [ ] Pre-Norm decoder block
- [ ] token embedding/LM head weight tying
- [ ] shifted causal loss
- [ ] parameter count와 VRAM estimate
- [ ] forward/backward shape/property tests
- [ ] state_dict round-trip test
- [ ] 128문서 overfit test

## M4 학습 시스템

- [ ] deterministic memmap dataset/sampler
- [ ] document boundary와 context sampling 정책
- [ ] AdamW decay/no-decay parameter groups
- [ ] warmup + cosine scheduler
- [ ] gradient accumulation과 clipping
- [ ] bf16/fp16/fp32 device capability 선택
- [ ] JSONL metric logger
- [ ] 고정 prompt sample logger
- [ ] validation loop
- [ ] 원자적 checkpoint writer
- [ ] model/optimizer/scheduler/scaler/RNG/data cursor 저장
- [ ] strict fingerprint checkpoint resume
- [ ] SIGTERM graceful checkpoint
- [ ] NaN/Inf fail-fast diagnostic
- [ ] CPU smoke 50 step
- [ ] 중단·재개 동일성 integration test

## M5 평가와 추론

- [ ] NLL/perplexity evaluator
- [ ] Korean Wikipedia cloze schema와 provenance
- [ ] generation prompt suite 동결
- [ ] temperature/top-k/top-p generation CLI
- [ ] repetition, distinct-n, Unicode validity
- [ ] exact contamination 검사
- [ ] MinHash contamination 검사
- [ ] canary exposure test
- [ ] 긴 문자열 train match/암기 검사
- [ ] 평가 JSON 및 Markdown renderer
- [ ] KV cache 설계 ADR(v1.1)

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
| - | - | - | - | - | M0 첫 항목 |

## 즉시 중단 조건

- dump checksum 불일치
- attribution metadata 손실
- train/validation/test 문서 누출
- tokenizer round-trip 실패 또는 ID overflow
- causal leakage test 실패
- 반복 NaN/Inf 또는 checkpoint 복구 실패
- 예상 비용/시간이 승인값의 120% 초과
- 라이선스·개인정보 문제가 해결되지 않은 상태의 공개 시도
