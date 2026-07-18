# 토크나이저와 Transformer 모델 구현 교재

이 문서는 검증된 `corpus-v1.jsonl.zst`에서 byte-level BPE를 만들고, 이를 소비하는 decoder-only Transformer를 작은 수치 계약부터 조립하는 과정이다. 먼저 `uv run pytest -q tests/test_m2_tokenizer.py tests/test_m3_model.py`를 실패시키는 최소 골격을 만든 뒤 절 순서대로 통과시킨다.

## 1부. 토크나이저와 shard

### `src/llmex/tokenizer/__init__.py`

- **책임:** M2 패키지에서 외부가 사용할 최소 토크나이저 API를 제공한다.
- **먼저 구현할 계약:** `SPECIAL_TOKENS`, `load_tokenizer`를 import하고 `__all__`로 둘만 공개한다.
- **단계별 구현:** ① `core.py` 계약을 먼저 완성한다. ② 두 심볼만 re-export한다. ③ package import가 학습을 실행하지 않는지 확인한다.
- **반드시 실패해야 할 사례:** import만으로 artifact 생성, 존재하지 않는 심볼 export, 내부 `_assert_contract`까지 공개하는 경우다.
- **관련 테스트와 명령:** `uv run python -c 'from llmex.tokenizer import SPECIAL_TOKENS, load_tokenizer; print(SPECIAL_TOKENS)'`; `uv run pytest -q tests/test_m2_tokenizer.py`.
- **완료 산출물:** special token 계약과 안전 loader에 한정된 package boundary다.

### `src/llmex/tokenizer/core.py`

- **책임:** corpus identity를 고정하고 train split만으로 결정적 byte-level BPE를 학습·검증·로드한다.
- **먼저 구현할 계약:** `SPECIAL_TOKENS=("<pad>","<bos>","<eos>","<unk>")`, `SPECIAL_IDS` 0~3; `iter_documents`, `corpus_fingerprint`, `build_tokenizer`, `train`, `load_tokenizer`, `verify_round_trip`; 내부 `_assert_contract`다.
- **단계별 구현:** ① 압축 row의 split/text/SHA를 streaming 검증한다. ② split별 source SHA 목록과 corpus file SHA를 canonical fingerprint로 묶고 overlap을 거부한다. ③ `BPE(unk_token, byte_fallback=True)`에 ByteLevel pre-tokenizer/decoder를 결합한다. ④ `BpeTrainer`에 고정 special token 순서를 넘겨 train split iterator만 학습한다. ⑤ 임시 디렉터리에 tokenizer/vocab/merges/config를 쓰고 각각 SHA·bytes를 manifest에 기록한 뒤 replace한다. ⑥ load 시 모든 artifact SHA와 special ID를 재검사한다.
- **반드시 실패해야 할 사례:** corpus 파일 없음, 잘못된 split/text/SHA, source SHA가 여러 split에 존재, validation/test가 vocab 학습에 영향, special ID 변경, artifact 한 byte 변조, Unicode round-trip에서 UNK 또는 원문 불일치다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m2_tokenizer.py -k 'special_ids or split_leak or unicode_property'`; `uv run llmex tokenizer train --config docs/book/examples/tokenizer-smoke.yaml --force`.
- **완료 산출물:** `tokenizer.json`, `vocab.json`, `merges.txt`, `config.json`, `tokenizer-manifest.json`과 그 fingerprint다.

### `src/llmex/tokenizer/evaluate.py`

- **책임:** 전체 split의 토큰 효율과 seed 고정 Unicode round-trip 안전성을 평가한다.
- **먼저 구현할 계약:** `fixed_unicode_samples(count, seed)`, `evaluate(config, force=False)`다.
- **단계별 구현:** ① 한국어 완성형·자모·jamo 조합, family emoji, 한자, ASCII, combining mark 표본을 앞에 고정한다. ② 나머지는 surrogate를 제외한 Unicode 범위에서 local `random.Random(seed)`로 만든다. ③ split별 문자/UTF-8 byte/token/word/UNK/document를 합산한다. ④ chars/token, bytes/token, tokens/word, byte baseline 감소율을 계산한다. ⑤ JSON fingerprint와 Markdown 보고서를 쓴다.
- **반드시 실패해야 할 사례:** global RNG로 표본이 달라짐, surrogate 생성, UNK가 있는데 통과, round-trip 불일치, 기존 다른 operation의 평가 파일 덮어쓰기다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m2_tokenizer.py -k 'unicode_round_trip or fixed_10000'`; `uv run llmex tokenizer evaluate --config docs/book/examples/tokenizer-smoke.yaml --force`.
- **완료 산출물:** `evaluation.json`, `evaluation.md`와 split별 효율·UNK 0·고정 표본 수다.

