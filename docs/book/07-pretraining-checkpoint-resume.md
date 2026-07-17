# 07. Causal 사전학습, trainer, checkpoint와 재개

## 학습 목표

- 결정적 sampler, AdamW, warmup+cosine, gradient accumulation을 구현한다.
- 모델뿐 아니라 optimizer·sampler·RNG를 완전 checkpoint한다.
- 안전 중단과 exact resume를 검증한다.

## 선행지식

역전파, AdamW와 학습률 schedule의 기초가 필요하다.

## 관련 실제 파일

- [trainer](../../src/llmex/train/engine.py), [dataset/sampler](../../src/llmex/train/data.py), [optimizer](../../src/llmex/train/optim.py)
- [runtime](../../src/llmex/train/runtime.py), [checkpoint](../../src/llmex/train/checkpoint.py)
- [학습 테스트](../../tests/test_m4_training.py), [교재 연결 설정](examples/pretrain-smoke.yaml), [baseline 설정](../../configs/training/baseline-100m.yaml)

## 핵심 개념과 수식

유효 batch token은 `micro_batch × accumulation × (sequence_length-1)`이다. warmup 뒤 cosine schedule은 다음과 같이 만들 수 있다.

\[
lr(s)=lr_{min}+\frac12(lr_{max}-lr_{min})(1+\cos(\pi p))
\]

여기서 `p`는 warmup 이후 진행 비율이다. 정확한 재개 조건은 model/optimizer/scaler/scheduler/sampler/RNG/step과 config·corpus·tokenizer·model·shards fingerprint가 모두 일치하는 것이다.

## 단계별 구현

1. memory-mapped shard에서 길이 `sequence_length+1` window를 만든다.
2. seed 기반 permutation·epoch·cursor를 가진 sampler를 구현한다.
3. bias/norm은 decay 제외, 나머지는 AdamW decay group으로 나눈다.
4. accumulation 동안 loss를 나누어 backward하고 마지막에 unscale·clip·step한다.
5. NaN/Inf loss·gradient를 `failure.json`과 함께 즉시 실패시킨다.
6. checkpoint bytes를 temp write→fsync→atomic replace하고 audit 때 immutable bytes의 SHA-256을 계산한다.
7. SIGTERM은 현재 accumulation 경계에서 latest checkpoint를 저장하고 종료한다.

```python
optimizer.zero_grad(set_to_none=True)
for _ in range(accumulation):
    loss = model(batch(), targets=tokens).loss
    scaler.scale(loss / accumulation).backward()
scaler.unscale_(optimizer)
clip_grad_norm_(model.parameters(), max_norm)
scaler.step(optimizer); scaler.update()
```

## 실제 명령

```bash
uv run llmex config validate docs/book/examples/pretrain-smoke.yaml --kind training
uv run llmex train smoke --config docs/book/examples/pretrain-smoke.yaml
uv run llmex train run --config docs/book/examples/pretrain-smoke.yaml
uv run llmex train resume --config docs/book/examples/pretrain-smoke.yaml --checkpoint runs/book-pretrain/checkpoints/latest.pt
uv run llmex train audit --config docs/book/examples/pretrain-smoke.yaml
uv run pytest -q tests/test_m4_training.py
```

이 설정은 04장의 smoke 전용 `artifacts/tokenizers/book-smoke-bpe/shards/manifest.json`을 직접 읽는다. 그 manifest는 세 split 모두 256-token window를 가지며 requested/actual vocab이 16,000으로 같은 결정적 smoke corpus에서 만들어져야 한다. production `artifacts/tokenizers/bpe-16k`나 stock `configs/training/smoke.yaml`과 섞지 않는다.

## 예상 산출물

`resolved-config.json`, `fingerprints.json`, `metrics.jsonl`, `checkpoints/latest.pt`, step checkpoint와 `best.pt`가 생긴다. 별도 checkpoint SHA sidecar는 만들지 않으며 `train audit`가 파일의 immutable bytes를 읽어 SHA-256을 계산한다. metrics에는 loss/lr/gradient norm/tokens/s/device/precision이 기록된다.

## 검증 테스트

- 연속 N step과 K step+resume의 model/optimizer/sampler/RNG가 같다.
- checkpoint byte/SHA 손상, schema·fingerprint·필수 상태 누락을 거부한다.
- malicious pickle은 `weights_only` 경계에서 실행되지 않는다.
- validation은 고정 sampler 상태를 보존하고 train cursor에 영향을 주지 않는다.

## 흔한 실패와 해결

- 모델 weight만 복원: Adam moment와 data 순서가 달라진다. 전체 상태를 필수화한다.
- accumulation 중간 저장: gradient state가 없으면 exact resume가 아니다. optimizer 경계에서만 저장한다.
- `max_steps` 변경 시 schedule 재계산: 기존 trajectory가 바뀐다. 원 horizon과 연장 정책을 checkpoint에 보존한다.

## 체크리스트

- [ ] 유효 batch/token 계산이 문서와 metric에 일치한다.
- [ ] NaN/Inf와 손상 checkpoint가 실패-폐쇄된다.
- [ ] exact resume 회귀가 통과한다.
- [ ] best/latest 선택 기준이 고정 validation loss다.

## 연습문제

1. sampler의 epoch/cursor 직렬화와 복원을 구현하라.
2. `micro_batch=2, accumulation=8, seq=1024`의 step당 target token을 계산하라.
3. SIGTERM을 보내고 latest checkpoint로 동일 결과를 재개하라.
