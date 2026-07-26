# 사주 질의 실행 계약

llmex는 사주·만세력 질문을 받으면 먼저 계산에 필요한 정보를 확인한다. 다음 항목이 필요하다.

- 생년월일
- 출생 시각(시, 가능하면 분)
- 양력 또는 음력
- 성별

출생지는 시간대 확인을 위한 선택 정보다. 정보가 부족하면 답변에 `calculate_saju` 도구를 사용할 수 있다고 명시하고 누락 항목을 요청한다.

모든 정보가 있으면 모델의 자유 생성에 의존하지 않고 런타임 라우터가 다음과 같은 JSON을 만든다.

```json
{"arguments":{"calendar":"solar","day":1,"gender":"남","hour":9,"month":1,"year":1990},"tool":"calculate_saju"}
```

이 JSON은 사주 계산기(MCP)의 입력이며, 라우터가 사주 결과를 임의로 만들어내는 것은 아니다. 실제 계산 결과를 받은 뒤에만 설명을 생성한다. 원시 GGUF를 직접 `llama.cpp`로 호출하는 경우에는 이 런타임 계약 계층을 포함한 llmex 실행기를 사용해야 하며, GGUF 단독 자유 생성의 JSON 형식 준수는 보장하지 않는다.

검증 명령:

```bash
uv run pytest -q tests/test_g003_chat.py
uv run llmex sft generate --config configs/sft/qwen36mtp-v5-saju-nosystem-explicit-60.yaml \
  --checkpoint runs/sft-qwen36mtp-v5-saju-nosystem-explicit-60/checkpoints/latest.pt \
  --prompt '사주를 볼 수 있어?' --temperature 0
```
