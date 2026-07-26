# 정식 full latest 기반 100M 대화 후보

## 산출물

- checkpoint: `runs/sft-qwen36mtp-v5-full-latest-dialogue-memory-180/checkpoints/latest.pt`
- GGUF: `~/work/models/llmex/llmex-100m-full-latest-dialogue-memory-180-Q4_K_M.gguf`
- GGUF SHA-256: `2ba65de38119e83f2bf66eca351c29dbdabdc77882ae576a574ccb9d21cce056`

## llama.cpp

```bash
MODEL="$HOME/work/models/llmex/llmex-100m-full-latest-dialogue-memory-180-Q4_K_M.gguf"
/home/dirmich/work/llama.cpp/build-gpu/bin/llama-completion \
  -m "$MODEL" --jinja --single-turn -n 120 --temp 0 -p '사주를 볼 수 있어?'
```

실행 결과는 사주·만세력 계산을 도울 수 있다고 밝히고 생년월일, 출생 시각, 양력/음력, 성별을 요청한 뒤 `[end of text]`로 종료했다. 완전한 입력을 실제 계산하는 단계는 `calculate_saju` runtime dispatcher에 위임한다.

기억 대화는 runtime memory가 `마감일은`과 `마감일을` 조사를 모두 처리해 모델 fallback 없이 기억 확인 문장을 반환한다.
