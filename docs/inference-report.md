# M5 추론 시스템 보고서

## 생성과 sampling

`llmex generate`는 빈 prompt와 모델 문맥보다 긴 prompt를 거부한다. `temperature=0`은 greedy이며, 양수이면 temperature scaling 뒤 top-k와 nucleus top-p를 순서대로 적용한다. seed가 고정된 장치별 `torch.Generator`를 사용하므로 같은 장치·checkpoint·설정의 token ID가 재현된다. repetition penalty는 이미 등장한 token의 양수 logit을 나누고 음수 logit을 곱하는 표준 sign-aware 방식이다.

배치별 EOS 상태를 추적하고 완료된 행은 EOS로 고정한다. 모든 행이 EOS에 도달하거나 `max_new_tokens`를 소진하거나 모델 `max_seq_len`에 닿으면 종료한다. 출력에는 실제 종료 사유를 판별할 수 있는 EOS/문맥 제한 flag가 포함된다.

## KV cache 정확성

첫 forward는 prompt 전체의 layer별 RoPE 적용 K/V를 보존한다. 이후에는 새 token만 projection하고 절대 position offset과 명시적 causal mask를 사용한다. cache layer 수, 누적 길이와 모델 문맥 상한을 매 호출 검증한다. CPU 테스트는 cache/no-cache의 다음-token logits를 수치 허용오차 내 비교하고 greedy 전체 생성 token ID를 완전 동일 비교한다.

## benchmark

`llmex benchmark`는 warm-up 뒤 여러 번 같은 생성 계약을 실행하고 평균 latency와 생성 token/s를 기록한다. CUDA에서는 각 구간을 synchronize하고 peak allocated memory를 초기화·측정한다. CPU에서는 peak CUDA memory를 `null`로 명시한다. 이 수치는 모델·prompt·생성 길이·cache 설정 fingerprint와 함께 비교해야 하며 서로 다른 입력의 절대 성능 비교에 사용하지 않는다.
