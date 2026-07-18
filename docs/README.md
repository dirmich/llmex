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

현재 상태: 1.22.2. Qwen/public+Gemma 한국어 curriculum을 검증했고, 두 teacher에 각각 train 900·heldout 180의 영어·일본어 대화·한↔영·한↔일 prompt inventory를 생성했다. teacher 간 exact prompt overlap은 0이며 다국어 품질 suite는 18 scenario·108응답이다. Qwen36mtp와 Gemma4에서 총 2,160개 label을 수집 중이며 완료 후 100M latest 기반 SFT에 함께 넣는다. [실행 가이드](run-guide.md), [한국어 대화 SFT 가이드](chat-sft.md), [teacher 증류 데이터 실행 가이드](teacher-distillation.md), [M7 릴리스 체크리스트](release-checklist.md)에 SHA·실행 결과와 외부 승인 경계를 기록한다.