### `src/llmex/tokenizer/pack.py`

- **책임:** 문서 EOS 경계를 보존한 split별 연속 token stream을 원자적 memory-mapped shard로 게시한다.
- **먼저 구현할 계약:** `_write_shard(path, ids, dtype)`, `pack(config, force=False)`다.
- **단계별 구현:** ① tokenizer vocab 최대 ID로 little-endian `uint16`/`uint32`를 선택하고 uint32 초과는 거부한다. ② 각 문서를 encode한 뒤 EOS ID를 한 개 붙인다. ③ global start/end/eos boundary와 source SHA를 기록한다. ④ `shard_tokens`마다 `.bin.tmp` memmap을 flush/fsync/replace한다. ⑤ shard SHA·token 수·min/max ID 및 tokenizer/corpus fingerprint를 manifest에 넣는다. ⑥ 임시 디렉터리에서 완성한 뒤 기존 bin을 교체한다.
- **반드시 실패해야 할 사례:** EOS 누락/중복, 문서 boundary 오프셋 오류, dtype overflow, shard SHA 또는 길이 불일치, tokenizer manifest와 corpus identity 누락이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m2_tokenizer.py -k 'eos_dtype_boundaries or deterministic_shards'`; `uv run llmex tokenizer pack --config docs/book/examples/tokenizer-smoke.yaml --force`.
- **완료 산출물:** `shards/{train,validation,test}-NNNNN.bin`과 `shards/manifest.json`이다.

## 2부. Decoder-only Transformer

### `src/llmex/model/__init__.py`

- **책임:** 완성 모델의 안정된 공개 인터페이스만 노출한다.
- **먼저 구현할 계약:** `CausalLM`, `CausalLMOutput`, `GenerationConfig`와 정확한 `__all__`다.
- **단계별 구현:** ① 하위 수치 모듈을 먼저 완성한다. ② `lm.py`의 세 심볼을 re-export한다. ③ import 시 tensor나 장치를 만들지 않는지 확인한다.
- **반드시 실패해야 할 사례:** import 순환, private block을 API로 약속, package import가 CUDA 초기화를 요구하는 경우다.
- **관련 테스트와 명령:** `uv run python -c 'from llmex.model import CausalLM, CausalLMOutput, GenerationConfig'`; `uv run pytest -q tests/test_m3_model.py`.
- **완료 산출물:** 학습·추론이 공유하는 세 이름의 package API다.

### `src/llmex/model/norm.py`

- **책임:** 마지막 hidden 차원에 학습 가능한 RMSNorm을 적용한다.
- **먼저 구현할 계약:** `RMSNorm(size, eps=1e-5).forward(inputs)`다.
- **단계별 구현:** ① 크기 `size`의 ones weight를 parameter로 만든다. ② 입력을 fp32로 올려 제곱 평균과 `rsqrt(mean+eps)`를 계산한다. ③ 원 dtype으로 복원한 뒤 weight를 곱한다. ④ reference 식과 forward/backward를 비교한다.
- **반드시 실패해야 할 사례:** 평균을 hidden 차원이 아닌 전체 tensor에서 계산, 저정밀 통계로 NaN, dtype 미복원, gradient가 non-finite인 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m3_model.py -k rmsnorm`.
- **완료 산출물:** 입력 shape를 보존하고 finite gradient를 갖는 정규화 layer다.

