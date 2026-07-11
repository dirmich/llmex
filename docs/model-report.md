# M3 decoder-only 모델 보고서

## 구현 계약

모델은 `int64[B,T]` token ID를 받아 `float[B,T,V]` logits와 선택적 shifted causal loss를 반환한다. 계산 순서는 token embedding, 반복 Pre-Norm decoder block, 최종 RMSNorm, embedding과 가중치를 공유하는 LM head다.

각 block은 다음 수식을 따른다.

```text
h' = h + Dropout(GQA(RMSNorm(h)))
h_out = h' + Dropout(W_down(SiLU(W_gate RMSNorm(h')) ⊙ W_up RMSNorm(h')))
```

- RMSNorm은 `x / sqrt(mean(x²) + eps)`를 float32로 계산한 뒤 입력 dtype으로 복원한다.
- RoPE는 head의 인접 좌표 쌍을 위치별 각도로 회전하며 position offset을 지원한다.
- GQA는 query head마다 KV head를 동일한 비율로 공유한다. `n_kv_heads == n_heads`이면 MHA와 같다.
- causal mask는 절대 query/key position으로 만들므로 전체 forward와 KV cache 증분 forward가 같은 규칙을 사용한다.
- 기본 attention은 PyTorch SDPA이며, 독립 eager 구현을 수치 기준으로 유지한다.
- loss는 `logits[:, :-1]`과 `targets[:, 1:]`의 cross entropy이며 padding은 `ignore_index`로 제외한다.

## 초기화와 파라미터

Linear/embedding 가중치는 평균 0, 설정 가능한 표준편차(기본 `0.02`)의 정규분포로 초기화한다. 각 block의 attention output projection과 SwiGLU down projection은 깊이에 따른 residual 누적을 완화하도록 `1 / sqrt(2L)`을 추가 적용한다. bias는 사용하지 않는다. LM head와 token embedding은 동일 `Parameter`를 공유하므로 파라미터 수에서 중복 집계하지 않는다.

`llmex model inspect --config configs/model/smoke.yaml`은 다음을 JSON artifact로 기록한다.

- resolved config와 작업 fingerprint
- 정확한 학습 가능 파라미터 수
- fp32 가중치 byte 수
- fp32 가중치·gradient·AdamW 상태를 합친 근사 학습 byte 수
- weight tying 확인값

이 추정치는 activation, allocator, kernel workspace와 CUDA context를 포함하지 않으므로 실제 peak memory를 대신하지 않는다.

## 생성과 KV cache

라이브러리 API의 `generate`는 greedy(`temperature=0`)와 temperature/top-k sampling, EOS 중단, seed가 지정된 PyTorch generator를 지원한다. 각 layer cache는 RoPE가 적용된 key와 value를 `[B,H_kv,T,D_head]`로 보존한다. cache 사용 여부에 따른 greedy 결과 parity를 테스트한다. PRD에서 KV cache는 v1.1 목표이므로 M3에서는 안정적인 내부 API로 제공하며 CLI 공개 계약은 M5에서 확정한다.

## 독립 구현과 검증

교재의 Ch 14–18, 27, 31 notebook과 attention/nano-GPT benchmark는 수식과 구성 요소를 확인하는 읽기 전용 참고 자료로만 사용했다. production 코드는 `0.ref`를 import하거나 복사하지 않고 typed 모듈로 독립 구현했다.

검증은 RMSNorm·RoPE 수식 tensor, GQA shape property, SDPA/eager parity, causal leakage 0, shifted loss, padding ignore, finite gradient, CPU forward/backward, weight tying, state dict round-trip, cached/uncached 생성 parity, 정확한 parameter count, 128문서 synthetic overfit과 CLI artifact 계약을 포함한다. 128문서 overfit은 데이터·trainer 성능 기준이 아니라 모델의 학습 가능성과 loss 감소를 확인하는 M3 gate다.
