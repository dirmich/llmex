# Qwen3 사주·만세력 tool 학습 결과

## 실행

```bash
uv run --with 'transformers==4.57.6' --with 'tokenizers==0.22.2' \
  --with 'peft==0.19.1' --with 'accelerate==1.14.0' \
  --with 'bitsandbytes==0.50.0' \
  python -m llmex.qwen3 fit --config configs/qwen3-14b/qlora-saju-tool.yaml
```

## 결과

- 모델: 로컬 Qwen3-14B safetensors 8 shard
- 학습: 100/100 step, 약 1시간 31분 1초
- train loss: `0.887926`
- 학습 중 held-out loss: `0.942531`
- adapter: `runs/qwen3-14b-qlora-saju-tool`
- 입력: 기존 한국어 대화 8,746행 + 사주 MCP tool 20행
- held-out: 기존 1,498행 + 사주 MCP tool 4행

이 loss는 tool 호출 형식의 학습 신호가 반영됐다는 지표이지, 모든 생년월일 계산의
정확성을 보증하지 않는다. 실제 계산은 계속 `saju-mcp` tool에 위임하고, adapter는
tool 이름·인자 JSON을 선택하는 역할로 사용한다. 독립 eval과 추론 결과를 확인한
뒤에만 모델 품질을 판단한다.

## 실제 추론 결과

`2001년 11월 3일 오후 2시 20분 남자입니다. 사주를 계산해줘.`를 입력한 결과,
한국어 응답과 언어 gate는 통과했지만 `calculate_saju` JSON 호출은 생성하지
않고 일반 안내문을 반환했다. 따라서 현재 adapter는 tool schema를 이해할 수 있는
학습 신호는 있으나 자동 tool 호출 품질은 미완료다. 다음 실험에서는 tool 예제를
충분히 oversampling하고, JSON 호출 여부를 별도 pass/fail gate로 평가해야 한다.