### `src/llmex/model/rope.py`

- **책임:** Q/K의 인접 좌표 쌍에 rotary position embedding을 적용하고 device/dtype별 sin/cos cache를 재사용한다.
- **먼저 구현할 계약:** `RotaryEmbedding(head_dim, max_seq_len, theta)`, `cos_sin(length, offset, device, dtype)`, `forward(inputs, offset=0)`다.
- **단계별 구현:** ① 짝수 head dimension을 강제한다. ② inverse frequency를 persistent하지 않은 buffer로 둔다. ③ max sequence 전체 각도를 fp32로 계산하고 요청 dtype/device로 cache한다. ④ offset slice를 반환한다. ⑤ even/odd 좌표에 2D 회전식을 적용하고 flatten한다.
- **반드시 실패해야 할 사례:** 홀수 head dimension, length 0, 음수 offset, offset+length가 max 초과, device/dtype가 바뀌었는데 낡은 cache 재사용이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m3_model.py -k rope`.
- **완료 산출물:** manual rotation과 같은 tensor 및 cache decoding에서 올바른 position offset이다.

### `src/llmex/model/attention.py`

- **책임:** RoPE가 적용된 causal grouped-query self-attention과 선택적 KV cache를 구현한다.
- **먼저 구현할 계약:** `KVCache = tuple[Tensor, Tensor]`, `GroupedQueryAttention(config)`, `forward(inputs, cache=None, use_cache=False, implementation="sdpa")`다.
- **단계별 구현:** ① `head_dim`, query heads/KV heads, group 수를 config에서 계산한다. ② bias 없는 Q/K/V/out projection을 만든다. ③ `[B,T,D]`를 `[B,H,T,head_dim]`으로 바꾸고 Q/K에 past offset RoPE를 적용한다. ④ 과거 K/V를 sequence 축에 concat한다. ⑤ KV heads를 group 수만큼 반복한다. ⑥ absolute query/key position으로 boolean causal mask를 만든다. ⑦ SDPA와 eager reference 경로를 구현하고 merged output과 present cache를 반환한다.
- **반드시 실패해야 할 사례:** past+current가 max 초과, 미래 token이 과거 logits에 영향, KV head 반복 shape 오류, eager/SDPA 불일치, `sdpa|eager` 외 구현명 통과다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m3_model.py -k 'gqa_shape or causality or cache'`.
- **완료 산출물:** `[B,T,D]` attention output과 요청 시 layer KV cache다.

### `src/llmex/model/block.py`

