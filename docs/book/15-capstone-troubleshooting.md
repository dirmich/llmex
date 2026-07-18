# 15. End-to-end capstone과 문제 해결

이 capstone은 두 층이다. 00~08장의 fixture CPU 경로는 저장소만으로 실행할 수 있다. 09~14장의 teacher·혼합 SFT·수동 승인·private HF/GGUF 경로는 필요한 외부 입력과 실제 checkpoint SHA·llama.cpp checkout을 명시하는 gated extension이다. 외부 조건이 없는 상태에서 도움말 확인만으로 전체 capstone 완료를 주장하지 않는다.

## 학습 목표

- 데이터부터 자동·수동 대화 품질 증거까지 작은 실행을 완성한다.
- 실패 지점을 artifact와 invariant로 좁힌다.
- 장기 학습·외부 공개 전에 stop condition을 판정한다.

## 선행지식

00~14장을 순서대로 완료해야 한다.

## 관련 실제 파일

- [전체 실행 가이드](../run-guide.md), [pipeline](../../src/llmex/pipeline.py), [smoke 설정들](../../configs)
- [전체 테스트](../../tests), [운영 runbook](../operations-runbook.md), [실패 모드](../failure-modes.md)
- [TODO](../todo.md), [구현 이력](../history.md), [역사 snapshot인 프로젝트 계획](../../../knowledge_base/Codex/LLMEX/프로젝트%20계획.md)

현재 동작의 권위는 이 저장소의 `src/llmex`, `configs`, `docs`와 CLI `--help`다. 외부 `knowledge_base`의 프로젝트 계획은 M0부터 1.5.2까지의 운영 snapshot을 이해하는 참고 자료일 뿐이다. 그 문서의 개인 절대 경로나 과거 단계·산출물을 현재 capstone에 복제하지 않는다.

## 핵심 개념

capstone의 목적은 좋은 대형 모델을 만드는 것이 아니라 모든 경계가 작은 fixture에서 연결되고 재검증되는지 증명하는 것이다. 단계별 산출물은 다음 단계의 단순 경로 입력이 아니라 SHA/fingerprint가 고정된 전제다.

```text
dated dump → attributed corpus → tokenizer/shards → causal checkpoint
→ eval evidence → teacher inventory/export → non-leaking mix
→ SFT checkpoint → automatic quality → manual quality → release decision
```

## 단계별 구현

1. `uv sync --frozen`과 전체 정적 검사를 통과한다.
2. sample MediaWiki fixture로 extract/clean/dedup/document split/report를 실행한다.
3. 작은 tokenizer를 학습하고 Unicode round-trip·shard manifest를 검증한다.
4. smoke CausalLM을 몇 step 학습하고 중단·resume parity와 checkpoint audit를 통과한다.
5. validation/test NLL, cloze, generation, contamination/canary, cache benchmark를 실행한다.
6. teacher는 먼저 mock server/pilot으로 prepare→collect→export→validate를 검증한다.
7. public+teacher mix의 heldout 우선 격리, overlap 0, release blocked를 확인한다.
8. assistant-only SFT preflight baseline→train→best/latest eval/generate를 실행한다.
9. SHA 고정 자동 quality suite와 현재 구현된 수동 blind review gate를 실행한다.
10. release audit/bundle을 만들되 법무·외부 공개 승인이 없으면 공개하지 않는다.

## 실제 명령

repository의 stock YAML은 서로 자동 연결된 capstone 세트가 아니며 일부는 과거 독립 fixture다. 원본을 직접 실행하거나 덮어쓰지 말고 `docs/book/examples`의 파생 YAML을 사용한다. 동적 SHA가 필요한 teacher·mix·SFT·quality 설정은 각 장의 지시에 따라 복사본을 만들고, 직전 단계가 확정한 실제 SHA와 경로를 옮긴 뒤 반드시 `llmex config validate`를 통과시킨다.

```bash
uv sync --frozen
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run llmex data sample-e2e --config configs/data/sample.yaml \
  --input tests/fixtures/kowiki-sample.xml.bz2 \
  --output-dir data/book/sample-corpus --max-documents 1000

uv run python docs/book/examples/build-smoke-corpus.py
uv run llmex config validate docs/book/examples/tokenizer-smoke.yaml --kind tokenizer
uv run llmex tokenizer train --config docs/book/examples/tokenizer-smoke.yaml
uv run llmex tokenizer evaluate --config docs/book/examples/tokenizer-smoke.yaml
uv run llmex tokenizer pack --config docs/book/examples/tokenizer-smoke.yaml

uv run llmex config validate docs/book/examples/pretrain-smoke.yaml --kind training
uv run llmex train smoke --config docs/book/examples/pretrain-smoke.yaml

uv run llmex config validate docs/book/examples/evaluation-smoke.yaml --kind evaluation
uv run llmex eval --config docs/book/examples/evaluation-smoke.yaml

uv run llmex distill --help
uv run llmex sft preflight-mix --help
uv run llmex sft prepare-mix --help
uv run llmex sft --help
uv run llmex sft quality-preflight --help
uv run llmex sft quality-review-validate --help
uv run llmex release audit --help
uv run llmex release bundle --help
uv run llmex release gate --help
uv run llmex model export-hf --help
uv run llmex model export-gguf --help
```

