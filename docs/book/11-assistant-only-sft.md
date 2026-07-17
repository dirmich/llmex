# 11장. Assistant-only SFT 학습기 만들기

대화 데이터의 모든 token에 언어 모델 loss를 주면 모델은 사용자 질문과 system 지시까지 흉내 내도록 학습된다. Assistant-only supervised fine-tuning(SFT)은 입력 문맥은 attention에 사용하되 assistant가 말해야 할 token에만 loss를 준다. 이 장에서는 masking, token 가중 gradient accumulation, 완전 재개 checkpoint를 구현한다.

## 학습 목표

- assistant-only label mask를 직접 만들 수 있다.
- token-level cross entropy와 perplexity를 설명할 수 있다.
- 크기가 다른 micro-batch loss를 target token 수로 가중할 수 있다.
- 재현 가능한 SFT checkpoint에 필요한 상태를 열거할 수 있다.
- LLMEX의 preflight, train, resume, eval, generate를 실행하고 산출물을 검증할 수 있다.

## 선행지식

- decoder-only causal language model과 next-token prediction
- cross entropy, AdamW, gradient accumulation
- tokenizer special token과 attention context
- 10장의 mix manifest와 release 정책

## 관련 실제 파일

- [SFT 설정 schema](../../src/llmex/config.py)
- [chat schema·hash·라이선스 검증](../../src/llmex/chat/data.py)
- [assistant-only label 생성](../../src/llmex/chat/template.py)
- [SFT trainer와 checkpoint 복원](../../src/llmex/chat/runtime.py)
- [결정적 sampler](../../src/llmex/train/data.py)
- [checkpoint 저장·검증](../../src/llmex/train/checkpoint.py)
- [smoke SFT 설정](../../configs/sft/smoke.yaml)
- [SFT 회귀 테스트](../../tests/test_g003_chat.py)
- [SFT 운영 가이드](../chat-sft.md)

## 핵심 개념/수식

### 1. ChatRow 계약

한 행은 system 선택 1회, user/assistant 교대, assistant 종료 구조를 가진다.

```json
{
  "schema_version": 1,
  "id": "example-001",
  "split": "train",
  "messages": [
    {"role": "user", "content": "대한민국의 수도는?"},
    {"role": "assistant", "content": "서울입니다."}
  ],
  "provenance": {
    "dataset": "example",
    "source": "local-fixture",
    "license": "CC-BY-4.0",
    "collected_at": "2026-07-18"
  },
  "sha256": "정규화된 본문 fingerprint"
}
```

loader는 행 hash, split, 허용 라이선스, 중복 ID를 검사한다. train/heldout 사이에서는 행 hash뿐 아니라 canonical final-user prompt와 provenance source identity의 교집합도 금지한다.

### 2. Assistant-only mask

LLMEX template은 각 turn 앞에 role prefix를 넣고 assistant content 뒤에 EOS를 붙인다.

```text
<bos>
<|system|> ...
<|user|> ...
<|assistant|> 정답 ... <eos>
```

label에서 학습하지 않을 위치는 PyTorch cross entropy의 기본 ignore index인 `-100`으로 둔다.

```python
ids = [BOS]
labels = [-100]

for message in messages:
    prefix = encode(role_prefix[message.role])
    content = encode(message.content + "\n")
    ids += prefix
    labels += [-100] * len(prefix)
    ids += content
    labels += content if message.role == "assistant" else [-100] * len(content)
    if message.role == "assistant":
        ids += [EOS]
        labels += [EOS]
```

token \(t\)의 label을 \(y_t\)라 하면 loss는 assistant target 집합 \(A\)에만 적용된다.

\[
\mathcal{L}_{SFT}=-\frac{1}{|A|}\sum_{t\in A}\log p_\theta(y_t\mid x_{<t})
\]

문맥 token은 loss에 들어가지 않지만 attention 입력에는 남아 있으므로 assistant가 질문에 조건화된다. EOS도 assistant target이므로 답변 종료를 학습한다.

### 3. 길이와 truncation

