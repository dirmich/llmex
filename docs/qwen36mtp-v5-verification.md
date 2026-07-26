# qwen36mtp v5 정식 데이터·100M SFT 검증 기록

`data/chat/ko-public-qwen-natural-v5-10k/manifest.json`은 공개 데이터와
qwen36mtp teacher export를 결합한 검증된 split이다. train 12,606행,
held-out 2,722행, prompt overlap 0이며 CarrotAI 공개 4,979행, teacher
3,860행, koWiki 3,767행으로 구성된다.

100M latest 기반 SFT는 `configs/sft/qwen36mtp-v5-full.yaml`으로 410 step
완료했으며 결과는 `runs/sft-qwen36mtp-v5-full/checkpoints/latest.pt`이다.
held-out assistant NLL은 1.375728, PPL은 3.957958이다.

고정 162응답 자동 gate는 EOS 100%, hard n-gram loop 0건, harmful refusal
100%, benign false refusal 0%, multi-turn retention 100%, machine correctness
100%를 기록했다. 수동 release 승격은 독립 reviewer 점수·서명이 필요한 별도
gate이며 임의 서명을 만들지 않았다.
