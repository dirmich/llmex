# 04. Byte-level BPE와 chat template

## 학습 목표

- byte-level BPE를 결정적으로 학습·평가한다.
- 문서 경계를 보존한 token shard를 만든다.
- role template와 assistant-only label masking을 구현한다.

## 선행지식

UTF-8 byte, BPE merge와 cross-entropy label masking을 이해해야 한다.

## 관련 실제 파일

- [tokenizer core](../../src/llmex/tokenizer/core.py), [평가](../../src/llmex/tokenizer/evaluate.py), [packing](../../src/llmex/tokenizer/pack.py)
- [chat data](../../src/llmex/chat/data.py), [chat template](../../src/llmex/chat/template.py)
- [tokenizer 테스트](../../tests/test_m2_tokenizer.py), [chat 테스트](../../tests/test_g003_chat.py), [16k 설정](../../configs/tokenizer/bpe-16k.yaml)

## 핵심 개념과 수식

BPE는 가장 빈번한 인접 symbol pair를 반복 병합한다. byte-level 시작 어휘는 모든 UTF-8 byte를 표현하므로 UNK 의존을 줄인다. 효율은 `chars/token`, `bytes/token`, `tokens/word`와 byte baseline 대비 감소율로 본다.

Chat SFT에서 loss는 assistant 본문과 assistant EOS에만 적용한다.

\[
L=-\frac{1}{N_{assistant}}\sum_{t:y_t\neq-100}\log p(y_t\mid x_{<t})
\]

## 단계별 구현

1. `<pad>`, `<bos>`, `<eos>`, `<unk>`, `<|system|>`, `<|user|>`, `<|assistant|>` ID를 고정한다.
2. train split만으로 BPE를 학습하고 tokenizer JSON·manifest를 원자 저장한다.
3. 고정 Unicode 표본의 encode→decode round-trip, UNK와 효율을 평가한다.
4. 문서마다 `text`를 encode한 뒤 EOS 하나를 붙인다. pack 경로에는 BOS가 없다.
5. token stream을 고정 `shard_tokens` 크기의 little-endian `.bin`으로 자른다. 긴 문서는 shard 경계를 넘을 수 있으며 manifest의 전역 boundary가 시작·끝·EOS 위치를 보존한다.
6. chat role prefix와 content를 각각 별도로 encode하고 system/user/role prefix label을 `-100`으로 mask한다.

```python
ids, labels = [BOS], [-100]
for message in messages:
    prefix = encode(role_prefix[message.role])
    content = encode(message.content + "\n")
    ids.extend(prefix)
    labels.extend([-100] * len(prefix))
    ids.extend(content)
    labels.extend(content if message.role == "assistant" else [-100] * len(content))
    if message.role == "assistant":
        ids.append(EOS)
        labels.append(EOS)
assert len(ids) == len(labels)
if len(ids) > max_length:
    ids, labels = ids[-max_length:], labels[-max_length:]
if len(ids) < 2 or all(label == -100 for label in labels[1:]):
    raise IntegrityError("truncation 뒤 assistant 학습 token이 없습니다")
```

실제 구현도 role prefix와 content를 별도로 encode한다. 왼쪽 truncation 뒤 assistant content 또는 EOS label이 하나도 남지 않으면 실패한다.

## 실제 명령

```bash
uv run python docs/book/examples/build-smoke-corpus.py
uv run llmex config validate docs/book/examples/tokenizer-smoke.yaml --kind tokenizer
uv run llmex tokenizer train --config docs/book/examples/tokenizer-smoke.yaml
uv run llmex tokenizer evaluate --config docs/book/examples/tokenizer-smoke.yaml
uv run llmex tokenizer pack --config docs/book/examples/tokenizer-smoke.yaml
uv run pytest -q tests/test_m2_tokenizer.py tests/test_g003_chat.py
```

교재 설정은 03장의 작은 MediaWiki fixture가 아니라 생성기가 만든 `data/book/smoke-corpus/corpus-v1.jsonl.zst`를 읽고 smoke 전용 plural 경로 `artifacts/tokenizers/book-smoke-bpe`에 쓴다. 생성 corpus는 세 split에 각각 여러 문서와 256개보다 많은 token을 제공하고, schema가 허용하는 요청 vocab 16,000개를 실제로 모두 채우는 결정적 합성 어휘 reservoir를 포함한다. 정식 corpus는 stock `configs/tokenizer/bpe-16k.yaml`과 canonical production 경로 `artifacts/tokenizers/bpe-16k`를 사용한다. smoke와 production artifact를 같은 output에 섞지 않는다.

## 예상 산출물

`artifacts/tokenizers/book-smoke-bpe/tokenizer.json`, tokenizer manifest/report, `artifacts/tokenizers/book-smoke-bpe/shards/*.bin`과 실제 `artifacts/tokenizers/book-smoke-bpe/shards/manifest.json`이 생긴다. manifest의 requested/actual vocab은 모두 16,000이어야 한다. chat tokenization 결과는 길이가 정확히 같은 `input_ids`, `labels`를 가진다.

## 검증 테스트

- 모든 special token ID와 실제 vocab 크기가 manifest와 같다.
- 한글·emoji·결합문자·제어문자 표본이 strict UTF-8 round-trip한다.
- 마지막 shard를 제외한 shard가 `shard_tokens` 크기이고 manifest token 수/SHA와 일치한다. 문서는 shard 경계를 넘을 수 있으며 전역 boundary가 정확해야 한다.
- user/system token label은 전부 `-100`, assistant 본문·EOS만 target이다.
- tokenizer 함수는 초과 row를 왼쪽에서 자르고 assistant target이 하나도 남지 않으면 거부한다. 정식 trainer/mix 경로는 전체 길이를 먼저 검사해 학습 row truncation을 실패-폐쇄한다.

## 흔한 실패와 해결

- validation/test로 tokenizer 학습: 평가 누출이다. train 문서만 iterator에 넣는다.
- special ID drift: tokenizer·model·checkpoint 호환성이 깨진다. 상수와 manifest를 함께 검증한다.
- assistant EOS masking: 모델이 멈추는 법을 배우지 못한다. EOS를 target에 포함한다.

## 체크리스트

- [ ] vocab/special ID가 고정됐다.
- [ ] Unicode round-trip과 UNK gate가 통과한다.
- [ ] `.bin` shard SHA와 전역 문서 boundary·EOS 위치가 검증된다.
- [ ] assistant-only masking과 길이 초과 실패가 테스트됐다.

## 연습문제

1. role prefix와 첫 글자가 하나의 BPE token이 되는 사례를 만들고 masking을 검증하라.
2. 16k와 32k의 bytes/token·embedding 파라미터 비용을 비교하라.
3. multi-turn에서 각 assistant EOS가 label에 포함되는지 property test를 작성하라.
