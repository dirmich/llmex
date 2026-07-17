# LLMEX를 밑바닥부터 만드는 실습 교재

이 교재는 작은 한국어 decoder-only 언어 모델을 빈 Python 프로젝트에서 재구성하는 학습 경로다. 완성 코드의 행별 해설이 아니라 입력·출력·불변식·실패 조건을 먼저 세우고 작은 모듈을 하나씩 검증한다. 현재 경로·상태·명령의 권위는 이 저장소의 `src/llmex`, `configs`, 현재 `docs`와 CLI `--help`다. [프로젝트 계획](../../../knowledge_base/Codex/LLMEX/프로젝트%20계획.md)은 과거 의사결정과 M0 시점의 역사 snapshot으로만 참고하며, 그 문서의 개인 macOS 절대경로나 낡은 단계 지시를 현재 명령으로 복제하지 않는다.

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

처음에는 00~08장을 CPU smoke 설정으로 끝낸다. 그다음 09~13장의 대화 경로를 오프라인 fixture로 검증하고, 마지막에만 실제 teacher·GPU·장기 학습을 사용한다. 각 장의 체크리스트가 모두 통과하기 전에는 다음 단계의 큰 실행을 시작하지 않는다.

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
