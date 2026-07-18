# LLMEX를 밑바닥부터 만드는 실습 교재

이 교재는 작은 한국어 decoder-only 언어 모델을 빈 Python 프로젝트에서 재구성하는 학습 경로다. 완성 코드의 행별 해설이 아니라 입력·출력·불변식·실패 조건을 먼저 세우고 작은 모듈을 하나씩 검증한다. 현재 경로·상태·명령의 권위는 이 저장소의 `src/llmex`, `configs`, 현재 `docs`와 CLI `--help`다. [프로젝트 계획](../../../knowledge_base/Codex/LLMEX/프로젝트%20계획.md)은 M0부터 1.5.2까지 누적된 외부 운영 wiki snapshot이며 현재 저장소보다 후순위다. 그 문서의 개인 macOS 절대경로나 과거 checkpoint 수치를 현재 명령·결과로 복제하지 않는다.

## 이 책의 독자와 진입점

- Python과 PyTorch tensor 연산을 처음부터 구현하고 싶은 독자는 00장부터 순서대로 진행한다.
- Transformer 수학을 알고 있는 독자는 03~08장으로 데이터·재현 계약을 먼저 익힌 뒤 16장의 모델 모듈 지도를 사용한다.
- base model은 있고 대화 학습이 목적인 독자는 07장의 checkpoint 계약을 확인한 뒤 09~13장을 진행한다.
- 운영·출시 담당자는 01~02장, 08장, 12~15장과 `meta/`의 주장·출처 원장을 함께 검토한다.

선수 지식은 Python type hint, JSON/YAML, 기본 선형대수, cross entropy, Git이다. CUDA kernel 구현이나 분산 학습 경험은 필수가 아니다.

## 학습 경로

| 단계 | 장 | 결과 |
|---|---|---|
| 기반 | [00 환경과 저장소](00-environment-repo-tour.md) → [01 요구사항과 실패-폐쇄](01-requirements-reproducibility.md) → [02 설정과 provenance](02-config-fingerprint-provenance.md) | 재현 가능한 실행 골격 |
| 데이터 | [03 데이터 파이프라인](03-data-pipeline.md) → [04 토크나이저와 chat template](04-tokenizer-chat-template.md) | provenance가 보존된 token/chat 입력 |
| 모델 | [05 Transformer 수학](05-transformer-components-math.md) → [06 모델 조립과 생성](06-model-forward-generation.md) | causal decoder와 KV cache 생성 |
| 학습·평가 | [07 사전학습과 checkpoint](07-pretraining-checkpoint-resume.md) → [08 평가와 오염](08-evaluation-contamination-canary.md) | 중단 복구 가능한 학습과 봉인 평가 |
| 대화 | [09 teacher 증류](09-teacher-distillation.md) → [10 공개+teacher mix](10-public-teacher-mix.md) → [11 assistant-only SFT](11-assistant-only-sft.md) | 누출을 차단한 대화 학습 |
| 품질·출시 | [12 자동 품질 gate](12-automatic-quality-gate.md) → [13 수동 blind review](13-manual-blind-review.md) → [14 릴리스와 GGUF](14-release-export-gguf.md) | 자동·사람 품질 증거와 공개 경계 |
| 종합 | [15 capstone과 문제 해결](15-capstone-troubleshooting.md) | 데이터부터 추론까지 독립 재구성 |
| 코드 지도 | [16 코드 모듈 지도](16-code-module-atlas.md) | `src/llmex` Python 모듈 57개의 책임·입출력·불변식 추적 |
| 제작 워크북 | [17 단계별 제작 워크북](17-guided-build-workbook.md) | 빈 골격에서 대화 품질·릴리스까지 직접 재구현 |
| 평가·해설 | [18 학습 평가와 rubric](18-assessment-rubric.md) | 진단·exit ticket·capstone 채점 기준 |

