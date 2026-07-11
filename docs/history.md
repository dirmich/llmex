# 구현 이력

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
