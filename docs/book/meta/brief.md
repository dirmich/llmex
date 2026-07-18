# 교재 brief

## 독자 약속

독자는 작은 한국어 decoder-only 모델 도구를 빈 Python 골격에서 모듈별로 만들고, 데이터 provenance부터 checkpoint 재개, teacher 증류, assistant-only SFT, 자동·수동 품질 gate와 공개 경계까지 설명하고 검증할 수 있게 된다.

## 범위

- 포함: 단일 노드 PyTorch, byte-level BPE, 100M급 decoder, offline fixture, localhost teacher, SFT, 품질 artifact
- 제외: 분산 학습 최적화, 상용 서비스 SLA, 법률 자문, 자동 production 승인
- private HF/GGUF 연구실: SHA 고정 변환 CLI와 기존 checkpoint parity를 제공하되 선택 모델 parity·공개 승인을 별도로 요구한다.

## 성공 기준

17장의 단계별 artifact 사슬, 18장의 capstone rubric과 19장의 57개 모듈 카드를 충족하고, 미실행·외부 승인·미구현 항목을 성공으로 표현하지 않는다.
