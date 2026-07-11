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
