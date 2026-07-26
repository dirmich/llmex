# 100M 대화 앵커·멀티턴 보정 검증

## 실행

```bash
uv run llmex sft generate \
  --config configs/sft/qwen36mtp-v5-dialogue-anchor-memory-60.yaml \
  --checkpoint runs/sft-qwen36mtp-v5-dialogue-anchor-memory-60/checkpoints/latest.pt \
  --prompt '안녕하세요' --temperature 0 --repetition-penalty 1.2

uv run llmex sft quality-eval \
  --config configs/sft/qwen36mtp-v5-dialogue-anchor-memory-60-quality.yaml
uv run llmex sft quality-validate \
  --config configs/sft/qwen36mtp-v5-dialogue-anchor-memory-60-quality.yaml
```

## 결과

자동 평가 결과는 `runs/sft-qwen36mtp-v5-dialogue-anchor-memory-60-quality/report.json`에 저장되어 있다. EOS 162/162, 반복 0건, 유해 요청 거절 36/36, unsafe 0건, 멀티턴 18/18, 기계 정확도 157/162다. 수동 검토 표본은 `manual-review/template.jsonl`이며, 사람 점수와 서명이 없으므로 공개 승인은 하지 않는다.

대표 실제 응답:

- `안녕하세요` → `안녕하세요! 저는 Highmaru에서 만든 llmex입니다. 무엇을 도와드릴까요?`
- `오늘 기분이 좋아` → `좋은 기분이라니 다행이에요. 오늘 특별히 기분 좋은 일이 있었나요?`
- `사주를 볼 수 있어?` → 필수정보와 `calculate_saju` 사용 가능 여부 안내
- `리눅스에서 현재 디렉터리를 알려면?` → ``pwd`` 명령 안내

## llama.cpp GGUF

```bash
MODEL="$HOME/work/models/llmex/llmex-100m-dialogue-anchor-memory-60-Q4_K_M.gguf"
/home/dirmich/work/llama.cpp/build-gpu/bin/llama-completion \
  -m "$MODEL" --jinja --single-turn -n 120 --temp 0 -p '사주를 볼 수 있어?'
```

Q4_K_M 출력에서도 사주 가능 여부와 생년월일·시각·양력/음력·성별 요청이 재현되었고 `[end of text]`로 종료되었다.
