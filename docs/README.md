# LLMEX 문서

LLMEX는 《LLM을 만들기 위한 수학 기반 이론과 Python 실습》의 토크나이저, Transformer, 사전학습, nano-GPT 내용을 실제 한국어 Wikipedia 학습 프로젝트로 확장한다.

개발 시작 순서:

1. [수학 기반 이론·Python 실습 교재](book/README.md)에서 환경부터 release까지 00~15장을 순서대로 학습한다.
2. [실행 가이드](run-guide.md)에서 데이터 확보부터 학습·추론까지 실제 명령과 경로를 확인한다.
   대화 학습은 [한국어 대화 SFT 가이드](chat-sft.md), teacher 수집은 [teacher 증류 데이터 실행 가이드](teacher-distillation.md)를 함께 확인한다.
3. [PRD](prd.md)에서 제품 목표와 완료 기준을 읽는다.
4. [구현 계획](plan.md)에서 아키텍처와 단계별 검증 명령을 확인한다.
5. [TODO](todo.md)의 `M0`부터 체크하며 구현한다.
6. 중요한 결정은 [결정 기록](decisions.md)에 추가한다.
7. 구현 전에 [`../0.ref/README.md`](../0.ref/README.md)에서 기반 교재 참조 코드와 사용 경계를 확인한다.

현재 상태: 1.9.2. README와 00~15장으로 구성된 [실습 교재](book/README.md)가 현재 코드·설정·CLI의 데이터→학습→평가→품질→release 경로를 재현한다. SFT mix는 모든 assistant turn의 주민번호·휴대전화·이메일·secret과 안전한 추가 규칙을 학습 전에 제외하고, 원천 identity가 없던 공개 행에는 원행 SHA/ID를 계승해 teacher 파생행과 정확히 결속한다. 기존 자동·수동 품질 gate와 네 단계 외부 승인 계약은 유지되며, production trust policy에 실제 운영 역할이 등록되기 전 승인은 의도적으로 실패한다. 정식 qwen36mtp v5 수집과 실제 학습 모델의 사람 검토는 별도 진행 상태다. [실행 가이드](run-guide.md), [한국어 대화 SFT 가이드](chat-sft.md), [teacher 증류 데이터 실행 가이드](teacher-distillation.md), [M7 릴리스 체크리스트](release-checklist.md)에 실행 계약과 외부 승인 경계를 기록한다.
