# 구현 이력

## 2026-07-11 · 1.4.0 external telemetry freshness와 최종 권위 재검증

- external command 실행 직전에 예측 불가능한 nonce를 만들고 `LLMEX_STAGE_NONCE`를 포함한 환경 계약으로 run-id, stage, 예산, Git commit, 설정 fingerprint 및 출력 경로를 전달한다.
- command가 실행 중 실제 사후 telemetry를 발급하도록 정상 회귀를 바꾸고, 서명 subject의 모든 실행 식별자와 `issued_at >= stage_started_at`, 현재 만료 유효성을 검증한다.
- 서로 다른 유효 서명을 가진 과거 telemetry 재생과 후속 local stage의 권위 파일 TOCTOU 변조를 회귀 테스트로 차단했다.
- 최종 성공 직전 마지막 권위 telemetry의 digest, 서명, subject, 예산과 사용량 상한을 전부 다시 검증하며 실패 상태를 원자적으로 기록한다.

## 2026-07-11 · 1.3.0 사후 권위 gate와 공개키 신뢰 체인

- external stage의 사전 final telemetry는 승인 근거로 사용하지 않으며, 실행 직전 digest와 다른 사후 final telemetry가 없으면 단계와 전체 상태를 실패로 고정한다.
- 사후 telemetry를 issuer 서명, repository commit, config fingerprint, stage, deterministic run-id, token/energy 예산과 실제 최종 사용량에 결속했다.
- verifier의 HMAC secret 환경변수 입력을 제거하고 패키지 pinned root Ed25519 공개키가 서명한 HEAD policy와 issuer Ed25519 서명을 순서대로 검증한다.
- cloze/canary 후보를 prefix와 따로 tokenize하지 않고 결합 sequence offset으로 score span을 정해 경계 merge를 보존했다.


## 2026-07-11 · 1.2.0 외부 신뢰 경계 차단 해제

- 승인 파일 위치가 아니라 명시 subject repository root와 canonical HEAD commit에 release/pipeline 진술을 결속했다.
- HEAD에 봉인되고 group/other 쓰기가 금지된 `.llmex/trust-policy.json`의 key digest·role·kind만 권위 있는 보호 CI policy로 인정한다. 일반 프로세스 환경변수만으로 만든 self-signed 결과는 승인하지 않는다.
- 외부 evidence와 최종 resource telemetry의 서명, RFC3339 유효 기간, role/kind, commit/config/artifact 결속을 검증하고 누락·변조 시 대기한다.
- JSONL.ZST와 pipeline Markdown까지 file/directory fsync와 atomic replace 계약으로 통일했다.

## 2026-07-11 · 1.1.1 AI slop 정리

- `acf2841..45bd4ff`의 변경 코드·테스트만 대상으로 52개 targeted regression을 먼저 통과시켰다.
- fallback inventory를 작성하고 OS 자원 탐지, pipeline 재개·복구, checkpoint 로드 경계가 실패-안전형임을 확인했다.
- 미사용 artifact sidecar 검증 함수를 삭제하고 평가 Markdown의 원자적 쓰기를 공통 구현으로 통합했다.
- 압축된 preflight 지역 변수 대입을 명시적으로 풀고 버전·lock·릴리스 이력을 `1.1.1`로 동기화했다.

## 2026-07-11 · M0 저장소 기반

- Python 3.11+ `src` layout과 패키지 버전 `0.1.0`을 구성했다.
- Typer root CLI와 config 검증, fingerprint, run 생성 명령을 추가했다.
- Pydantic strict 모델로 알 수 없는 키, 암묵적 타입 변환, 잘못된 dump URL과 모델 형상을 거부한다.
- path/run/fingerprint, JSON 구조화 로그, 안정적인 종료 코드를 추가했다.
- 한국어 MediaWiki XML 오프라인 bzip2 fixture와 단위 테스트를 추가했다.
- Ruff, Pyright strict, Pytest, GitHub Actions 품질 게이트를 구성했다.
- Dockerfile, Compose bind mount, 오프라인 서비스와 CUDA bf16 smoke script를 추가했다.
- `0.ref`는 수정하지 않았고 production import 금지를 테스트로 고정했다.
- 실제 DGX Spark의 `aarch64` Ubuntu(kernel `6.17.0-1014-nvidia`), NVIDIA GB10, driver `580.142`, CUDA compatibility `13.0`, Docker `29.2.1`을 확인했다.
- NVMe `/`는 전체 `3.6T` 중 `1.9T` 사용 가능, RAM은 전체 `119Gi` 중 `28Gi` 사용 가능, swap은 전체 `15Gi` 중 `11Gi` 사용 상태로 기록했다.
- `nvidia-smi`의 framebuffer memory가 `Not Supported`임을 확인하고, NVIDIA Container Runtime의 실제 GPU 전달로 판정을 보완했다.
- `nvcr.io/nvidia/pytorch:25.10-py3` 로컬 이미지 digest를 `sha256:42263b2424fc237b34c4fc4a91c30d603c57eed36e37d31ff6d9a4f1f801edee`로 확인해 Dockerfile, `.env`, Compose 기본값에 고정했다.
- `docker run --rm --gpus all ... python scripts/cuda_smoke.py`에서 PyTorch `2.9.0a0+145a3a7`, CUDA `13.0`, NVIDIA GB10을 확인했고 bf16 결과가 `finite=true`로 통과했다.