`sample-e2e`는 M1 파이프라인과 provenance를 보여 주는 독립 실습이며, 입력 fixture가 너무 작아 이후 학습에 쓰지 않는다. 바로 다음 생성기는 schema가 완전한 합성 문서를 split마다 6개씩 원자 기록하고 결정적 corpus SHA를 출력한다. 이 corpus에서 04장의 smoke 전용 `artifacts/tokenizers/book-smoke-bpe`를 만들고 07장의 `runs/book-pretrain`, 08장의 validation/test 평가로 실제 연결한다. production `artifacts/tokenizers/bpe-16k`와 충돌하지 않는다. 실행 후 tokenizer manifest의 requested/actual vocab이 모두 16,000인지, shard manifest의 각 split `tokens`가 training `sequence_length` 256보다 큰지 확인한다. pretrain 예제의 `model.vocab_size`도 같은 16,000에 결속돼 있다.

나머지는 값이 실행 때마다 달라지는 다음 결속 사슬을 따른다.

1. 09장에서 teacher `export → validate`를 마친 뒤 export manifest SHA를 확정한다.
2. 그 SHA와 공개 데이터 경로를 10장의 `sft-mix-book.yaml`에 넣고 `preflight-mix → prepare-mix → status-mix → validate-mix`한다.
3. mix manifest SHA를 11장의 `sft-book.yaml`에 넣고 07장의 base checkpoint에서 SFT를 수행한다.
4. SFT config·SFT checkpoint·scenario suite의 실제 SHA 세 개를 12장의 `quality-book.yaml`에 넣고 자동 quality를 평가·검증한다.
5. 같은 checkpoint와 품질 증거를 13장의 최소 100개 blind review에 결속하고 수동 gate evidence를 만든다.
6. 14장에서 선택 checkpoint를 private HF와 F16 GGUF로 내보내 Transformers/llama.cpp parity를 확인한다.
7. 법무·baseline·quality-release·release 네 승인과 엄격한 manual evidence 검증을 모두 통과한 경우에만 public release gate를 연다.

placeholder SHA는 실행 가능한 값이 아니다. 각 설정은 저장 후 해당 `--kind`의 `config validate`와 단계별 preflight를 먼저 통과해야 한다.

## 예상 산출물

각 단계에 resolved config, manifest/fingerprint, metrics, checkpoint+SHA, JSON/Markdown/checksum 평가, distillation spool/export, mix manifest, SFT checkpoint, automatic results/report/manifest, manual template/gate evidence와 release bundle이 남는다.

## 검증 테스트

- fresh 디렉터리에서 같은 입력과 seed로 핵심 artifact bytes/fingerprint가 같다.
- 단계별 파일 한 byte를 바꾸면 바로 다음 validate가 실패한다.
- validation/test/quality suite와 train prompt/source 교집합이 0이다.
- checkpoint resume 뒤 loss/data cursor/RNG가 연속 실행과 같다.
- 자동 품질 실패나 critical 수동 review가 release 성공으로 바뀌지 않는다.

## 흔한 실패와 해결

| 증상 | 먼저 확인 | 해결 |
|---|---|---|
| config validation 실패 | 오타·암묵적 문자열·경로 | strict 오류의 첫 필드를 수정하고 fingerprint 재생성 |
| tokenizer/model 불일치 | vocab·special IDs·manifest SHA | 같은 tokenizer manifest에 모델 설정을 다시 결속 |
| resume loss 급변 | optimizer/sampler/RNG/schema | weight-only 우회를 금지하고 완전 checkpoint부터 재개 |
| EOS 미도달·반복 loop | assistant EOS label·data·decoding | masking을 검증하고 seed/profile별 최악값으로 재평가 |
| teacher 완료율 저하 | finish reason·길이·copy filter | pilot을 중단·보존하고 prompt/filter를 별도 version으로 교정 |
| quality validate 변조 | pinned SHA·부분 output·staging | 원인을 확인한 새 output dir에서 재실행; 기존 증거 덮어쓰기 금지 |
| OOM | sequence/micro batch/peak+RSS | micro batch를 줄이고 accumulation으로 유효 batch 유지 |

## 최종 체크리스트

- [ ] 모든 입력은 date/revision/license/SHA provenance를 가진다.
- [ ] split/overlap/tokenizer/causal/checkpoint gate가 실패-폐쇄된다.
- [ ] 학습과 재개가 deterministic smoke에서 일치한다.
- [ ] 평가 범위와 미실행 항목을 숨기지 않는다.
- [ ] 자동·수동 품질 증거가 checkpoint와 응답 hash에 결속된다.
- [ ] teacher/internal data의 release blocked가 유지된다.
- [ ] 기존 checkpoint parity를 선택 checkpoint parity로 오인하지 않는다.
- [ ] 법무·책임자 승인 전 외부 공개하지 않는다.

## 연습문제

1. capstone을 완전히 새 임시 root에서 두 번 실행하고 달라진 artifact를 분류하라.
2. 의도적으로 tokenizer manifest, checkpoint, quality response를 각각 변조해 어느 gate가 잡는지 기록하라.
3. 87.8M baseline에서 실제 대화 모델까지 남은 데이터·학습·자동·수동·릴리스 작업을 DAG로 그려라.
4. 장애 보고서를 “관측 증거/원인 추론/미확인/복구 검증” 네 구역으로 작성하라.
