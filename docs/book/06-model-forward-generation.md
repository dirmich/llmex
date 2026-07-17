# 06. CausalLM 조립, forward와 generation

## 학습 목표

- embedding, decoder blocks, final norm, tied LM head를 조립한다.
- shifted causal cross-entropy를 구현한다.
- greedy/sampling, repetition penalty와 KV cache 생성을 검증한다.

## 선행지식

[05장](05-transformer-components-math.md), categorical sampling과 cross-entropy가 필요하다.

## 관련 실제 파일

- [CausalLM](../../src/llmex/model/lm.py), [모델 공개 API](../../src/llmex/model/__init__.py)
- [추론 runtime](../../src/llmex/inference/runtime.py), [평가 생성](../../src/llmex/evaluation/runner.py)
- [모델 테스트](../../tests/test_m3_model.py), [평가 테스트](../../tests/test_m5_evaluation.py)

## 핵심 개념과 수식

입력 token `x_0...x_{T-1}`에서 위치 `t` logits는 다음 token `x_{t+1}`을 예측한다.

\[
L=-\frac1{T-1}\sum_{t=0}^{T-2}\log softmax(z_t)_{x_{t+1}}
\]

embedding과 LM head weight tying은 같은 행렬 `E`를 입력 lookup과 `hE^T` 출력에 쓴다. sampling은 temperature로 logits를 나누고 top-k/top-p를 적용한다. temperature 0은 argmax다.

## 단계별 구현

1. token embedding 후 N개 block과 final RMSNorm을 통과시킨다.
2. LM head bias 없이 projection하고 embedding weight를 공유한다.
3. targets가 있으면 `logits[:,:-1]`과 `targets[:,1:]`의 cross-entropy를 계산한다.
4. 생성 첫 호출은 전체 prompt, 이후 cache가 있으면 마지막 token만 입력한다.
5. repetition penalty, top-k, nucleus mask 후 명시적 `torch.Generator`로 sample한다.
6. EOS 또는 `max_new_tokens`/`max_seq_len`에서 중단한다.

```python
for _ in range(limit):
    out = model(current, caches=caches, use_cache=True)
    logits = out.logits[:, -1] / temperature
    next_id = logits.argmax(-1) if temperature == 0 else sample(logits, generator)
    tokens = torch.cat((tokens, next_id[:, None]), dim=1)
    if eos_id is not None and bool((next_id == eos_id).all()):
        break
    current, caches = next_id[:, None], out.caches
```

## 실제 명령

```bash
uv run llmex model inspect --config configs/model/smoke.yaml
uv run llmex config validate docs/book/examples/evaluation-smoke.yaml --kind evaluation
uv run llmex generate --config docs/book/examples/evaluation-smoke.yaml --prompt '대한민국의 수도는'
uv run pytest -q tests/test_m3_model.py tests/test_m5_evaluation.py
```

generation 명령은 07장의 `runs/book-pretrain/checkpoints/best.pt`가 생긴 뒤 실행한다. 모델 forward만 먼저 확인할 때는 첫 `model inspect`와 테스트까지만 실행한다.

## 예상 산출물

forward는 `[batch, sequence, vocab]` logits와 선택적 scalar loss/cache를 반환한다. generation artifact에는 prompt·token IDs·decoded text·EOS/context/repetition/distinct와 fingerprint가 기록된다.

## 검증 테스트

- tied weight가 같은 storage/parameter인지 확인한다.
- 수동 shifted CE와 model loss가 같다.
- greedy는 반복 실행이 동일하고 sampling은 같은 seed에서 동일하다.
- cache/no-cache token IDs가 같다.
- max context 초과와 빈 prompt를 거부한다.

## 흔한 실패와 해결

- target shift 누락: 현재 token을 그대로 복사하는 trivial loss가 된다.
- cache 사용 중 전체 prompt 재입력: K/V가 중복된다. 이후에는 마지막 token만 넣는다.
- global RNG 의존: 평가 순서에 따라 출력이 바뀐다. 별도 generator를 전달한다.

## 체크리스트

- [ ] logits/loss/cache shape가 명시됐다.
- [ ] shifted loss와 weight tying이 검증됐다.
- [ ] sampling seed와 cache parity가 고정됐다.
- [ ] EOS/max/context 종료를 구분한다.

## 연습문제

1. top-p 0.9의 후보 선택 알고리즘을 구현하라.
2. repetition penalty를 양/음 logits에 다르게 적용해야 하는 이유를 조사하라.
3. cache 사용 전후 token당 latency를 측정하라.
