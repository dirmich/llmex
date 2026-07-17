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

현재 상태: 1.8.1. SHA 고정 자동 품질 gate에 이어 `sft quality-review-template/quality-gate/quality-review-validate` 수동 blind review gate가 구현됐다. 자동 full-row와 artifact, sampling challenge에 결속된 최소 100개 표본과 safety-critical 전수를 context blind 형식으로 검토하며, 독립 quality 2명·safety 1명·필요 시 adjudicator의 서명과 단일 trust snapshot을 검증한다. effective score matrix의 dimension/category 평균 4.0, 핵심 항목 4점 이상 90%, critical·safety veto를 실패-폐쇄로 적용하고 원자 artifact를 release 네 번째 필수 gate에 strict 결속한다. production trust policy에는 신규 역할이 아직 등록되지 않아 실제 운영 승인은 의도적으로 실패한다. 정식 qwen36mtp v5 수집과 실제 학습 모델의 사람 검토는 별도 진행 상태다. [실행 가이드](run-guide.md), [한국어 대화 SFT 가이드](chat-sft.md), [teacher 증류 데이터 실행 가이드](teacher-distillation.md), [M7 릴리스 체크리스트](release-checklist.md)에 실행 계약과 외부 승인 경계를 기록한다.
