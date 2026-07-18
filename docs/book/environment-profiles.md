# 부록 A. 환경 프로필과 챕터별 준비표

이 부록은 독자가 각 장을 시작하기 전에 어떤 환경이 필요한지 빠르게 판정하는 체크시트다. 장치가 큰 환경일수록 더 높은 학습 단계가 아니라 더 큰 입력을 실행할 수 있을 뿐이다. 모든 계약은 CPU fixture에서 먼저 검증한다.

## 1. 공통 설치

```bash
git clone <저장소-주소> llmex
cd llmex
python3 --version
uv --version
uv sync --frozen
uv run llmex --version
```

기준은 Python 3.11 이상, lockfile과 호환되는 `uv`, Git revision을 읽을 수 있는 checkout이다. `uv sync --frozen`이 lockfile 변경을 요구하면 중단한다. 개인 경로, API key, teacher 원문 응답은 Git에 기록하지 않는다.

## 2. 네 가지 실행 프로필

### CPU 교재 프로필

- 용도: 00~08장, 16~20장, 작은 offline 증류·mix·SFT
- 권장: RAM 8 GiB 이상, 빈 공간 10 GiB 이상
- 확인: `uv run pytest -q tests/test_foundation.py tests/test_config.py`
- 한계: 작은 모델의 기능과 재현 계약만 증명하며 대화 품질을 증명하지 않는다.

### CUDA pilot 프로필

- 용도: 07장 학습, 11장 SFT의 장치·메모리·throughput pilot
- 필수: CUDA 인식 PyTorch, bf16 지원 장치 또는 명시적 fp32 fallback
- 확인:

```bash
uv run python -c 'import torch; print({"cuda": torch.cuda.is_available(), "bf16": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False, "torch": torch.__version__})'
```

- 한계: pilot checkpoint를 정식 full run에 이어 학습하지 않는다. 같은 base에서 새 run을 시작한다.

### DGX Spark 장기 프로필

- 용도: 전체 corpus, 100M pretraining, 장기 SFT
- 필수: 고정 container digest, host NVMe, unified memory·RSS·swap 관찰
- 확인: `free -h`, `df -h . data artifacts runs`, `nvidia-smi`, 실제 preflight JSON
- 한계: 전용 VRAM 하나만으로 수용 가능성을 판단하지 않는다.

### Local teacher 프로필

- 용도: 09장 teacher 10k response distillation
- 필수: loopback OpenAI-compatible `/v1`, model identity, timeout·응답 byte 제한
- 확인:

```bash
curl --fail --silent --show-error http://localhost:8081/v1/models
uv run llmex distill preflight --config configs/distill/qwen36mtp-10k.yaml
```

- 한계: teacher 출력은 내부 전용 라이선스와 release block을 계승한다.

## 3. 챕터별 준비표

| 장 | 최소 프로필 | 추가 입력 | 시작 전 명령 | 종료 증거 |
|---:|---|---|---|---|
| 00 | CPU | 없음 | `uv sync --frozen` | CLI/version/config 검증 |
| 01 | CPU | 작은 임시 파일 | foundation test | 원자 쓰기·오류 코드 |
| 02 | CPU | YAML fixture | config test | 설정 fingerprint·SHA |
| 03 | CPU | sample XML bz2 | `data sample-e2e` | provenance corpus manifest |
| 04 | CPU | sample corpus | tokenizer smoke | Unicode round-trip·packed SHA |
| 05 | CPU | model smoke YAML | `model inspect` | shape·causal·parameter 수 |
| 06 | CPU | 작은 checkpoint | M3/M5 test | cache/no-cache parity |
| 07 | CPU, 선택 CUDA | packed shard | train smoke | 완전 재개·checkpoint audit |
| 08 | CPU | evaluation fixture | eval smoke | PPL·canary·contamination 상태 |
| 09 | CPU fixture, 실제 수집은 teacher | public chat·corpus | distill test/preflight | inventory·spool·export validate |
| 10 | CPU | public/teacher 4 split | mix preflight | prompt/source overlap 0 |
| 11 | CPU tiny, 실제 학습은 CUDA | tokenizer·mix manifest·base | SFT preflight | assistant-only loss·checkpoint |
| 12 | CPU tiny 또는 CUDA | suite·checkpoint SHA | quality preflight | 고정 rollout·자동 gate |
| 13 | CPU | 자동 평가 artifact | review template | 독립 서명 또는 명시적 차단 |
| 14 | CPU | wheel/sdist | release audit/build | checksum·SBOM·provenance |
| 15 | 선택한 전체 트랙 | 앞 장 산출물 | capstone 표 | 입력부터 결과까지 SHA 사슬 |
| 16 | CPU | `src/llmex` | book test | 57개 모듈 일대일 지도 |
| 17 | CPU→선택 GPU | 단계별 fixture | 각 단계 표적 test | 빈 골격 재구현 기록 |
| 18 | CPU | 학습 기록 | exit ticket | rubric 점수·근거 |
| 19 | CPU | 모듈별 fixture | `tests/test_book.py` | 57개 파일별 계약·실패 test |
| 20 | CPU | 교재 생성 fixture | offline chat E2E | mix→SFT→추론→품질 artifact |

## 4. 저장 공간과 산출물 경계

```text
Git 추적: src/ tests/ configs/ docs/ pyproject.toml uv.lock
Git 제외: data/ artifacts/ runs/ dist/의 대용량·실행 산출물
```

파일명 `latest`는 편의 포인터일 뿐 신뢰 근거가 아니다. 다음 단계 설정에는 실제 입력 파일과 manifest/checkpoint의 SHA-256을 고정한다. 교재 smoke의 작은 산출물도 같은 규칙을 사용한다.

## 5. 시작 전 공통 기록 양식

```markdown
- 장/실습:
- Git revision:
- Python/uv/PyTorch:
- 장치와 precision:
- 입력 파일 SHA-256:
- 설정 fingerprint:
- 예상 시간·공간:
- 실행하지 않는 경계:
```

이 기록으로 실패가 코드, 입력, 설정, 장치 중 어디에서 발생했는지 분리한다.