처음에는 00~08장을 CPU smoke 설정으로 끝낸다. 그다음 09~13장의 대화 경로를 오프라인 fixture로 검증하고, 마지막에만 실제 teacher·GPU·장기 학습을 사용한다. 각 장의 체크리스트가 모두 통과하기 전에는 다음 단계의 큰 실행을 시작하지 않는다.

개념을 순서대로 공부하려면 00~15장을 읽고, 특정 파일의 책임을 찾으려면 16장을 색인으로 사용한다. 완성 코드를 보지 않고 직접 만들어 보려면 17장의 0~12단계를 수행한 뒤 해당 단계에서 연결한 원본 모듈과 비교한다.

## 트랙별 비용과 경계

| 트랙 | 네트워크 | 장치 | 대략 시간 | 여유 공간 | 증명하는 것 |
|---|---|---|---|---|---|
| fixture CPU | 설치 때만 | CPU, RAM 8 GiB+ | 1~3시간 | 10 GiB | 모듈·CLI·재개 계약 |
| CUDA pilot | 데이터 확보 때 | bf16 CUDA, RAM/VRAM은 설정 의존 | 수분~수시간 | 100 GiB+ | 실제 forward·학습·checkpoint |
| 100M base | dump 확보 때 | DGX Spark급, unified memory 관찰 | 수일 | 1 TiB+ | 대규모 pretraining 실행 |
| teacher 10k | localhost endpoint | teacher 장치 별도 | 수시간~수일 | 50 GiB+ | provenance가 있는 instruction 생성 |
| full SFT·품질 | 원칙적으로 offline | bf16 CUDA | 수십 분~수시간 | checkpoint당 약 1 GiB+ | 실제 대화 자동 품질 |
| 수동·공개 | 검토 채널 의존 | 무관 | 사람 일정 의존 | artifact 보존량 의존 | 독립 품질·법무·공개 승인 |

시간과 공간은 현재 100M 기준의 계획값이며 보장값이 아니다. 실제 preflight와 run artifact의 wall time, RSS, peak allocation, disk 사용량을 권위값으로 사용한다.

## 교재의 공통 규칙

- 설정·입력·checkpoint·평가물은 경로가 아니라 내용 SHA-256과 fingerprint로 결속한다.
- attribution 손실, split 누출, tokenizer round-trip, causal leakage, checkpoint 복구 실패는 경고가 아니라 즉시 중단이다.
- `data/`, `artifacts/`, `runs/`는 큰 영속 산출물이며 Git 소스와 분리한다.
- smoke 성공은 모델 품질, 법무 승인 또는 외부 공개 승인이 아니다.
- 모든 명령은 저장소 루트에서 `uv run ...`으로 실행한다고 가정한다.
- 예제는 저장소 기준 상대 경로만 사용하고 개인 홈·macOS 절대 경로를 기록하지 않는다.
- stock YAML은 서로 다른 milestone의 기록일 수 있다. 파생 설정 지시가 있으면 원본을 그대로 실행하지 말고 복사 후 upstream artifact 경로·SHA·vocab을 수정하고 `llmex config validate`를 먼저 통과시킨다.

## 완주 기준

`uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run llmex release audit`가 통과하고, capstone의 manifest·checkpoint·평가 artifact가 현재 입력에서 재검증되어야 한다. 외부 공개는 별도의 수동 품질·법무·책임자 승인이 있어야 한다.

00~08장은 저장소에 포함된 fixture로 실행 가능한 기본 capstone이다. 09~13장은 teacher 또는 offline fixture, 검증된 chat data와 동적 SHA가 필요한 대화 확장이다. 14장의 GGUF/llama.cpp parity는 현재 구현된 CLI가 아니라 후속 연구실의 acceptance contract이므로, converter와 parity test를 실제 구현하기 전에는 필수 실행 성공으로 기록하지 않는다.

책 원고의 독자 약속, 문체, 출처와 검증 가능한 주장은 [제작 메타데이터](meta/README.md)에서 관리한다.
