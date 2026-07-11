# LLMEX 문서

LLMEX는 《LLM을 만들기 위한 수학 기반 이론과 Python 실습》의 토크나이저, Transformer, 사전학습, nano-GPT 내용을 실제 한국어 Wikipedia 학습 프로젝트로 확장한다.

개발 시작 순서:

1. [PRD](prd.md)에서 제품 목표와 완료 기준을 읽는다.
2. [구현 계획](plan.md)에서 아키텍처와 단계별 검증 명령을 확인한다.
3. [TODO](todo.md)의 `M0`부터 체크하며 구현한다.
4. 중요한 결정은 [결정 기록](decisions.md)에 추가한다.
5. 구현 전에 [`../0.ref/README.md`](../0.ref/README.md)에서 기반 교재 참조 코드와 사용 경계를 확인한다.

현재 상태: M0–M3 구현 완료. 모델 수식·계약과 검증 범위는 [M3 모델 보고서](model-report.md), 실행 환경과 전체 검증 이력은 [환경](environment.md), [구현 이력](history.md)을 참고한다.
