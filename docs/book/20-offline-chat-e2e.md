# 20장. 네트워크 없이 대화 학습 전체 경로 실행하기

09~13장의 개별 계약을 하나의 작은 CPU 실습으로 연결한다. 이 실습은 교재가 작성한 공개·teacher fixture를 생성하고, 공개+teacher 혼합, assistant-only SFT, 실제 추론, 자동 품질 평가와 재검증을 순서대로 실행한다. teacher HTTP 호출과 외부 수동 서명은 사용하지 않는다.

## 학습 목표

- 네 입력 split과 teacher manifest가 mix config에 어떻게 결속되는지 확인한다.
- 작은 random-init 모델을 실제로 학습하고 checkpoint에서 한국어 응답을 생성한다.
- checkpoint·SFT config·suite SHA를 고정한 뒤 품질 artifact를 재검증한다.
- 기능 smoke와 대화 품질·공개 승인의 차이를 설명한다.

## 환경 설정

[환경 프로필 부록](environment-profiles.md)의 CPU 교재 프로필을 사용한다.

```bash
uv sync --frozen
uv run python -VV
uv run pytest -q tests/test_sft_mixer.py tests/test_g003_chat.py tests/test_sft_quality.py
```

실습은 `data/book/chat-smoke`, `artifacts/book/chat-smoke`, `runs/book-chat-smoke`만 사용한다. 기존 정식 학습 경로와 teacher server를 건드리지 않는다. 처음부터 다시 할 때는 이 세 교재 경로만 별도 보관하거나 제거한다.

## 1단계. Fixture와 동적 설정 만들기

```bash
uv run python docs/book/examples/build-chat-smoke-fixtures.py
```

스크립트는 다음을 결정적으로 만든다.

```text
data/book/chat-smoke/
  public-{train,heldout}.jsonl
  teacher-{train,heldout}.jsonl
  teacher-manifest.json
artifacts/book/chat-smoke/tokenizer/
  tokenizer.json
  tokenizer-manifest.json
runs/book-chat-smoke/configs/
  mix.yaml
  sft.yaml
```

각 ChatRow의 `sha256`은 id, messages, provenance, split의 canonical fingerprint다. teacher manifest는 teacher train/heldout 파일 SHA와 내부 전용 라이선스, `redistribution_allowed=false`, `release_gate=blocked`를 가진다. 스크립트를 다시 실행했을 때 출력 SHA가 같아야 한다.

## 2단계. 공개+teacher 혼합

```bash
uv run llmex config validate runs/book-chat-smoke/configs/mix.yaml --kind sft-mix
uv run llmex sft preflight-mix --config runs/book-chat-smoke/configs/mix.yaml
uv run llmex sft prepare-mix --config runs/book-chat-smoke/configs/mix.yaml
uv run llmex sft status-mix --config runs/book-chat-smoke/configs/mix.yaml
uv run llmex sft validate-mix --config runs/book-chat-smoke/configs/mix.yaml
```

`data/book/chat-smoke/mixed/manifest.json`에서 다음을 직접 확인한다.

- public/teacher 네 입력과 teacher manifest SHA가 기록됨
- train과 heldout의 final-user prompt overlap이 0
- provenance source overlap이 0
- 내부 teacher release block이 혼합 결과에 계승됨
- `train.jsonl`, `heldout.jsonl`의 실제 SHA가 manifest와 일치함

한 글자를 바꾼 복사본으로 `validate-mix`가 실패하는지 별도 임시 경로에서 실험한다. 원 산출물을 직접 고쳐 통과시키지 않는다.

## 3단계. Assistant-only SFT

```bash
uv run llmex config validate runs/book-chat-smoke/configs/sft.yaml --kind sft
uv run llmex sft preflight --config runs/book-chat-smoke/configs/sft.yaml --measure-baseline
uv run llmex sft train --config runs/book-chat-smoke/configs/sft.yaml
uv run llmex sft eval \
  --config runs/book-chat-smoke/configs/sft.yaml \
  --checkpoint runs/book-chat-smoke/sft/checkpoints/latest.pt
```

이 설정은 CPU fp32, 1-layer, 12 optimizer step이다. 목적은 품질이 아니라 실제 tokenization, assistant label mask, backward, validation, checkpoint 게시가 연결되는지 확인하는 것이다. 학습 log에서 전체 sequence 수가 아니라 assistant target token 수로 loss가 가중되는지 코드와 함께 추적한다.

## 4단계. 실제 한국어 추론

```bash
uv run llmex sft generate \
  --config runs/book-chat-smoke/configs/sft.yaml \
  --checkpoint runs/book-chat-smoke/sft/checkpoints/latest.pt \
  --prompt "대한민국의 수도는 어디인가요?"
```

JSON 결과에서 `response`, 생성 token 수, EOS/최대 길이 종료 이유, 반복 지표를 기록한다. tiny random-init 12-step 모델이 정답을 내지 못해도 실행 계약은 통과할 수 있다. 그 결과를 “대화 가능” 또는 “품질 gate 통과”로 기록하지 않는다.

## 5단계. Checkpoint에 결속된 품질 설정 만들기

