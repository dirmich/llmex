# Qwen3-14B identity·사주 v2 로컬 테스트 기록

실행일: 2026-07-26 17:00 (KST)

## 산출물

- 학습: `runs/qwen3-14b-qlora-identity-saju-v2` (100 step, checkpoint-25/50/75/100)
- 병합: `dist/qwen3-14b-identity-saju-v2-merged`
- GGUF: `~/work/models/llmex/qwen3-14b-identity-saju-v2-Q4_K_M.gguf`
- SHA-256: `ab0094d51b94dd2cae6139c5eecc6829aa447f81024ba9547f6efe9abb554292`
- 파라미터: 14,768,307,200

## 학습 결과

| 항목 | 결과 |
|---|---:|
| global step | 100 |
| train runtime | 2,835.854초 |
| train loss | 0.948624 |
| eval loss | 1.266257 |

## 재현 명령

```bash
MODEL="$HOME/work/models/llmex/qwen3-14b-identity-saju-v2-Q4_K_M.gguf"
BIN="/home/dirmich/work/llama.cpp/build-gpu/bin/llama-completion"
"$BIN" -m "$MODEL" -ngl 99 -no-cnv -n 80 --temp 0 --repeat-penalty 1.2 --seed 0 --special
```

## 게이트 결과

- identity: 통과. `내 이름은 LLMEX이며, ... Highmaru ... Qwen3 ...` 응답을 생성했다.
- 사주 도구 호출: 실패. 동일한 학습 system/user 형식에서 모델이 사고문을 생성하거나 JSON 인자만 출력하고 `"tool": "calculate_saju"`를 생성하지 않았다. 따라서 실제 MCP 연결 가능한 도구 사용 모델이라고 판정하지 않는다.
- 결론: GGUF 변환·로컬 실행·identity는 검증했지만, 사주 도구 호출을 포함한 최종 대화 품질 게이트는 미달이다. 다음 학습에서는 도구 호출 전용 샘플을 더 늘리고 `<think>` 억제 및 정확한 tool-call 출력 형식을 고정해야 한다.