### M0 마감 검증 기록

- `uv sync --frozen`: lockfile 변경 없이 동기화 통과
- `uv run ruff check .`: 통과
- `uv run ruff format --check .`: 통과
- `uv run pyright`: 통과
- `uv run pytest -q`: `14 passed`
- `uv run llmex --help`: 도움말 출력 통과
- `cd 0.ref && shasum -a 256 -c SHA256SUMS`: 참조 파일 checksum 통과
- `docker compose config`: digest 고정값과 Compose 구성 해석 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 · M1 Wikipedia 데이터 파이프라인

- 패키지와 프로젝트 버전을 `0.2.0`으로 올렸다.
- 날짜 고정 Wikimedia URL/status/SHA256SUMS metadata, 저장공간 검사, timeout/retry, HTTP Range resume, checksum 검증과 읽기 전용 raw manifest를 구현했다.
- bzip2 XML streaming 추출에서 namespace 0, redirect 제외, 마지막 revision과 page/revision/source/dump/license attribution을 보존했다.
- parser ADR에 후보 비교와 한계를 기록하고 표·참조 제거, 수식·목록 표시문 보존, NFC/control/공백 정제 및 정책 통계를 구현했다.
- 최소 길이·한글 비율·반복·markup 품질 필터, exact SHA-256과 선택적 결정적 MinHash near-dedup, document-hash split을 구현했다.
- schema v1 JSONL.ZST reader/writer, 단계별 CLI, data manifest/report, 최대 100건 자동 감사 JSON/Markdown을 구현했다.
- 외부 네트워크 없는 확장 fixture와 golden test, 손상 checksum, local HTTP resume, attribution, split disjoint, 결정적 E2E hash 검증을 추가했다.
- 실제 전체 dump와 실제 입력 1,000문서 canary는 실행하지 않았다. `--max-documents 1000` 실행 기능과 fixture 기반 smoke 통과만 검증했으며 실제 canary 완료로 기록하지 않는다.

## 2026-07-11 · M2 토크나이저와 token shards

- 패키지 버전을 `0.3.0`으로 올리고 Hugging Face `tokenizers`, NumPy를 runtime dependency로 추가했다.
- train split 전용 streaming iterator와 special ID 0–3, initial byte alphabet, byte fallback을 갖춘 결정적 byte-level BPE 학습을 구현했다.
- 16k/32k 설정, tokenizer JSON, vocab, merges, resolved config, corpus fingerprint와 artifact checksum manifest를 추가했다.
- 문자/토큰, 바이트/토큰, 단어당 토큰, raw byte baseline 비교와 split별 통계를 JSON/Markdown으로 출력한다.
- source 문서별 EOS와 전역 경계를 보존하고 실제 최대 ID에 따라 little-endian `uint16`/`uint32`를 선택하는 원자적 memmap shard writer를 구현했다.
- shard별 checksum, token 수, 최소/최대 ID 및 tokenizer/corpus fingerprint manifest와 fingerprint 충돌 보호를 추가했다.
- 한글 완성형·자모·NFD·emoji ZWJ·한자·ASCII·combining marks, Hypothesis 유효 Unicode와 고정 10,000표본, train-only fitting, 누출, EOS, next-token 정렬, 결정적 checksum 테스트를 추가했다.
- 외부 네트워크 없이 M1 형식 fixture corpus로 `tokenizer train/evaluate/pack` CLI E2E를 검증한다.

