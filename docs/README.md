# LLMEX 문서

LLMEX는 《LLM을 만들기 위한 수학 기반 이론과 Python 실습》의 토크나이저, Transformer, 사전학습, nano-GPT 내용을 실제 한국어 Wikipedia 학습 프로젝트로 확장한다.

개발 시작 순서:

1. [실행 가이드](run-guide.md)에서 데이터 확보부터 학습·추론까지 실제 명령과 경로를 확인한다.
   대화 학습은 [한국어 대화 SFT 가이드](chat-sft.md), teacher 수집은 [teacher 증류 데이터 실행 가이드](teacher-distillation.md)를 함께 확인한다.
2. [PRD](prd.md)에서 제품 목표와 완료 기준을 읽는다.
3. [구현 계획](plan.md)에서 아키텍처와 단계별 검증 명령을 확인한다.
4. [TODO](todo.md)의 `M0`부터 체크하며 구현한다.
5. 중요한 결정은 [결정 기록](decisions.md)에 추가한다.
6. 구현 전에 [`../0.ref/README.md`](../0.ref/README.md)에서 기반 교재 참조 코드와 사용 경계를 확인한다.

현재 상태: 1.7.0. 공개 데이터 자체의 train/heldout canonical prompt overlap 152개와 공개 train·teacher heldout 교차 overlap 658개(공개 train 879행 영향)를 실측해 단순 concat을 금지했다. `sft prepare-mix/preflight-mix/status-mix/validate-mix`는 teacher manifest SHA를 고정하고 heldout prompt·원천 우선 격리, tokenizer 길이 gate, 원자 lock·staging과 내부 전용 release blocked 계승을 적용한다. 정식 qwen36mtp v5 수집은 진행 중이므로 현재 건수는 `distill status`로 확인한다. 완료 뒤 export manifest SHA를 mix config에 고정하고 pilot/full SFT 설정을 만든다. [teacher 증류 데이터 실행 가이드](teacher-distillation.md), [한국어 대화 SFT 가이드](chat-sft.md), [M7 릴리스 체크리스트](release-checklist.md), [재현성 bundle](reproducibility.md), [acceptance matrix](acceptance-matrix.md)에 실행 계약과 외부 승인 경계를 기록한다.
