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

현재 상태: 1.22.13. focused-v12 step 150은 실제 자유대화 비문으로 기각했고, 이어진 expanded 1차 수집도 source 문형과 split·teacher 의미 누출 결함 때문에 export 없이 중단했다. `prompt_index` 전단사 순열로 의미 조합 범위를 분리한 natural-v3 다국어와 natural-v2 한국어 source를 다시 생성해 Qwen/Gemma 다국어 각 2,000, Gemma 한국어 3,000 inventory의 고유 request·canonical 본문 교집합 0·모든 의미 축의 양 split 분포·Wikipedia 보충 0·endpoint preflight를 확인했다. 다음 단계는 새 source의 collect→export→validate→mix→100M latest SFT→390응답과 suite 밖 smoke다.
