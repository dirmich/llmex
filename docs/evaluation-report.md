# M5 평가 시스템 보고서

## 평가 계약

`llmex eval`은 M4 checkpoint와 학습 설정, M2 tokenizer·shard manifest를 함께 받는다. 설정·모델·corpus·tokenizer·shard fingerprint와 checkpoint SHA-256을 기록하며 하나라도 다르면 실행 전에 거부한다. tokenizer artifact checksum, special token ID, 실제 vocab 크기와 모델 vocab 크기도 엄격히 검증한다.

validation/test는 겹치지 않는 다음-token window로 평가한다. 합산 NLL에서 `loss = NLL/token`, token perplexity, `NLL/UTF-8 byte`, bits/byte, byte perplexity를 계산한다. 큰 NLL의 `exp` overflow만 방지하며 원 NLL은 그대로 보존한다.

고정 cloze schema v1은 문항 ID, `[MASK]` prompt, 정답과 provenance를 보존한다. 고정 생성 suite는 띄어쓰기, 조사·어미, 고유명사, 숫자·날짜 범주를 포함한다. 생성 결과에는 반복률, distinct-1/2, 엄격한 UTF-8 유효성, EOS 도달과 문맥 제한 종료를 기록한다.

corpus가 주어지면 평가 문자열과 생성문에 대해 train 본문 substring exact 검사와 정규화 문자 5-gram Jaccard near-match를 수행한다. canary 목록은 학습 단계에서 주입된 값이 없으면 빈 목록과 `미검출` 상태로 명시하며, 생성문의 긴 train match 결과를 별도 보존한다. 실제 공개 판단에는 사람이 canary와 고유 구절 목록을 승인해야 한다.

## 산출물

- `evaluation-report.json` / `.md`: 지표, cloze, 생성 품질, 오염·암기 결과
- `generation-report.json` / `.md`: sampling 설정, seed, token ID, 종료와 품질 지표
- `benchmark-report.json` / `.md`: latency, token/s, 가능한 CUDA peak allocation
- 각 보고서의 `.checksums.json`: 두 본문 파일의 SHA-256과 checksum manifest fingerprint

모든 JSON은 schema version, 입력 fingerprint와 자체 payload fingerprint를 가진다. Markdown과 JSON은 임시 파일 뒤 원자적으로 교체한다.
