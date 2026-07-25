# Qwen3-14B QLoRA 실행

## 완료된 학습 산출물

100 step QLoRA 학습과 checkpoint-100 단독 heldout 재평가를 완료했다.

- adapter: `runs/qwen3-14b-qlora/checkpoint-100/adapter_model.safetensors`
- 학습 loss: `0.88898`
- heldout: 학습 중 `0.9439`, 단독 재평가 `0.94556` (100 samples)

위 수치는 토큰 수준 assistant-only loss다. 실제 대화 가능 여부는 별도의 생성 테스트에서 identity, 언어 일치, EOS, 반복, 안전, 수동 품질 게이트를 통과해야 한다.

이 경로는 기존 100M 모델의 tokenizer·trainer·CLI와 분리되어 있다. 입력은
`Qwen/Qwen3-14B`의 원본 Transformers safetensors이며 GGUF는 학습 입력으로
받지 않는다.

## 준비

```bash
uv pip install -r configs/qwen3-14b/requirements.txt
hf download Qwen/Qwen3-14B --local-dir ~/work/models/Qwen3-14B
```

`configs/qwen3-14b/qlora.yaml`의 `model_dir`를 실제 로컬 디렉터리로 바꾼다.
데이터는 기존 `ChatRow` JSONL 계약을 사용하며 train/heldout 라이선스와
final-user prompt 비누출을 preflight에서 다시 검사한다.

## 실행

```bash
python -m llmex.qwen3 check --config configs/qwen3-14b/qlora.yaml
python -m llmex.qwen3 fit --config configs/qwen3-14b/qlora.yaml
python -m llmex.qwen3 eval --config configs/qwen3-14b/qlora.yaml
```

`check`는 GPU에 모델을 올리지 않는다. 로컬 모델, safetensors shard,
tokenizer 파일, 데이터, 선택 의존성이 모두 확인된 뒤에만 `fit`을 실행한다.
학습은 Qwen 공식 chat template를 `enable_thinking=false`로 고정하고 system/user
및 assistant role prefix를 `-100`으로 마스킹해 assistant 본문과 종료 token에만
loss를 적용한다.

14B 4-bit 본체와 optimizer/activation을 함께 올려야 하므로 실제 필요 VRAM은
sequence length와 batch에 따라 달라진다. 먼저 `micro_batch_size: 1`,
`gradient_accumulation_steps: 16`으로 smoke run을 수행하고 OOM이면
`sequence_length`를 줄인다. adapter 산출물은 `output_dir`에 저장되며 원본
safetensors는 변경하지 않는다.
