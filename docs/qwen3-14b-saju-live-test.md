# Qwen3-14B 사주 실추론 확인

모델: `~/work/models/llmex/qwen3-14b-identity-saju-v3-Q4_K_M.gguf`

```bash
MODEL="$HOME/work/models/llmex/qwen3-14b-identity-saju-v3-Q4_K_M.gguf"
BIN="/home/dirmich/work/llama.cpp/build-gpu/bin/llama-completion"
"$BIN" -m "$MODEL" -ngl 99 --jinja --single-turn --reasoning off \
  -n 256 --temp 0.2 --seed 42 \
  -sys '너는 Highmaru에서 만든 llmex다. 사주 질문에는 가능 여부를 말하고 생년월일, 출생 시각, 양력/음력, 성별을 요청한다.' \
  -p '사주를 볼 수 있어?'
```

2026-07-27 실행 결과: 사주를 볼 수 있다고 답하고 생년월일·양력/음력·출생 시각·성별을 요청했으며 `<\/think>` 뒤 자연어 답변과 `[end of text]` 종료를 확인했다. 실제 사주 계산은 응답을 `calculate_saju` dispatcher에 전달해야 하며 모델이 계산 결과를 임의로 만들지 않는다.
