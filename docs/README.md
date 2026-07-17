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

현재 상태: 1.6.0, 전체 Wikipedia corpus/tokenizer와 100k baseline 학습, full latest validation/test 평가, SFT strict 재개와 teacher 10k schema 2 수집 파이프라인을 완료했다. qwen36mtp v3 inventory 10,000건과 preflight는 준비됐지만 실제 collect는 pending 10,000이다. teacher 출력은 내부 전용이며 release blocked다. 다음은 실제 collect/resume, current spool export/validate, 공개 instruction+teacher 혼합 SFT와 대화/EOS/repetition/safety/manual gate다. [teacher 증류 데이터 실행 가이드](teacher-distillation.md), [한국어 대화 SFT 가이드](chat-sft.md), [M7 릴리스 체크리스트](release-checklist.md), [재현성 bundle](reproducibility.md), [acceptance matrix](acceptance-matrix.md)에 실행 계약과 외부 승인 경계를 기록한다.