현재 tokenizer 함수는 길이가 넘으면 왼쪽을 자르지만, trainer 초기화는 모든 train/heldout 행의 실제 전체 길이를 먼저 계산해 `sequence_length` 초과를 실패시킨다. source manifest를 쓰는 정식 경로에서는 mix 단계도 truncation 없이 길이를 거른다.

추론 공간도 확인한다.

\[
L_{generation\ prompt}+max\_new\_tokens\le model.max\_seq\_len
\]

이 검사가 없으면 학습은 성공했는데 실제 대화 생성은 context limit에 즉시 걸릴 수 있다.

검증을 마친 token을 매 batch에서 다시 BPE 처리할 필요는 없다. LLMEX는 1차 tokenization에서 길이·generation gate와 input/label SHA-256을 계산하고, offset을 포함한 정확한 persistent byte가 완화 불가 128 MiB 이내인지 먼저 확인한다. 통과한 경우에만 train/heldout 각각에 연속 int32 input, int32 label, int64 offset tensor를 할당한다. 2차 tokenization 값이 1차 SHA와 같아야 buffer를 채우므로 두 pass 사이의 동일 길이 값 변경도 차단한다.

```text
train cache   = input int32 + label int32 + offsets int64
heldout cache = input int32 + label int32 + offsets int64
총 영속 tensor 객체 = 6
```

batch에서는 sampler index의 offset 구간만 long으로 복사하고 PAD와 `-100`을 채운다. 따라서 기존 token/label tensor와 정확히 같으면서 학습·validation 중 BPE 재실행은 0회다. `sft preflight`의 `token_cache`에서 split별 행·token·byte, dtype, tensor 수와 cap을 확인한다.

### 4. Target-token 가중 accumulation

micro-batch마다 assistant token 수가 다르다. batch loss를 단순 평균하면 짧은 답변과 긴 답변이 같은 비중을 갖는다. LLMEX는 각 micro-batch의 target 수 \(n_i\)로 가중한다.

\[
\mathcal{L}_{acc}=\sum_i \frac{n_i}{\sum_j n_j}\mathcal{L}_i
\]

```python
counts = [count(labels != -100) for labels in micro_batches]
total = sum(counts)
for batch, count in zip(micro_batches, counts):
    loss = model(batch).loss
    (loss * count / total).backward()
clip_grad_norm_(model.parameters(), max_norm)
optimizer.step()
```

heldout loss도 batch 평균의 평균이 아니라 target token 가중 평균이다.

\[
\mathcal{L}_{heldout}=\frac{\sum_i n_i\mathcal{L}_i}{\sum_i n_i},
\qquad PPL=\exp(\min(\mathcal{L}_{heldout},80))
\]

### 5. 완전 재개 checkpoint

모델 가중치만 저장하면 같은 학습을 이어가는 것이 아니다. 현재 SFT schema 2 checkpoint에는 다음이 포함된다.

- model, optimizer, scaler
- scheduler step/horizon/policy
- train/validation sampler cursor와 epoch
- Python, NumPy, CPU/CUDA Torch RNG
- step, validation count, best validation loss
- 실제 precision
- config/model/tokenizer/train/heldout/base checkpoint fingerprint
- redistribution/release 정책

저장은 optimizer 경계(`micro_step == 0`)에서만 허용된다. restore는 sampler cursor가 step과 맞는지, scheduler horizon이 유효한지, tensor와 optimizer 상태가 유한한지까지 검사한다.

### 6. Source manifest와 release 계승

정식 mix를 사용한다면 SFT YAML에 두 값을 함께 넣는다.

```yaml
source_manifest: data/chat/ko-public-teacher-v1/manifest.json
expected_source_manifest_sha256: "현재 mix manifest의 64자리 SHA-256"
```

trainer는 manifest의 train/heldout SHA, tokenizer SHA, length gate, release 정책을 현재 입력과 대조한다. 내부 teacher 라이선스가 있으면 checkpoint에도 `redistribution_allowed=false`, `release_gate=blocked`가 기록된다. 학습 성공이 배포 허가를 뜻하지 않는다.

### 7. Fresh run과 resume 경계

