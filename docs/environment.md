# 실행 환경

## 재현 계약

- Python: 3.11 이상
- 패키지 관리자: `uv 0.10.2`
- 로컬 품질 게이트: Ruff, Pyright strict, Pytest
- 단위 테스트: 외부 네트워크와 GPU를 사용하지 않음
- 영속 경로: host의 `data/`, `artifacts/`, `runs/`
- 비밀정보: `.env`, Docker credential store에 두고 Git에 기록하지 않음

`uv.lock`은 `uv sync`가 만든 정확한 Python 의존성 해석 결과다. CI는 `--frozen`으로 lock 변경을 금지한다.

## 현재 M0 검증 환경

2026-07-11에 실제 DGX Spark에서 M0 인수 검증을 수행했다.

- 아키텍처와 운영체제: `aarch64` Ubuntu, kernel `6.17.0-1014-nvidia`
- GPU: NVIDIA GB10
- NVIDIA driver: `580.142`
- CUDA compatibility: `13.0`
- NVMe `/`: 전체 `3.6T`, 사용 가능 `1.9T`
- RAM: 전체 `119Gi`, 사용 가능 `28Gi`
- swap: 전체 `15Gi`, 사용 `11Gi`
- Docker: `29.2.1`
- `nvidia-smi` framebuffer memory: `Not Supported`

검증 이미지는 다음 digest로 고정한다.

```text
nvcr.io/nvidia/pytorch:25.10-py3@sha256:42263b2424fc237b34c4fc4a91c30d603c57eed36e37d31ff6d9a4f1f801edee
```

로컬 이미지 `nvcr.io/nvidia/pytorch:25.10-py3`의 digest가 위 값임을 확인한 뒤 다음 smoke test를 실행했다.

```bash
docker run --rm --gpus all \
  nvcr.io/nvidia/pytorch:25.10-py3@sha256:42263b2424fc237b34c4fc4a91c30d603c57eed36e37d31ff6d9a4f1f801edee \
  python scripts/cuda_smoke.py
```

결과는 PyTorch `2.9.0a0+145a3a7`, CUDA `13.0`, NVIDIA GB10이었으며 bf16 행렬곱 결과는 `finite=true`였다. 따라서 NVIDIA Container Runtime의 GPU 전달과 컨테이너 CUDA bf16 연산을 모두 통과했다. `nvidia-smi`의 framebuffer `Not Supported` 표시는 이 통합 GPU에서 실패 판정 근거로 사용하지 않는다.

## DGX Spark 인수 절차

장비에서 다음 결과를 `runs/<run-id>/environment.json` 또는 운영 기록에 보존한다.

```bash
uname -m
cat /etc/os-release
nvidia-smi
df -h /path/to/llmex
docker info | grep -i runtime
docker buildx imagetools inspect "$LLMEX_BASE_IMAGE"
docker compose run --rm --gpus all dev python scripts/cuda_smoke.py
```

`uname -m`은 `aarch64`여야 한다. `nvidia-smi`가 DGX Spark iGPU의 framebuffer memory를 `Not Supported`로 표시하더라도 GPU 미인식으로 단정하지 않는다. 최종 판정은 PyTorch가 CUDA tensor를 만들고 bf16 행렬곱을 유한값으로 완료하는지로 한다.

`Dockerfile`, `.env`, `.env.example`, `docker-compose.yml`의 기본 이미지는 실제 DGX Spark smoke test를 통과한 동일 digest로 고정한다. 태그만 사용하거나 검증 없이 digest를 변경하면 M0 재현 기준에서 벗어난다.

## bind mount와 오프라인 실행

`docker-compose.yml`의 `dev` 서비스는 source와 세 영속 경로를 bind mount한다. `offline` 서비스는 같은 mount에 `network_mode: none`을 추가한다. 이미지 pull과 dump download만 네트워크 구간에서 수행하고, 설정 검증·정제·학습·평가는 오프라인 서비스에서 재현할 수 있어야 한다.
