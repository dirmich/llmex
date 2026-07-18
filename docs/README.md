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

현재 상태: 1.22.20. `natural-v4`가 질문·제안 행위를 품질 fingerprint에 결속하고 불안정한 비반복 지시를 제거했다. Qwen·Gemma source는 각각 6,000개 고유 prompt, split 간 prompt overlap 0이며 manifest fingerprint는 `438c1e6264f73ba80c876994b214b1fa0cd48dc7ebb52fc698bffcbb812ca03c`다. 두 fresh 2,000건 inventory도 prepare와 실제 endpoint preflight를 통과했다. 다음 단계는 Qwen v3 수집·독립 감사→Gemma 한국어 v3 수집·감사→Gemma 다국어 v3 순차 수집·감사→승인 export/validate→비누출 mix→100M latest SFT→390응답과 suite 밖 smoke→로컬 HF/GGUF·llama.cpp 검증이다. Hugging Face에는 공개·비공개 모두 업로드하지 않는다.
