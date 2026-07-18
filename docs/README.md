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

현재 상태: 1.22.22. `natural-v5`는 기존 natural-v3/v4 bytes를 보존하고 동사 활용·보수적 장소 동의어·ASCII 단어 경계를 새 계약에만 추가했다. teacher별 6,000개 fresh prompt는 모두 고유하고 과거 source와 prompt가 겹치지 않는다. Qwen v4 inventory는 train 1,466/heldout 534, Gemma v4는 train 1,488/heldout 512이며 두 endpoint preflight가 통과했다. 다음 단계는 Qwen v4 수집·조기 여섯 task 분포 감사→독립 표본 감사→Gemma 한국어 v3와 Gemma 다국어 v4 순차 수집→승인 export/validate→비누출 mix→100M latest SFT→390응답과 suite 밖 smoke→로컬 HF/GGUF·llama.cpp 검증이다. Hugging Face에는 공개·비공개 모두 업로드하지 않는다.
