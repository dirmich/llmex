# Qwen3-14B GGUF llama.cpp 테스트

정확한 12B 원본은 현재 `~/work/models`에 없으므로, 12B급 대체 후보로 이미 학습·병합된 Qwen3-14B를 사용한다. 이 모델은 14,768,307,200 파라미터이며 12B로 부르면 안 된다.

## 모델

```text
경로: ~/work/models/llmex/qwen3-14b-identity-saju-v2-Q4_K_M.gguf
크기: 약 8.4 GiB
SHA-256: ab0094d51b94dd2cae6139c5eecc6829aa447f81024ba9547f6efe9abb554292
```

## 실행

```bash
MODEL="$HOME/work/models/llmex/qwen3-14b-identity-saju-v2-Q4_K_M.gguf"
BIN="/home/dirmich/work/llama.cpp/build-gpu/bin/llama-completion"
"$BIN" -m "$MODEL" -ngl 99 -no-cnv -n 96 \
  --temp 0.2 --top-p 0.9 --repeat-penalty 1.15 --seed 42 --special \
  -p $'<|im_start|>system\n너는 Highmaru에서 만든 llmex다. Qwen3 기반으로 파인튜닝되었다. 질문 언어와 같은 언어로 간결하게 답한다.\n<|im_end|>\n<|im_start|>user\n안녕하세요. 넌 누구고 무엇을 도와줄 수 있어?\n<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
```

## 실제 결과

`안녕하세요! 저는 Highmaru에서 개발한 llmex입니다. Qwen3 모델을 기반으로 파인튜닝되어, 다양한 언어로의 번역, 대화 이해 및 생성 등 여러 작업에 사용될 수 있습니다.` 응답 후 `<|im_end|>`로 종료됐다.

llama.cpp GPU 초기화와 생성이 성공했으며, 생성 속도는 약 24 tokens/s였다. Hugging Face 업로드나 서명 gate는 수행하지 않았다.
