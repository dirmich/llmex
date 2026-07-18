# LLMEX

LLMEX 1.21.3은 날짜가 고정된 한국어 Wikipedia 사전학습, 허가된 JSONL 대화 데이터의 assistant-only SFT와 내부 전용 teacher 증류 데이터 수집을 위한 재현 가능한 교육·연구 도구다. 정식 Qwen v5 10k는 현재 CLI에서 completed 10,000, accepted 9,712, pending 0과 export overlap 0으로 재검증됐다. 정확도·안전 중심 162응답 gate와 인사·일상·근거·기억 중심 120응답 준비도 gate를 함께 제공하며, 기존 v11 step 50은 준비도 정확도 45%로 실패했다. 공개+teacher mix와 후속 curriculum manifest를 최종 SFT에 SHA로 결속하며 내부 teacher 출력·가중치·corpus는 외부 공개하지 않는다.

## 빠른 시작

```bash
uv sync
uv run llmex --help
uv run llmex config validate configs/data/sample.yaml --kind data
uv run llmex run create --config configs/model/smoke.yaml --kind model --dry-run
uv run llmex train smoke --config configs/training/smoke.yaml --dry-run
uv run llmex sft preflight --config configs/sft/smoke.yaml --no-measure-baseline
uv run llmex sft quality-preflight --config <quality-config.yaml>
uv run llmex sft quality-review-template --config <quality-config.yaml>
uv run llmex sft quality-gate --help
uv run llmex sft quality-review-validate --help
uv run llmex sft train --config configs/sft/smoke.yaml --dry-run
uv run llmex sft --help
uv run llmex distill --help
make check
uv run llmex release audit
uv run llmex release bundle --output dist/reproducibility
```

Python 3.11 이상과 `uv`가 필요하다. 테스트는 네트워크와 GPU를 사용하지 않는다.

## 주요 경로

- `configs/`: 검증 가능한 데이터·모델 YAML
- `src/llmex/`: production 패키지. `0.ref`를 import하지 않는다.
- `tests/fixtures/`: 작은 오프라인 MediaWiki XML bzip2 fixture
- `data/`, `artifacts/`, `runs/`: Git에 넣지 않는 host 영속 데이터
- `docs/environment.md`: 로컬·DGX Spark 환경 계약
- `docs/history.md`: 구현·검증 이력
- `docs/book/`: 환경부터 release까지 이어지는 00~20장 교재, 57개 모듈 카드와 결정적 smoke 예제
- `docs/chat-sft.md`: JSONL 대화 데이터, SFT 재개, 평가·생성 계약
- `docs/teacher-distillation.md`: teacher 10k 준비·수집·재개·export·검증 계약

## 컨테이너

DGX Spark에서는 먼저 장비 driver와 호환되는 ARM64 NGC PyTorch 이미지 digest를 확인해 `.env`의 `LLMEX_BASE_IMAGE`에 넣는다. 이후 다음 명령을 사용한다.

```bash
cp .env.example .env
docker compose build
docker compose run --rm dev make check
docker compose run --rm --gpus all dev python scripts/cuda_smoke.py
```

Compose는 저장소, `data/`, `artifacts/`, `runs/`를 host bind mount하며 학습 컨테이너는 `network_mode: none`으로 실행할 수 있다.

## 오류 코드

| 코드 | 의미 |
|---:|---|
| 0 | 성공 |
| 2 | YAML/설정 검증 실패 |
| 3 | 입력 파일 실패 |
| 4 | 기존 출력과 충돌 |
| 5 | 무결성 실패 |
| 70 | 예상하지 못한 내부 오류 |

자세한 목표와 이후 milestone은 [`docs/`](docs/README.md)를 참고한다.
