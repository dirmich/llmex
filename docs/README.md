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

현재 상태: 1.8.0. 비누출 mix와 실제 SFT preflight에 더해 `sft quality-preflight/eval/status/validate` 자동 품질 gate가 구현됐다. 이 gate는 SHA-256으로 고정한 SFT 설정·schema 2 checkpoint·MIT 한국어 suite의 읽은 snapshot bytes를 단일 원본으로 사용하고, 실제 멀티턴 대화와 greedy 1회·sampling 고정 seed 최소 5회를 평가한다. repository suite는 24개 scenario·27개 unique turn이며 canonical 설정은 162개 응답을 만든다. EOS/context limit/max token, target-token 가중 heldout NLL/PPL, 정확도·거부·오거부·PII·secret·Unicode·distinct·3회 연속 n-gram loop를 category/profile/seed 최악값으로 판정한다. 자동 artifact는 lock·staging·manifest-last 원자 publish 후 현재 입력에서 다시 유도해 검증한다. 정식 qwen36mtp v5 수집은 진행 중이며 수동 품질 검토 gate는 1.8.1 후속 작업이다. [실행 가이드](run-guide.md), [한국어 대화 SFT 가이드](chat-sft.md), [teacher 증류 데이터 실행 가이드](teacher-distillation.md), [M7 릴리스 체크리스트](release-checklist.md)에 실행 계약과 외부 승인 경계를 기록한다.