## 2026-07-11 · M3 decoder-only Transformer

- 패키지 버전을 `0.4.0`으로 올리고 PyTorch 2.x를 runtime dependency로 추가해 lockfile을 동기화했다.
- float32 내부 계산 RMSNorm, 인접 좌표 회전 RoPE와 position offset, GQA/MHA projection과 명시적 절대 위치 causal mask를 구현했다.
- PyTorch SDPA 기본 경로와 독립 eager reference 경로가 같은 projection·mask에서 수치 일치하도록 구성했다.
- bias 없는 SwiGLU, Pre-Norm residual decoder block, 최종 RMSNorm과 tied token embedding/LM head를 구현했다.
- 평균 0·표준편차 `init_std` 초기화와 residual output projection의 `1/sqrt(2L)` scale을 적용했다.
- `int64[B,T]` 입력, `float[B,T,V]` logits, shifted cross entropy, padding ignore index와 shape/길이 오류 계약을 구현했다.
- greedy/temperature/top-k generation과 layer별 RoPE 적용 KV cache를 라이브러리 API로 추가하고 cached/uncached parity를 고정했다.
- `llmex model inspect`가 resolved config, fingerprint, 정확한 파라미터 수, fp32 weight와 AdamW 근사 메모리, weight tying을 JSON artifact로 기록한다.
- RMSNorm/RoPE 수식, GQA Hypothesis property, SDPA/eager parity, causal leakage 0, loss shift, finite gradient, state dict, 생성 cache, 128문서 synthetic overfit과 CLI E2E 테스트를 추가했다.
- 교재 Ch 14–18, 27, 31과 benchmark는 읽기 전용 수식 참고로만 사용했으며 production import 없이 독립 구현했다.

### M3 마감 검증 기록

- `uv sync --frozen`: `0.4.0` lockfile 변경 없이 동기화 통과
- `uv run ruff format --check .`, `uv run ruff check .`: 통과
- `uv run pyright`: strict 기준 오류·경고 0건
- `uv run pytest -q`: `36 passed`
- `uv run llmex model inspect --config configs/model/smoke.yaml`: `2,835,584` parameters, tied weight와 JSON artifact 출력 통과
- NVIDIA GB10 CUDA forward/backward smoke: finite loss와 역전파 통과
- `cd 0.ref && shasum -a 256 -c SHA256SUMS`: 전체 참조 무결성 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 · M4 결정적 학습 엔진

- 패키지 버전을 `0.5.0`으로 올리고 strict `TrainingConfig`와 AdamW 설정을 추가했다.
- checksum 검증 memmap shard dataset, shard 경계 연속 context, epoch/cursor 복구형 결정적 sampler와 next-token batch를 구현했다.
- tied parameter 중복을 제거한 decay/no-decay AdamW group, update 단위 warmup+cosine, gradient accumulation과 global norm clipping을 구현했다.
- CUDA bf16 우선 자동 선택, CUDA fp16 GradScaler, bf16 scaler 비활성, CPU/MPS fp32 fallback 정책을 구현했다.
- train/validation/생성 표본 JSONL과 처리량·CUDA peak memory 지표, validation NLL/perplexity와 best 판정을 구현했다.
- 보존형 step, latest, best checkpoint를 flush·file/directory `fsync`·atomic rename으로 저장한다.
- model/optimizer/scheduler/scaler, train/validation sampler, Python·NumPy·PyTorch CPU/CUDA RNG와 best 상태를 완전 복구한다.
- config/corpus/tokenizer/model/shard fingerprint 충돌, shard/checkpoint 손상과 NaN/Inf를 즉시 거부하고 진단 artifact를 남긴다.
- SIGTERM은 현재 update 경계에서 graceful checkpoint 후 종료하며 `train run/resume/smoke` CLI를 제공한다.
- CPU 50-step loss 감소, accumulation 동등성, bitwise 중단·재개와 오류주입 테스트를 추가했다.

### M4 마감 검증 기록

