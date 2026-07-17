# 08. 평가, contamination과 canary

## 학습 목표

- token-weighted NLL/PPL, cloze, 생성 품질을 봉인 artifact로 만든다.
- exact/near contamination과 canary exposure를 구분한다.
- cache parity와 latency/memory benchmark를 수행한다.

## 선행지식

로그우도, perplexity, rank와 Jaccard가 필요하다.

## 관련 실제 파일

- [평가 runner](../../src/llmex/evaluation/runner.py), [추론 runtime](../../src/llmex/inference/runtime.py)
- [평가 테스트](../../tests/test_m5_evaluation.py), [교재 연결 설정](examples/evaluation-smoke.yaml), [평가 보고서](../evaluation-report.md)
- [canary/오염 요구사항](../prd.md), [실패 모드](../failure-modes.md)

## 핵심 개념과 수식

예제 loss의 단순 평균이 아니라 전체 target token 음의 로그우도를 합산한다.

\[
NLL=\frac{\sum_i\sum_{t\in i}-\log p(x_t|x_{<t})}{\sum_i T_i},\quad PPL=e^{NLL}
\]

contamination은 평가 prompt가 train corpus에 정확히 포함되는지와 5-character shingle Jaccard 최대값을 본다. canary는 비밀 후보의 조건부 평균 log-likelihood 순위를 측정하며, 설정된 rank 이내면 노출 실패다.

## 단계별 구현

1. training config, tokenizer/shard manifest와 checkpoint fingerprint를 strict 검증한다.
2. split별 loss sum과 target token 수를 누적해 NLL/PPL을 계산한다.
3. 고정 cloze 문항의 candidate span만 결합 tokenization offset으로 score한다.
4. generation에 seed/sampling/token IDs/EOS/context/repetition/distinct/Unicode를 기록한다.
5. train corpus를 한 번 순회해 exact와 bounded shingle Jaccard를 계산한다.
6. canary provenance·candidate·secret schema와 파일 SHA를 검증하고 rank gate를 낸다.
7. JSON/Markdown을 원자 저장하고 checksum manifest와 payload fingerprint를 만든다.

```python
log_probs = logits[:, :-1].log_softmax(-1)
nll_sum += -log_probs.gather(-1, targets[:, 1:, None]).sum()
token_count += targets[:, 1:].numel()
ppl = math.exp(min(nll_sum / token_count, 80.0))
```

## 실제 명령

```bash
uv run llmex config validate docs/book/examples/evaluation-smoke.yaml --kind evaluation
uv run llmex eval --config docs/book/examples/evaluation-smoke.yaml
uv run llmex generate --config docs/book/examples/evaluation-smoke.yaml
uv run llmex benchmark --config docs/book/examples/evaluation-smoke.yaml
uv run pytest -q tests/test_m5_evaluation.py
```

이 설정은 07장의 training config와 best checkpoint, 04장의 smoke 전용 `artifacts/tokenizers/book-smoke-bpe` manifest, 생성된 `data/book/smoke-corpus/corpus-v1.jsonl.zst`를 같은 상대 경로로 결속한다. validation/test split마다 256-token window가 있으므로 NLL 평가가 실제로 실행된다. production tokenizer와 stock `configs/evaluation/smoke.yaml`은 이 capstone 입력에 섞지 않는다.

## 예상 산출물

`evaluation-report.json`, `evaluation-report.md`, `evaluation-report.checksums.json`과
`generation-report.*`, `benchmark-report.*` 대응 파일이 생긴다. payload에는 checkpoint SHA와
config/corpus/tokenizer/model/shards fingerprint가 있다.

## 검증 테스트

- 작은 logits의 수동 token-weighted NLL과 일치한다.
- cloze candidate가 BPE 경계에서 prefix와 merge돼도 span score가 맞다.
- corpus/canary 경로가 없으면 “통과”가 아니라 미실행/실패다.
- cache/no-cache 생성 parity와 고정 seed 재현성이 통과한다.
- artifact 한 byte 변조를 checksum/fingerprint 검증이 잡는다.

## 흔한 실패와 해결

- split별 1 batch 값을 전체 평가로 표기: `max_batches`와 token count를 보고서에 노출한다.
- canary 파일 없음=안전: 미실행은 증거 부재다. gate 실패/대기로 유지한다.
- candidate를 따로 tokenize: prefix 경계 merge가 바뀐다. 결합 offset을 사용한다.

## 체크리스트

- [ ] 평가 checkpoint와 모든 입력 fingerprint가 결속됐다.
- [ ] NLL이 target-token 가중이다.
- [ ] contamination/canary 미실행을 통과로 해석하지 않는다.
- [ ] 생성·benchmark artifact가 checksum으로 봉인됐다.

## 연습문제

1. 길이 2와 20인 예제에서 예제 평균과 token 평균 차이를 계산하라.
2. exact는 아니지만 높은 5-gram Jaccard인 문장을 만들어라.
3. canary 후보 수가 rank threshold보다 작을 때 설정을 어떻게 거부할지 설계하라.