새 학습과 중단 복구는 다른 명령이다. `sft train`은 `run_dir`가 존재하지 않을 때만 디렉터리를 원자적으로 만들며, 빈 디렉터리도 기존 run으로 간주해 거부한다. 검사 직후 다른 프로세스가 같은 경로를 만들더라도 실제 `mkdir`의 배타성으로 둘 중 하나만 성공한다. 기존 파일을 지우거나 덮어쓰지 않는다.

checkpoint의 전체 fingerprint와 상태를 복원한 `sft resume`만 기존 run에 계속 기록할 수 있다. pilot과 full은 같은 사전학습 base checkpoint에서 출발하되 서로 다른 미존재 run 디렉터리를 사용한다. full은 pilot checkpoint를 이어받지 않는다.

## 단계별 구현

1. 엄격한 Message/Provenance/ChatRow schema와 canonical row hash를 만든다.
2. train/heldout의 row, prompt, source overlap을 검사한다.
3. 고정 role prefix와 BOS/EOS를 정의한다.
4. assistant content/EOS만 target으로 두는 tokenizer를 만든다.
5. 모든 행에 target token이 있고 길이 계약을 만족하는지 초기화 때 검사한다.
6. 2-pass SHA 결속과 연속 compact buffer·hard cap으로 검증 token을 cache한다.
7. 결정적 sampler와 seed/RNG 설정을 만든다.
8. target-token 가중 accumulation, gradient clipping, finite 검사를 구현한다.
9. validation을 같은 방식의 token 가중 NLL/PPL로 계산한다.
10. 전체 상태와 fingerprint를 checkpoint에 저장하고 strict restore한다.
11. source manifest와 release 정책을 checkpoint와 평가까지 계승한다.
12. 새 train은 미존재 run 디렉터리를 원자 선점하고 strict resume만 기존 run을 사용한다.

## 실제 명령

stock smoke 설정은 독립 fixture이며 10장의 mix와 연결되지 않는다. `configs/sft/smoke.yaml`을 `docs/book/examples/sft-book.yaml`로 복사한 뒤 최소한 다음 필드를 수정한다.

```yaml
tokenizer_dir: artifacts/tokenizers/bpe-16k
train_data: data/chat/ko-public-teacher-v1/train.jsonl
heldout_data: data/chat/ko-public-teacher-v1/heldout.jsonl
source_manifest: data/chat/ko-public-teacher-v1/manifest.json
expected_source_manifest_sha256: "sha256sum으로 얻은 실제 64자리 값"
base_checkpoint: runs/book-pretrain/checkpoints/best.pt
run_dir: runs/book-sft
```

모델 shape와 vocab은 07장 checkpoint와 같아야 한다. placeholder를 실제 SHA로 바꾼 뒤에만 실행한다.

```bash
cp configs/sft/smoke.yaml docs/book/examples/sft-book.yaml
# 위 필드와 model shape를 수정한다.
sha256sum data/chat/ko-public-teacher-v1/manifest.json
uv run llmex config validate docs/book/examples/sft-book.yaml --kind sft
uv run llmex sft preflight --config docs/book/examples/sft-book.yaml --measure-baseline
uv run llmex sft train --config docs/book/examples/sft-book.yaml --dry-run
test ! -e runs/book-sft
uv run llmex sft train --config docs/book/examples/sft-book.yaml
```

중단된 run을 재개하고 평가·생성한다.

```bash
uv run llmex sft resume \
  --config docs/book/examples/sft-book.yaml \
  --checkpoint runs/book-sft/checkpoints/latest.pt

uv run llmex sft eval \
  --config docs/book/examples/sft-book.yaml \
  --checkpoint runs/book-sft/checkpoints/best.pt

uv run llmex sft generate \
  --config docs/book/examples/sft-book.yaml \
  --checkpoint runs/book-sft/checkpoints/best.pt \
  --prompt '대한민국의 수도는 어디인가요?'
```

정식 실행에서는 파생 설정에 10장의 mix 출력·manifest, 실제 base checkpoint, 모델 크기, 장치, pilot에서 검증한 step/batch를 반영한다. pilot과 full YAML의 `base_checkpoint`는 같고 `run_dir`는 달라야 한다. micro batch 4, accumulation 16에서 train 행 수가 `N`이면 `ceil(3 × floor(N / 4) / 16)`을 약 3 epoch의 full step 시작값으로 사용하되 pilot 실측으로 시간과 안정성을 다시 계산한다.