- `uv sync --frozen`: 0.5.0 lockfile 변경 없이 동기화 통과
- `uv run ruff format --check .`, `uv run ruff check .`: 통과
- `uv run pyright`: strict 기준 오류·경고 0건
- `uv run pytest -q`: `42 passed`
- CLI E2E: 0.5.0/version, help, training config validate, `train smoke --dry-run`, 테스트 내부 실제 train/resume/smoke 통과
- CPU: 50 optimizer step loss 감소, 연속/중단·재개 state bitwise 동일, NaN·손상·fingerprint 오류주입 통과
- NVIDIA GB10 CUDA: bf16 autocast 실제 2-step train/validation, JSONL CUDA peak memory, latest/best checkpoint 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 · M5 평가와 추론

- 패키지와 프로젝트 버전을 `0.6.0`으로 올리고 lockfile을 동기화했다.
- checkpoint, 학습 설정, 모델, tokenizer, corpus와 shard fingerprint 및 tokenizer artifact checksum/special ID/vocab 형상을 묶은 엄격한 추론 runtime을 구현했다.
- validation/test의 합산 NLL, token loss/perplexity, UTF-8 byte 정규화 NLL·bits/byte·byte perplexity를 구현했다.
- provenance를 가진 고정 Korean Wikipedia 형식 cloze schema와 띄어쓰기·조사/어미·고유명사·숫자/날짜 고정 prompt suite를 추가했다.
- greedy, temperature, top-k, top-p, seed, sign-aware repetition penalty와 배치별 EOS, max-new-token, 모델 문맥 제한 처리를 구현했다.
- KV cache prefill/decode offset 계약을 유지하고 cache/no-cache 다음-token logits 수치 동등성과 greedy 생성 완전 동등성을 자동 검증했다.
- 생성 반복률, distinct-1/2, UTF-8 유효성, EOS/문맥 종료, exact substring 및 문자 5-gram near contamination, canary/긴 생성 train match 결과를 보고한다.
- JSON/Markdown 평가·생성·benchmark artifact와 SHA-256 checksum manifest, payload fingerprint를 원자적으로 생성한다.
- 한국어 도움말, 구조화 오류 코드와 side-effect 없는 dry-run을 갖춘 root `eval`, `generate`, `benchmark` CLI를 추가했다.
- CPU CLI E2E에서 실제 checkpoint를 생성해 세 명령과 artifact를 검증했다. CUDA가 보이는 환경에서는 synchronize 기반 latency/token-s 및 peak allocated memory를 기록한다.

### M5 마감 검증 기록

- `uv sync --frozen`: lockfile 변경 없이 동기화 통과
- `uv run ruff format --check .`; `uv run ruff check .`: 통과
- `uv run pyright`: strict 오류 0건
- `uv run pytest -q`: 전체 테스트 통과
- `uv run llmex eval|generate|benchmark --dry-run`: side effect 없이 통과
- CPU checkpoint CLI E2E와 cache/no-cache logits·생성 동등성: 통과
- CUDA smoke/latency-memory: 실행 환경의 CUDA 가용성에 따라 결과 기록
- `git diff --check`: whitespace 오류 없음

### M5 GB10 CUDA smoke/benchmark 실측

- PyTorch `2.13.0+cu130`이 NVIDIA GB10을 인식했다.
- 2-layer, `d_model=64`, context 64 임시 모델에서 KV cache greedy 16-token 생성을 수행했다.
- latency `0.377293초`, 처리량 `42.407 token/s`, PyTorch peak allocation `34,166,272 byte`였다.
- cache decode logits는 모두 유한값이었다. 이 수치는 기능 smoke이며 baseline 모델 성능 수치가 아니다.
## 2026-07-11 · M6 전체 pipeline 계약과 외부 baseline gate (0.7.0)

