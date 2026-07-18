# LLMEX 문서

LLMEX는 《LLM을 만들기 위한 수학 기반 이론과 Python 실습》의 토크나이저, Transformer, 사전학습, nano-GPT 내용을 실제 한국어 Wikipedia 학습 프로젝트로 확장한다.

개발 시작 순서:

1. [수학 기반 이론·Python 실습 교재](book/README.md)에서 환경부터 release까지 00~19장을 순서대로 학습하고, 19장의 57개 모듈 카드를 따라 파일별로 구현한다.
2. [실행 가이드](run-guide.md)에서 데이터 확보부터 학습·추론까지 실제 명령과 경로를 확인한다.
   대화 학습은 [한국어 대화 SFT 가이드](chat-sft.md), teacher 수집은 [teacher 증류 데이터 실행 가이드](teacher-distillation.md)를 함께 확인한다.
3. [PRD](prd.md)에서 제품 목표와 완료 기준을 읽는다.
4. [구현 계획](plan.md)에서 아키텍처와 단계별 검증 명령을 확인한다.
5. [TODO](todo.md)의 `M0`부터 체크하며 구현한다.
6. 중요한 결정은 [결정 기록](decisions.md)에 추가한다.
7. 구현 전에 [`../0.ref/README.md`](../0.ref/README.md)에서 기반 교재 참조 코드와 사용 경계를 확인한다.

현재 상태: 1.22.9. focused-v12 LR 2e-6/4e-6 25-step A/B를 각각 전체 390응답으로 평가했다. 4e-6 후보는 EOS 100%, unsafe 0, 유해 거절 93.75%로 안전 우선순위에서 이겼지만 정확도 28.46%, 멀티턴 6.67%, 정상 오거절 13.45%, loop 1건이라 아직 배포 불가다. 원 step 600에서 optimizer를 다시 초기화하는 4e-6→4e-7 최대 150-step 정식 학습을 다음으로 실행한다. 품질을 통과한 checkpoint만 HF·GGUF와 private Hub 후보가 된다.
