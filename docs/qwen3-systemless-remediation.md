# Qwen3-14B 무시스템 identity·tool 보정

## 재현된 문제

기존 `qwen3-14b-identity-saju-v2-Q4_K_M.gguf`에 system turn 없이
`누가 너를 만들었어?`를 입력하면 자신을 llmex로 밝히지 않고
`알리바바 그룹 ... 개발되었습니다`라고 답했다. 기존 smoke는 identity system prompt를
항상 넣었기 때문에 이 실패를 검출하지 못했다.

## v3 학습 split

`scripts/build_qwen3_identity_saju_augmented.py`는 다음 신호를 결합한다.

- 일반 대화 replay 8,746행을 그대로 유지한다.
- 사주 tool 20행을 50회는 기존 system turn과 함께, 50회는 system turn 없이 넣는다.
- 단순 5행 반복 대신 한국어 256행, 영어 36행, 일본어 16행의 서로 다른 identity
  질문을 사용한다. Qwen3는 기반 모델이고 llmex의 제작자는 Highmaru라는 구분을
  긍정 질문과 Qwen·Alibaba 오인 교정 질문에 함께 학습한다.
- identity train은 308행으로 전체 11,054행의 약 2.79%다.
- identity 12행과 사주 8행을 train과 문장이 겹치지 않는 heldout으로 둔다.

```bash
uv run python scripts/build_qwen3_identity_saju_augmented.py
uv run python -m llmex.qwen3 check \
  --config configs/qwen3-14b/qlora-identity-saju-v3.yaml
uv run python -m llmex.qwen3 fit \
  --config configs/qwen3-14b/qlora-identity-saju-v3.yaml
```

기존과 같은 일반 대화·사주 replay 총량과 낮은 `1e-5` learning rate를 유지한다.
따라서 identity-only 학습으로 일반 행동을 덮어쓰는 실험이 아니다.

## GGUF 승격 gate

병합·Q4_K_M 변환 뒤 다음 gate를 실행한다. 세 입력 모두 system turn이 없으며,
identity 두 문항은 `llmex`와 `Highmaru`를 모두 요구하고 사주 문항은 설명문이 아닌
`calculate_saju` JSON tool call을 요구한다.

```bash
uv run python scripts/check_qwen3_gguf_contract.py \
  --model ~/work/models/llmex/qwen3-14b-identity-saju-v3-Q4_K_M.gguf \
  --llama-completion /home/dirmich/work/llama.cpp/build-gpu/bin/llama-completion
```

현재 v2 GGUF는 이 gate의 identity 조건을 통과하지 못한다. v3는 실제 학습·병합·양자화
후 이 gate가 모두 통과하기 전까지 승격하지 않는다. 이 변경은 모델 업로드, 릴리스 승인,
서명 또는 서명 대체물을 만들지 않는다.
