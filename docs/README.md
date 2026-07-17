# LLMEX 문서

LLMEX는 《LLM을 만들기 위한 수학 기반 이론과 Python 실습》의 토크나이저, Transformer, 사전학습, nano-GPT 내용을 실제 한국어 Wikipedia 학습 프로젝트로 확장한다.

개발 시작 순서:

1. [실행 가이드](run-guide.md)에서 데이터 확보부터 학습·추론까지 실제 명령과 경로를 확인한다.
   대화 학습은 [한국어 대화 SFT 가이드](chat-sft.md)를 함께 확인한다.
2. [PRD](prd.md)에서 제품 목표와 완료 기준을 읽는다.
3. [구현 계획](plan.md)에서 아키텍처와 단계별 검증 명령을 확인한다.
4. [TODO](todo.md)의 `M0`부터 체크하며 구현한다.
5. 중요한 결정은 [결정 기록](decisions.md)에 추가한다.
6. 구현 전에 [`../0.ref/README.md`](../0.ref/README.md)에서 기반 교재 참조 코드와 사용 경계를 확인한다.

현재 상태: 1.5.3, M0–M7 로컬 계약, 전체 Wikipedia corpus/tokenizer와 100k baseline 학습을 완료했다. SFT 정밀도·gradient accumulation·고정 validation/best checkpoint·schema 2 완전 재개와 무결성 검사를 강화하고 base checkpoint provenance와 평가·생성 strict 검증을 결속했다. 동일한 split별 128 batch 평가에서 100k `latest`가 best보다 validation/test PPL, 평균 repetition, EOS 도달에서 모두 우세해 SFT 시작점으로 선택했다. 이 선택은 대화 품질 gate 통과를 뜻하지 않으며 teacher 10k pilot, 혼합 SFT, 대화/EOS/repetition/safety/manual gate와 GGUF/llama.cpp parity가 남아 있다. [한국어 대화 SFT 가이드](chat-sft.md), [M7 릴리스 체크리스트](release-checklist.md), [재현성 bundle](reproducibility.md), [acceptance matrix](acceptance-matrix.md)에 실행 계약과 외부 승인 경계를 기록한다.
