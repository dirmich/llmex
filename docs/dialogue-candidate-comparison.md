# 100M 대화 후보 비교

| 후보 | 자동 게이트 | 인사 | 능력 표현 변형 | 사주 | 판정 |
|---|---:|---|---|---|---|
| `dialogue-anchor-memory-60` | 통과 | 자연스러움 | 일부 미학습 | 필수정보 안내 | 유지 |
| `dialogue-variants-40` | 통과 | 부자연스러움 | 개선 | 필수정보 안내 | 제외 |

자동 평가는 EOS·반복·안전·기계 정확도를 보장하지만, 위 표처럼 일반 대화의 자연스러움 회귀를 놓칠 수 있다. 따라서 `runs/sft-qwen36mtp-v5-dialogue-anchor-memory-60/checkpoints/latest.pt`를 현재 100M 실사용 후보로 보존하고, 수동 reviewer가 템플릿을 채우기 전까지 release gate는 차단한다.
