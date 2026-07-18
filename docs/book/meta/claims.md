# 검증 가능한 주장 원장

| 주장 | 권위 증거 | 갱신 조건 |
|---|---|---|
| 패키지 버전 | `pyproject.toml`, `src/llmex/__init__.py`, `uv.lock` | 버전 bump |
| Python 모듈은 57개이며 모두 학습 카드가 있다 | `find src/llmex -name '*.py'`, 16장 표, `tests/test_book.py` | 파일 추가·삭제 |
| 100M 모델 고유 parameter는 87,804,672개다 | model inspect와 baseline report | model config 변경 |
| 100k base pretraining이 완료됐다 | checkpoint audit와 training report | checkpoint 교체 |
| teacher 10k 수집 상태 | `llmex distill status` artifact | 수집 진행·export |
| public+teacher full mix/SFT 품질 | 최종 mix manifest, SFT checkpoint, quality artifact | 새 정식 실행 |
| GGUF/llama.cpp parity | private HF/GGUF CLI와 기존 checkpoint F16 greedy parity 구현 | 선택 checkpoint의 HF logits·llama.cpp EOS parity와 공개 승인 |
| production 수동·법무·공개 승인 | 독립 서명 evidence | 실제 issuer provisioning·승인 |

진행 중 수치는 본문에 고정 완료값처럼 쓰지 않는다. 완료 뒤 exact command, timestamp, input/config/output SHA를 이 원장과 실행 보고서에 함께 추가한다.