checkpoint bytes가 생긴 뒤에만 SHA를 계산해 quality 설정을 만든다.

```bash
uv run python docs/book/examples/build-chat-smoke-fixtures.py \
  --quality-checkpoint runs/book-chat-smoke/sft/checkpoints/latest.pt
uv run llmex config validate runs/book-chat-smoke/configs/quality.yaml --kind sft-quality
```

생성된 `quality.yaml`은 SFT config, checkpoint, 세 시나리오 suite의 SHA-256을 고정한다. checkpoint를 다시 학습했으면 quality 설정도 다시 만들어야 한다.

## 6단계. 자동 품질 평가와 재검증

```bash
uv run llmex sft quality-preflight --config runs/book-chat-smoke/configs/quality.yaml
uv run llmex sft quality-eval --config runs/book-chat-smoke/configs/quality.yaml
uv run llmex sft quality-status --config runs/book-chat-smoke/configs/quality.yaml
uv run llmex sft quality-validate --config runs/book-chat-smoke/configs/quality.yaml
```

교재 suite는 사실 질문, 민감 개인 식별번호 생성 거절, 두 turn 기억 시나리오를 greedy+고정 sampling seed로 실행한다. 기본 production 임계값은 완화하지 않으므로 tiny 모델의 자동 gate는 실패할 수 있다. `quality-validate`는 평가를 통과시킨다는 뜻이 아니라, 실패 결과까지도 고정 입력에서 변조 없이 재유도된 artifact인지 검증한다.

## 7단계. 모듈별로 다시 만들기

| 순서 | 직접 구현할 모듈 | 관찰할 산출물 |
|---:|---|---|
| 1 | `chat/data.py` | ChatRow schema·행 SHA·split/license 실패 |
| 2 | `chat/template.py` | assistant와 EOS만 남은 label |
| 3 | `chat/mixer.py` | preflight material·overlap 0·manifest |
| 4 | `chat/runtime.py` | 연속 token cache·target-token weighted loss |
| 5 | `train/checkpoint.py` | latest/best, RNG·optimizer·sampler state |
| 6 | `chat/quality.py` | 실제 multi-profile rollout·gate·재검증 |
| 7 | `chat/quality_review.py` | 자동 통과 뒤에만 만드는 blind template |

각 모듈은 [대화와 증류 모듈 카드](modules/04-chat-and-distillation.md)와 [학습·추론 모듈 카드](modules/03-training-inference-evaluation.md)의 실패 테스트를 먼저 작성한 뒤 이 E2E에 연결한다.

## 저장소 실측 기록

2026-07-18에 위 명령을 처음부터 실제 실행했다. mix는 train 8/heldout 4, fingerprint `0b6f1ab6…7d04`였고 prompt/source overlap은 0이었다. CPU fp32 12-step은 baseline PPL 411.3787에서 heldout PPL 75.6903으로 낮아졌다. latest checkpoint SHA는 `4b8a662b…492c`다.

수도 prompt의 생성은 즉시 EOS로 끝나 응답이 비었다. 3 scenario·4 turn·24 response 자동 품질 fingerprint는 `7eb2cd66…f08d`, `gate_passed=false`였고 byte 재유도는 통과했다. 이 결과는 교재 명령이 실행된다는 증거이며 대화 가능한 모델의 증거가 아니다.

## 실패 주입 실습

1. public heldout prompt를 public train에도 넣고 mix preflight가 누출을 거부하는지 확인한다.
2. teacher manifest의 train SHA 한 글자를 바꾸고 prepare가 중단되는지 확인한다.
3. SFT YAML의 vocab size를 tokenizer 실제 값과 다르게 바꾸고 preflight가 실패하는지 확인한다.
4. checkpoint 한 byte를 바꾼 복사본을 quality config에 연결하고 SHA 결속 실패를 확인한다.
5. quality output JSON을 편집하고 `quality-validate`가 byte 재유도 불일치를 검출하는지 확인한다.

## 완료 기준

- [ ] fixture 생성기를 두 번 실행해 동일한 입력 SHA를 얻었다.
- [ ] mix preflight/prepare/status/validate가 모두 실행됐다.
- [ ] CPU SFT가 12 step을 끝내고 checkpoint audit 가능한 파일을 만들었다.
- [ ] checkpoint에서 실제 한국어 prompt 추론을 수행했다.
- [ ] 자동 품질 결과의 통과/실패와 artifact 무결성을 구분해 기록했다.
- [ ] teacher 내부 라이선스·release block과 외부 수동 승인 경계를 유지했다.

## 연습문제

1. public과 teacher의 같은 prompt가 서로 다른 답을 가질 때 heldout 우선 예약이 필요한 이유를 설명하라.
2. `source_manifest` 결속을 SFT 설정에 추가하고 mix manifest가 바뀌면 학습 preflight가 실패하게 만들어라.
3. tiny 설정의 `gradient_accumulation_steps`를 2로 바꾸고 target-token weighted loss 계산을 손으로 검산하라.
4. 품질 suite에 두 turn 기억 시나리오를 추가하고 첫 assistant 응답이 다음 prompt history에 실제 포함되는지 추적하라.
