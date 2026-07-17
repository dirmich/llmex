# 05. Transformer 구성요소와 수학

## 학습 목표

- RMSNorm, RoPE, causal GQA, SwiGLU와 Pre-Norm residual을 직접 구현한다.
- tensor shape와 causal mask 불변식을 추적한다.
- eager attention과 SDPA 결과를 비교한다.

## 선행지식

행렬곱, softmax, 평균·분산, PyTorch tensor broadcasting이 필요하다.

## 관련 실제 파일

- [RMSNorm](../../src/llmex/model/norm.py), [RoPE](../../src/llmex/model/rope.py), [GQA](../../src/llmex/model/attention.py), [block](../../src/llmex/model/block.py)
- [모델 테스트](../../tests/test_m3_model.py), [모델 보고서](../model-report.md), [모델 설정](../../configs/model/smoke.yaml)

## 핵심 개념과 수식

RMSNorm은 평균을 빼지 않고 root mean square로 scale한다.

\[
RMSNorm(x)=g\odot\frac{x}{\sqrt{\frac1d\sum_i x_i^2+\epsilon}}
\]

attention은 `QK^T/√d_h`에 미래 위치 mask를 적용한다. GQA는 `h_q` query head가 `h_{kv}` key/value head를 공유하며 `h_q % h_{kv}=0`이어야 한다.

\[
Attention(Q,K,V)=softmax(M+QK^T/\sqrt{d_h})V
\]

RoPE는 위치 `p`마다 인접 좌표쌍을 각도 `p\theta_i`로 회전한다. SwiGLU는 `down(silu(gate(x)) ⊙ up(x))`다. Pre-Norm block은 `x + Attn(Norm(x))`, 이어서 `x + FFN(Norm(x))`이다.

## 단계별 구현

1. RMS 통계는 float32로 계산하고 원 입력 dtype으로 돌린다.
2. RoPE inverse frequency를 buffer로 두고 device/dtype별 cos/sin cache를 만든다.
3. Q는 `[B,h_q,T,d_h]`, K/V는 `[B,h_kv,T,d_h]`로 reshape한다.
4. K/V head를 group 수만큼 반복한 뒤 위치 `key <= query` mask를 적용한다.
5. eager와 `scaled_dot_product_attention` 두 경로를 제공한다.
6. residual dropout은 block 출력 경계에서만 적용한다.

```python
scores = q @ k.transpose(-2, -1) / math.sqrt(head_dim)
allowed = key_positions[None, :] <= query_positions[:, None]
scores = scores.masked_fill(~allowed, torch.finfo(scores.dtype).min)
out = scores.float().softmax(-1).to(q.dtype) @ v
```

## 실제 명령

```bash
uv run llmex model inspect --config configs/model/smoke.yaml
uv run pytest -q tests/test_m3_model.py
```

## 예상 산출물

각 모듈이 입력과 같은 batch/sequence 차원을 유지하고, inspect 결과에 고유 파라미터 수와 tensor shape가 나온다.

## 검증 테스트

- RMSNorm을 수식 reference와 비교한다.
- RoPE offset cache가 full sequence 계산의 slice와 같다.
- 미래 token을 바꿔도 과거 logits가 변하지 않는다.
- eager/SDPA forward·gradient가 허용 오차 안에서 같다.
- `n_heads == n_kv_heads`일 때 GQA가 MHA 특수 경우가 된다.

## 흔한 실패와 해결

- bool mask 방향 반전: 미래 정보가 누출된다. 작은 3×3 허용 행렬을 golden으로 고정한다.
- KV cache에서 RoPE offset 0 재사용: cached 생성이 full 생성과 달라진다. `past_length`를 offset으로 쓴다.
- fp16 norm overflow: 통계를 float32로 계산한다.

## 체크리스트

- [ ] 모든 tensor shape를 종이에 추적할 수 있다.
- [ ] causal leakage 테스트가 있다.
- [ ] eager/SDPA·cache/no-cache parity가 통과한다.
- [ ] invalid head/RoPE 범위를 즉시 거부한다.

## 연습문제

1. `d_model=256, h_q=8, h_kv=2`의 모든 Q/K/V shape를 계산하라.
2. Post-Norm과 Pre-Norm의 식을 비교하고 코드 순서를 바꿔라.
3. RoPE theta 변화가 긴 위치의 각도에 미치는 영향을 그려라.