## 예상 산출물

```text
runs/book-sft/
├── resolved-config.json
├── data-manifest.json
├── metrics.jsonl
└── checkpoints/
    ├── step-00000010.pt
    ├── latest.pt
    └── best.pt
```

train 결과에는 최종 step, 마지막 loss, best validation loss, checkpoint 경로가 나온다. `metrics.jsonl`에는 학습 loss/LR과 validation loss/PPL이 분리되어 기록된다.

## 검증 테스트

```bash
uv run pytest -q tests/test_g003_chat.py
uv run pytest -q tests/test_m4_training.py
uv run ruff check src/llmex/chat src/llmex/train tests/test_g003_chat.py
uv run pyright
```

확인해야 할 회귀는 다음과 같다.

- user/system/prefix label이 모두 `-100`
- assistant content와 EOS만 target
- truncation 뒤 target이 없으면 실패
- train/heldout row·prompt·source 누출 실패
- 허용되지 않은 라이선스 실패
- source manifest SHA·출력·tokenizer·length/release 변조 실패
- checkpoint model/optimizer/sampler/RNG/precision/policy 변조 실패
- resume 결과가 중단 없이 학습한 결과와 동일
- preflight baseline이 외부 RNG/sampler/model mode를 바꾸지 않음

## 흔한 실패와 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| assistant 학습 token 없음 | 잘못된 대화 순서 또는 너무 짧은 sequence | 마지막 turn이 assistant인지 확인하고 길이 gate를 앞단에 둔다. |
| prompt/source 누출 | mix를 거치지 않았거나 입력이 변함 | `validate-mix`를 다시 통과시키고 그 출력만 사용한다. |
| source manifest 결속 실패 | SHA, tokenizer, train/heldout 파일 불일치 | 현재 파일을 기준으로 새 run/config를 만들고 수동 완화하지 않는다. |
| fresh train run_dir 충돌 | 빈 경로를 미리 만들었거나 과거 run 경로 재사용 | 새 이름의 아직 존재하지 않는 run 경로를 지정하고, 중단 복구라면 `resume`을 사용한다. |
| resume sampler 오류 | 다른 config/data 또는 손상 checkpoint | 원 checkpoint와 config fingerprint를 대조한다. |
| fp16 scaler 오류 | 장치·precision 변경 | checkpoint와 같은 실제 precision으로 재개한다. |
| loss는 감소하지만 대화가 나쁨 | NLL만 최적화되고 생성 품질 미검증 | 12장 자동 gate와 13장 수동 gate를 별도로 실행한다. |

## 체크리스트

- [ ] assistant content와 EOS만 target인가?
- [ ] train/heldout row·prompt·source overlap이 0인가?
- [ ] 모든 행이 sequence/generation 길이 계약을 만족하는가?
- [ ] token cache의 2-pass SHA, offset 포함 byte와 128 MiB cap을 확인했는가?
- [ ] accumulation이 target token 수로 가중되는가?
- [ ] loss, gradient norm, checkpoint tensor가 finite인가?
- [ ] sampler와 RNG를 checkpoint에 저장하는가?
- [ ] optimizer 경계에서만 checkpoint를 저장하는가?
- [ ] source manifest SHA를 pin했는가?
- [ ] 내부 teacher release 차단을 계승하는가?
- [ ] pilot/full이 동일 base와 서로 다른 미존재 run 디렉터리를 사용하는가?
- [ ] 실제 대화 품질을 별도 gate로 검증할 계획인가?

## 연습문제

1. user token에도 loss를 주면 모델 행동이 어떻게 달라질 수 있는가?
2. micro-batch loss 단순 평균과 token 가중 평균의 차이를 숫자 예로 계산하라.
3. 모델과 optimizer만 저장한 checkpoint가 완전 재개가 아닌 이유를 세 가지 쓰라.
4. `max_steps`만 fingerprint에서 제외하고 scheduler horizon을 checkpoint로 검증하는 설계의 목적을 설명하라.
5. validation PPL이 좋아졌지만 EOS 도달률이 나빠질 수 있는 이유를 설명하라.
