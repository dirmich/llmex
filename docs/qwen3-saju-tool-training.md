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

## Q4 GGUF 로컬 변환 및 실행

adapter 병합부터 GGUF 양자화까지 다음 순서로 실행한다.

```bash
uv run --with 'transformers==4.57.6' --with 'tokenizers==0.22.2' \
  --with 'peft==0.19.1' --with 'accelerate==1.14.0' --with 'bitsandbytes==0.50.0' \
  python scripts/merge_qwen3_lora.py --base ~/work/models/Qwen3-14B \
  --adapter runs/qwen3-14b-qlora-saju-tool --output dist/qwen3-14b-saju-merged
uv run --with 'transformers==4.57.6' --with 'tokenizers==0.22.2' --with sentencepiece \
  python /home/dirmich/work/llama.cpp/convert_hf_to_gguf.py \
  dist/qwen3-14b-saju-merged --outfile dist/qwen3-14b-saju-f16.gguf --outtype f16
/home/dirmich/work/llama.cpp/build-gpu/bin/llama-quantize \
  dist/qwen3-14b-saju-f16.gguf dist/qwen3-14b-saju-Q4_K_M.gguf Q4_K_M
mkdir -p ~/work/models/llmex && cp dist/qwen3-14b-saju-Q4_K_M.gguf ~/work/models/llmex/
```

생성 파일은 `~/work/models/llmex/qwen3-14b-saju-Q4_K_M.gguf`(약 8.4GiB)이며,
SHA-256은 `58a4558193a1aa817fed204d7bce228df415be5cd4b77294ac9a843b0ddb0539`다.
CUDA `llama-completion` smoke에서 `대한민국의 수도는 서울입니다.`를 확인했다.
이 산출물은 로컬 검증용이고 Hugging Face에는 업로드하지 않는다.