- `PipelineConfig`에 저장공간·available memory·시간·에너지·파라미터·token 예산, 단계 명령, 출력, timeout과 필수 증거를 엄격히 모델링했다.
- `llmex pipeline preflight/run/status/drill/export`를 추가했다. 명령은 shell을 거치지 않고 실행되며 단계별 stdout/stderr tail, 종료 코드, 경과 시간, 출력 존재, config/evidence SHA-256과 재개 상태를 보존한다.
- 외부 단계는 필수 증거가 모두 존재하고 `--allow-external`을 명시하지 않으면 실행하지 않는다. 전체 dump나 장기 학습이 없을 때 완료로 보이는 fall-through를 차단했다.
- baseline을 정확히 87,804,672 parameters, 16k vocab, context 1024로 고정하고 120M 상한, 최대 6.5536B token, 168시간, 35kWh 예산을 설정했다.
- aarch64 DGX Spark에서 preflight와 model inspect를 실제 실행했다. available memory 약 27.6GiB, NVMe free 약 1.90TiB로 통과했고 모델/AdamW 정적 추정은 약 335MiB/1.31GiB였다.
- Wikimedia 20260701 dump 1,398,909,939 bytes를 실제 다운로드했다. 공식 SHA-1 `291b50…e1f98`과 일치했고 로컬 SHA-256 `991b26…5582`를 계산했다. 실제 선두 1,000문서 canary에서 997문서가 통과하고 exact 중복은 0건이었다.
- 같은 실제 canary로 16k/32k tokenizer를 모두 학습·평가했다. 32k가 token 수를 8.46% 줄였지만 artifact/embedding 비용 때문에 전체 corpus 처리량 승인 전 16k를 조건부 선택했다.
- GB10에서 87.8M 모델을 context 256, micro batch 1로 실제 100 step 학습해 41.12초, 마지막 2,479.94 token/s, PyTorch peak 1.67GiB를 기록했고 고정 NGC container bf16 smoke도 재통과했다.
- fixture pipeline test가 외부 대기→증거 공급→재개 완료, 출력 검증, 상태 fingerprint 복구 drill, dashboard export와 CLI status를 검증한다.
- `docs/baseline-report.md`, `docs/baseline-runbook.md`, ADR-015/016과 M6 검증표를 추가하고 모든 사용자 노출 설명을 한국어로 작성했다.

## 2026-07-11 · M7 공개 준비와 도구 안정 릴리스 (1.0.0)

- 프로젝트와 패키지 버전을 1.0.0으로 올리고 frozen lock을 갱신했다.
- data/model/tokenizer card, NOTICE, 보안·개인정보 정책, threat model, 운영 runbook, API/CLI, failure mode, migration, changelog, reproducibility와 acceptance matrix를 한국어로 추가했다.
- `llmex release audit`이 비밀 의심 문자열, 배포 금지 절대 경로, 필수 릴리스 문서와 production의 `0.ref` import 경계를 검사하도록 구현했다.
- `llmex release bundle`이 모든 배포 후보 파일의 SHA-256/byte manifest, CycloneDX 1.5 SBOM, in-toto statement와 SLSA provenance 형식 진술, 재현 명령을 생성하도록 구현했다.
- `llmex release gate`는 법무 검토·장기 baseline·공개 배포 결정 각각의 `approved=true`, 승인자, 시각, 근거가 없으면 종료 코드 5로 실패한다. 이 gate는 외부 결정을 자동으로 만들거나 자기 승인하지 않는다.
- MIT 소프트웨어 라이선스와 Wikipedia/참조/가중치 조건의 비법률적 경계를 분리했다. 원 데이터와 가중치는 패키지에 포함하지 않는다.
- sdist/wheel build, 새 가상환경 wheel 설치와 version/help smoke, wheel `0.ref` 제외, CLI/pipeline E2E, release generator/gate 회귀 테스트를 CI에 추가했다.
- ADR-017에서 1.0 도구 릴리스와 모델·데이터 공개 승인을 분리했다. 로컬 acceptance가 통과해도 외부 세 gate는 승인 증거 전까지 공개 금지 상태다.

### M7 마감 검증 기록

- `uv sync --frozen`: 1.0.0 lock 변경 없이 통과했다.
- `uv run ruff format --check .`; `uv run ruff check .`: 49개 Python 파일 format, lint 통과했다.
- `uv run pyright`: strict 오류·경고 0건이었다.
- `uv run pytest -q`: 전체 `49 passed`; M6/M7 CLI·pipeline 표적 E2E `5 passed`였다.
- `uv build`: `llmex-1.0.0.tar.gz`와 `llmex-1.0.0-py3-none-any.whl` 생성에 성공했다.
- 새 Python 3.11 venv에 wheel과 55개 의존성을 설치하고 1.0.0 version 및 모든 명령군 help smoke를 통과했다.
- sdist의 NOTICE·ATTRIBUTION·model card·examples 포함, sdist/wheel의 `0.ref` 제외와 wheel LICENSE 포함을 검사했다.
- `llmex release audit`은 비밀·로컬 경로·필수 문서·참조 경계를 통과했다. bundle은 120개 파일, 65개 설치 구성요소의 checksum/SBOM/provenance를 생성했다.
- 빈 외부 승인 파일은 의도대로 종료 코드 5로 실패했다. 참조 SHA-256과 `git diff --check`도 통과했다.
- 외부 미실행 항목: 전체 corpus 장기 baseline, 독립 법무·데이터·안전 검토, 공개 채널 배포.