- **책임:** SwiGLU FFN과 Pre-Norm residual decoder block을 조립한다.
- **먼저 구현할 계약:** `SwiGLU(config)`, `DecoderBlock(config)` 및 각 `forward`다.
- **단계별 구현:** ① gate/up/down bias 없는 선형층을 만든다. ② `down(silu(gate(x))*up(x))` 뒤 dropout을 적용한다. ③ block에 attention norm→attention→residual dropout/add를 둔다. ④ FFN norm→FFN→residual add를 이어 붙인다. ⑤ cache와 implementation 인자를 attention에 그대로 전달한다.
- **반드시 실패해야 할 사례:** post-norm으로 순서 변경, gate와 up의 곱 누락, residual shape 불일치, cache를 잃거나 잘못된 layer cache 반환이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m3_model.py -k 'forward or causality or cache'`.
- **완료 산출물:** hidden shape를 유지하는 decoder hidden과 optional present KV다.

### `src/llmex/model/lm.py`

- **책임:** tied embedding을 쓰는 전체 causal LM, shifted loss, greedy/sampling 생성을 제공한다.
- **먼저 구현할 계약:** dataclass `CausalLMOutput(logits, loss, cache)`, `GenerationConfig`; `CausalLM.forward`, `generate`, `parameter_count`, `memory_estimate`다.
- **단계별 구현:** ① token embedding, dropout, decoder blocks, final RMSNorm, bias 없는 LM head를 만든다. ② LM head weight를 embedding과 같은 parameter로 묶는다. ③ 모든 weight를 normal init하고 residual projection은 `1/sqrt(2*n_layers)`로 scale한다. ④ input/target/cache/length 계약을 검사한 뒤 block stack과 logits를 계산한다. ⑤ `logits[:,:-1]` 대 `targets[:,1:]` cross entropy와 `ignore_index`를 구현한다. ⑥ generate에서 cache/no-cache, repetition penalty, temperature 0 greedy, top-k, nucleus top-p, seeded multinomial, EOS batch 종료, context limit를 구현한다. ⑦ tied weight를 중복 세지 않는 parameter/memory 계산을 제공한다.
- **반드시 실패해야 할 사례:** int64 `[B,T]`가 아닌 입력, target shape 불일치, loss 입력 길이 1, cache layer 수 불일치, 빈/초과 문맥, 음수 생성 길이·temperature, top-k<1, top-p 범위 밖, repetition penalty≤0, EOS vocab 밖이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m3_model.py`; `uv run llmex model inspect --config configs/model/smoke.yaml`.
- **완료 산출물:** `[B,T,V]` logits·shifted loss·layer cache, cache parity를 갖는 생성 결과, 정확한 parameter 및 memory report다.

### `src/llmex/model/export.py`

- **책임:** release 차단 SFT checkpoint를 private HF Llama 디렉터리와 GGUF로 무결하게 변환한다.
- **먼저 구현할 계약:** `export_hf(config, checkpoint, expected_checkpoint_sha256, output_dir)`, `export_gguf(hf_dir, expected_hf_manifest_sha256, llama_cpp_dir, output, outtype)`다.
- **단계별 구현:** ① checkpoint immutable snapshot의 SHA·fingerprint·tensor shape/dtype/finite 값을 검증한다. ② LLMEX 이름을 HF Llama tensor 이름으로 완전 매핑하고 Q/K RoPE 배열을 half-split으로 변환한다. ③ tokenizer·BOS/EOS chat template·release 차단 manifest를 private mode staging에 기록하고 원자 게시한다. ④ 예상 HF manifest와 artifact SHA를 다시 확인한다. ⑤ 고정 ByteLevel BPE wrapper로 공식 llama.cpp converter를 실행한다. ⑥ GGUF magic·private mode를 확인하고 기존 출력 없이 게시한다. ⑦ Transformers logits와 llama.cpp greedy/EOS를 원본과 비교한다.
- **반드시 실패해야 할 사례:** checkpoint·manifest·artifact SHA 변조, tensor 누락·NaN·shape 불일치, public release policy, tokenizer 계약 불일치, 미지원 outtype, 변환 실패·timeout·동시 출력 생성, GGUF magic 손상이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_model_export.py`; `uv run llmex model export-hf --help`; `uv run llmex model export-gguf --help`.
- **완료 산출물:** 0700/0600 private HF 디렉터리와 `export-manifest.json`, 0600 GGUF, 원본/HF/llama.cpp parity 증거다.

## 묶음 완료 기준

1. `uv run pytest -q tests/test_m2_tokenizer.py tests/test_m3_model.py`가 통과한다.
2. `uv run ruff check src/llmex/tokenizer src/llmex/model tests/test_m2_tokenizer.py tests/test_m3_model.py`가 통과한다.
3. `uv run llmex tokenizer train/evaluate/pack` 재실행의 manifest·shard SHA가 같다.
4. 미래 token 변경이 과거 logits를 바꾸지 않고 cache/no-cache greedy generation이 같다.
5. `uv run llmex model inspect --config configs/model/smoke.yaml`의 parameter 수가 tied weight를 한 번만 센다.
