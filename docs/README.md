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

현재 상태: 1.19.0. 인사·일상 대화와 실시간 정보·근거의 미제공/제공 대조를 만드는 focused-v10을 구현했다. 생성 4,800/480행과 replay 6,000/600행을 합친 train 10,800/heldout 1,080행의 SHA는 `57e934ed…a976`·`01c9ba11…9076`, manifest fingerprint는 `f40fe0a0…ac20`이며 suite·split·source overlap은 0이다. 다음 단계는 v9 step 2 기반 저학습률 SFT와 고정 자동 gate·별도 자유대화 smoke 재검증이다. 내부 teacher checkpoint를 base로 한 모든 후속 SFT는 원 release block을 계승한다. [실행 가이드](run-guide.md), [한국어 대화 SFT 가이드](chat-sft.md), [teacher 증류 데이터 실행 가이드](teacher-distillation.md), [M7 릴리스 체크리스트](release-checklist.md)에 SHA·실행 결과와 외부 승인 경계를 기록한다.