## 2026-07-11 · M0–M7 최종 AI slop 정리 (1.0.1)

- 범위를 `d2cebc0^..c55078a`의 변경 파일로 고정하고 수정 전 전체 `49 passed`로 동작을 잠갔다.
- fallback-like inventory에서 downloader 재시도 루프 뒤의 도달 불가능한 대체 오류 분기를 masking fallback slop으로 분류해 삭제했다. 재시도 소진 시 원인 문자열을 보존한 `InputError`가 발생하는 회귀 테스트를 추가했다.
- `/proc/meminfo` 읽기 실패 시 자원 검사를 실패시키는 경로, 원자 저장의 임시 파일 정리, Git 정보 비가용 표시, tokenizer byte fallback은 실패-폐쇄 또는 외부 호환성 경계로 분류해 보존했다.
- dead code 외 duplication, naming/error handling, 불필요한 abstraction은 공개 계약을 유지하면서 개선할 고신뢰 후보가 없어 변경하지 않았다. 새 의존성은 추가하지 않았다.
- 프로젝트·패키지 버전을 1.0.1로 올리고 `uv.lock`, CLI·bundle 버전 회귀 테스트, 한국어 릴리스 문서를 동기화했다.

### 1.0.1 cleanup 검증 기록

- 표적 회귀 테스트: `18 passed`
- Ruff format/check: 49개 Python 파일 통과
- Pyright strict: 오류·경고 0건
- 전체 Pytest: `50 passed`
- release audit: 비밀·로컬 경로·필수 문서·참조 import 경계 통과
- build/bundle: `llmex-1.0.1.tar.gz`, `llmex-1.0.1-py3-none-any.whl`, 120개 파일 checksum과 65개 구성요소 SBOM 생성 통과
- `git diff --check`: whitespace 오류 없음

## 2026-07-11 — 1.1.0 최종 리뷰 차단 해소

- 보호 CI trust store 기반 HMAC-SHA256 승인 서명, RFC3339 발급·만료, issuer/role allowlist, 승인자 분리, evidence SHA-256, 버전·Git commit·config fingerprint 결속을 구현했다.
- pipeline evidence schema와 빈 JSON 거부, 단계 산출물 checksum/크기/schema 재검증, 실행 중 time/token/energy budget 중단, 실제 중단·손상·정리·재개 drill을 추가했다.
- checkpoint는 `weights_only=True`만 사용하며 NumPy RNG를 안전 tensor/basic type으로 저장한다. 악성 pickle 비실행 회귀를 추가했다.
- cloze 조건부 평균 log-likelihood·rank·accuracy와 canary 실제 rank gate/미실행 실패-폐쇄, 단일-pass 유계 메모리 exact/near contamination을 구현했다.
- 재개 세션 delta 처리량과 누적 wall-time 처리량을 분리하고 wheel/sdist digest, wheel METADATA 기반 SBOM, 배포 artifact subject provenance를 생성한다.
- artifact/JSON/sidecar 원자 쓰기·fsync 계약을 통일하고 split ADR을 실제 normalized-content SHA-256 계약과 일치시켰다.

## 2026-07-11 — 1.3.0 긴급 보안 키 회전

- 기존 1.3.0 root/issuer 키는 private key 로그 노출로 즉시 폐기했으며 더 이상 신뢰할 수 없다.
- 비밀키는 저장소, 로그 또는 명령 인자에 저장하지 않는다.
- 새 production policy는 fail-closed provisioning anchor로 교체했다. 실제 issuer private key는
  보호된 CI KMS/HSM에서 별도로 provisioning해야 한다.

## 2026-07-11 — 한국어 실행 가이드 추가

- `docs/run-guide.md`에 공식 Wikimedia dump URL·SHA-1과 프로젝트 고정 SHA-256을 구분해 기록했다.
- data download, 1,000문서 canary E2E, 전체 extract/clean/dedup/split/report, tokenizer
  train/evaluate/pack, model inspect, smoke train/resume, eval/generate/benchmark의 실제 `uv run`
  명령과 입력·출력 경로를 실행 순서대로 정리했다.
- `docs/README.md`에서 실행 가이드를 연결하고 Markdown 링크와 CLI help 계약을 점검했다.
