# 17장. 빈 저장소에서 대화 모델 도구까지 만드는 워크북

이 장은 00~16장의 지식을 실제 구현 순서로 바꾼다. 각 실습은 `준비 → 실패 테스트 → 최소 구현 → 통합 명령 → 산출물 검사`의 다섯 단계로 진행한다. 학습용 브랜치나 별도 디렉터리에서 구현하고, 정답 확인이 필요할 때만 현재 `src/llmex`를 비교한다.

## 학습 목표

- 57개 모듈을 의존 순서에 맞춰 작은 실행 단위로 재구현한다.
- 각 단계에서 먼저 실패 테스트를 만들고 artifact SHA로 완료를 증명한다.
- CPU fixture, CUDA pilot, 장기 실행과 외부 승인의 경계를 구분한다.

## 선행지식

00~08장의 CPU smoke를 실행할 수 있고, 16장의 모듈 지도에서 원하는 파일을 찾을 수 있어야 한다. teacher·SFT 확장은 09~13장의 provenance와 품질 gate 개념이 필요하다.

## 환경 프로필

| 프로필 | 목적 | 필수 조건 | 허용 범위 |
|---|---|---|---|
| CPU 최소 | 모듈·fixture·smoke 학습 | Python 3.11+, `uv 0.10.2`, 여유 공간 10 GiB | 00~08장, offline 증류 fixture, 작은 SFT |
| CUDA 개발 | 실제 모델 forward·학습 성능 확인 | CUDA 인식 PyTorch, bf16 smoke, 여유 공간 100 GiB 이상 | pilot 학습·benchmark |
| DGX Spark 장기 | 100M pretrain/SFT와 장기 artifact | 고정 NGC digest, GB10, unified memory/RSS/swap 기록, host NVMe | 전체 corpus와 정식 학습 |
| Teacher 연결 | localhost teacher 증류 | OpenAI-compatible endpoint, model identity 확인, 요청/응답 제한 | preflight 뒤 승인된 source만 수집 |

처음에는 CPU 최소 프로필만 사용한다. 네트워크·GPU·teacher를 일찍 붙이면 데이터 계약 오류와 장치 오류를 구분하기 어렵다.

## 0단계. 작업 공간과 재현 환경

1. `pyproject.toml`, `src/llmex`, `tests`, `configs`, `docs`, `data`, `artifacts`, `runs`를 만든다.
2. Python 하한과 dependency를 선언하고 `uv lock`으로 고정한다.
3. `errors.py`, `paths.py`, `fingerprint.py`, `config.py`를 차례로 구현한다.
4. 알 수 없는 config key와 프로젝트 밖 경로가 실패하는 테스트를 먼저 작성한다.
5. CLI `--version`, `config validate`, `fingerprint file`만 연결한다.

```bash
uv sync --frozen
uv run python -VV
uv run llmex --version
uv run llmex config validate configs/model/smoke.yaml --kind model
uv run pytest -q tests/test_foundation.py tests/test_config.py
```

완료 산출물은 lockfile, strict config 결과, 같은 입력에서 동일한 SHA다. 여기서는 `runs/`에 학습 결과가 생기지 않아야 한다.

## 1단계. 원자 I/O와 실행 기록

1. `data/io.py`에 같은 디렉터리 임시 파일→flush→fsync→replace를 구현한다.
2. 기존 output과 operation fingerprint가 같으면 재사용하고 다르면 conflict로 중단한다.
3. `locking.py`에 단일 writer lock을 추가한다.
4. `run.py`에 설정, Git revision, 환경 snapshot을 기록한다.
5. 쓰기 도중 예외를 주입해 최종 파일이 반쪽으로 남지 않는지 검사한다.

완료 기준은 “성공 시 완전한 새 파일, 실패 시 완전한 이전 파일” 둘 중 하나만 관찰되는 것이다.

## 2단계. Wikipedia 데이터 파이프라인

1. `schema.py`에서 attribution과 document schema를 먼저 고정한다.
2. `extract.py`를 fixture XML streaming parser로 구현한다.
3. `clean.py`에 markup 제거·정규화·품질 정책을 작은 함수로 추가한다.
4. `dedup.py`에서 exact hash 뒤 MinHash near duplicate를 처리한다.
5. `split.py`에서 normalized content hash 기반 split을 만든다.
6. `data/pipeline.py`와 CLI를 마지막에 연결한다.

```bash
uv run llmex data sample-e2e \
  --config configs/data/sample.yaml \
  --input tests/fixtures/kowiki-sample.xml.bz2 \
  --output-dir data/book/sample-corpus \
  --max-documents 1000 \
  --force
uv run pytest -q tests/test_m1_data.py
```

`data/book/sample-corpus/data-manifest.json`, `data-report.md`, `audit-sample.{json,md}`, `corpus-v1.jsonl.zst`와 split row 수, source URL/page/revision/license, split overlap 0을 직접 확인한다. fixture 성공 뒤에만 실제 dump download를 수행한다.

## 3단계. Byte-level BPE와 packed shard

1. `tokenizer/core.py`에서 special token 순서와 byte fallback을 고정한다.
2. 작은 train split으로 BPE를 학습하고 manifest에 corpus SHA를 넣는다.
3. 한국어 자모·emoji·결합문자 round-trip을 property test로 만든다.
4. `evaluate.py`에서 token/character 비율과 Unicode 표본을 평가한다.
5. `pack.py`에서 split별 token stream과 shard checksum을 만든다.

```bash
uv run llmex tokenizer train --config docs/book/examples/tokenizer-smoke.yaml --force
uv run llmex tokenizer evaluate --config docs/book/examples/tokenizer-smoke.yaml --force
uv run llmex tokenizer pack --config docs/book/examples/tokenizer-smoke.yaml --force
uv run pytest -q tests/test_m2_tokenizer.py
```

완료 기준은 round-trip 100%, special token ID 일치, manifest의 corpus/tokenizer/shard SHA 재계산 일치다.

## 4단계. Transformer를 작은 부품부터 구현

1. `RMSNorm`을 수식 기준 구현과 비교한다.
2. `RotaryEmbedding`이 Q/K norm을 보존하는지 확인한다.
3. `GroupedQueryAttention`에 causal mask만 먼저 구현한다.
4. cache 없는 logits를 고정한 뒤 KV cache 경로를 추가해 parity를 검사한다.
5. `SwiGLU`, `DecoderBlock`, `CausalLM`을 조립한다.
6. tied embedding의 고유 parameter 수를 계산한다.

```bash
uv run llmex model inspect --config configs/model/smoke.yaml
uv run pytest -q tests/test_m3_model.py
```

미래 token을 바꿔도 이전 위치 logits가 변하지 않고, cache/no-cache greedy token이 같아야 한다.

## 5단계. 결정적 사전학습과 완전 재개

1. `TokenShardDataset`과 `DeterministicBatchSampler`를 구현한다.
2. optimizer decay group과 warmup+cosine schedule의 경계값을 테스트한다.
3. CPU fp32 한 step부터 시작해 loss와 gradient 유한성을 확인한다.
4. RNG·sampler·optimizer·scheduler를 checkpoint에 저장한다.
5. N step 연속 학습과 K step+resume 학습의 parameter를 비교한다.
6. 안전 loader와 checkpoint audit를 추가한다.

```bash
uv run llmex train smoke --config docs/book/examples/pretrain-smoke.yaml
uv run llmex train audit --config docs/book/examples/pretrain-smoke.yaml
uv run pytest -q tests/test_m4_training.py
```

`latest.pt`가 존재한다는 사실만으로 완료하지 않는다. schema, 입력 fingerprint, state finite, scheduler/sampler step을 감사해야 한다.

## 6단계. 평가와 contamination

1. checkpoint+model+tokenizer를 strict하게 결속하는 `LoadedRuntime`을 만든다.
2. validation/test perplexity를 고정 batch로 계산한다.
3. cloze는 prompt와 candidate 결합 tokenization의 candidate offset부터 score한다.
4. canary exposure와 exact/near contamination을 별도 지표로 둔다.
5. 생성 반복률·distinct·EOS와 benchmark를 JSON/Markdown으로 원자 게시한다.

```bash
uv run llmex eval --config docs/book/examples/evaluation-smoke.yaml
uv run llmex generate --config docs/book/examples/evaluation-smoke.yaml --prompt "한국어는"
uv run llmex benchmark --config docs/book/examples/evaluation-smoke.yaml
uv run pytest -q tests/test_m5_evaluation.py
```

corpus나 canary 입력이 없으면 “0”이 아니라 `미실행`으로 기록하고 최종 gate는 실패-폐쇄한다.

## 7단계. Chat schema와 assistant-only mask

1. `Message`, `Provenance`, `ChatRow`의 role·license·source 계약을 만든다.
2. system/user/assistant marker와 EOS가 포함된 template을 렌더링한다.
3. 전체 token 중 assistant 응답과 EOS만 label로 남긴다.
4. 길이 초과 row를 조용히 자르지 않고 제외 사유로 기록한다.
5. public train/heldout의 prompt와 source overlap을 검사한다.

```bash
uv run pytest -q tests/test_g003_chat.py -k 'template or loader or mask'
```

한 row를 손으로 token별 출력해 input ID, label, role 구간을 표로 확인한다. PAD/user/system label은 모두 `-100`이어야 한다.

## 8단계. Offline teacher 증류 엔진

1. source row에서 `LogicalRequest` inventory를 먼저 만든다.
2. request ID를 prompt+source provenance+split 정책에서 결정적으로 계산한다.
3. 요청별 immutable spool과 전체 manifest/state를 분리한다.
4. fixture completion을 사용해 collect 중단과 resume를 검증한다.
5. rejection reason, accepted train/heldout export, 재검산 validate를 구현한다.
6. 마지막에만 no-redirect·timeout·byte-limit HTTP client를 붙인다.

```bash
uv run pytest -q tests/test_distill.py
uv run llmex distill --help
```

위 두 명령은 실제 endpoint를 호출하지 않는 offline 학습 경로다. 실제 teacher를 연결하는 별도 단계에서만 다음 live preflight를 실행한다.

```bash
uv run llmex distill preflight --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml
```

live preflight에서는 endpoint의 `/v1/models` identity와 응답 schema를 확인한다. 수집 도중 config나 source 파일을 바꾸지 않는다.

## 9단계. Public+teacher 혼합 데이터

1. public과 teacher의 train/heldout 네 입력을 immutable snapshot으로 읽는다.
2. teacher manifest SHA와 각 row provenance를 검증한다.
3. heldout 후보를 먼저 선택하고 그 prompt/source key를 train에서 금지한다.
4. token 길이·허가 license·민감 출력 조건을 적용한다.
5. preflight material과 실제 publish bytes가 같은지 validate한다.

```bash
uv run llmex sft preflight-mix --config <혼합-설정.yaml>
uv run llmex sft prepare-mix --config <혼합-설정.yaml>
uv run llmex sft validate-mix --config <혼합-설정.yaml>
uv run pytest -q tests/test_sft_mixer.py
```

완료 manifest에는 입력 네 개와 teacher manifest의 SHA, 선택/제외 사유별 수, split별 source 분포, overlap 0이 있어야 한다.

품질 평가가 실패하면 suite 문장을 데이터에 붙이지 않는다. 별도 `SFTCurriculumConfig`를 만들고 모든 user turn의 정규화 hash, provenance source, token 길이, assistant 민감 출력과 EOS label을 검증한 뒤 생성한다.

```bash
uv run llmex sft curriculum-preflight --config <보정-설정.yaml>
uv run llmex sft curriculum-prepare --config <보정-설정.yaml>
uv run llmex sft curriculum-validate --config <보정-설정.yaml>
uv run pytest -q tests/test_sft_curriculum.py
```

manifest에서 범주별 행 수만 보지 말고 `assistant_target_tokens` 비율을 계산한다. assistant-only SFT 손실은 행 수가 아니라 목표 token 수에 좌우되므로 긴 replay가 짧은 산술·EOS 예제를 압도하지 않아야 한다.

첫 보정 뒤에도 gate가 실패하면 결과의 실제 응답을 범주별로 읽고 다음 profile의 책임을 좁힌다. `focused-v2`는 인공 문항 번호를 제거하고 사실·산술·추출·형식·한국어·문맥·네 가지 안전 거절·정상 안전·불확실성·EOS·반복을 독립 범주로 분리한다. 이어지는 `focused-v3` 실습은 그 평가에서 실패한 한국어·문맥·불확실성·PII/secret·폭발물·EOS·지시만 남기고 원 정식 mix를 소량 replay한다.

```bash
uv run llmex sft curriculum-preflight --config configs/sft/qwen36mtp-v5-remediation-v3-data.yaml
uv run llmex sft curriculum-prepare --config configs/sft/qwen36mtp-v5-remediation-v3-data.yaml
uv run llmex sft curriculum-validate --config configs/sft/qwen36mtp-v5-remediation-v3-data.yaml
```

완료 증거는 train 4,350/heldout 435행, suite·split 모든 user turn overlap 0, source overlap 0, manifest fingerprint `de97a3cb…7238`이다. 새 profile을 추가할 때 기존 config에는 optional 값을 직렬화하지 않아 이전 fingerprint와 생성 bytes가 그대로 재검증되는 회귀를 먼저 작성한다.

학습 뒤에는 validation best 하나만 평가하지 않는다. 보존된 중간 checkpoint를 같은 suite·profile·seed로 재유도하고 correctness, safety, multi-turn의 망각을 비교한다. 실제 focused-v3에서는 step 200의 PPL이 가장 낮았지만 step 25의 correctness가 더 높았고 둘 다 gate를 통과하지 못했다. 이 비교를 다음 curriculum의 성공 범주 replay 비중과 중단 step 근거로 사용한다.

## 10단계. SFT 학습·재개·추론

1. 검증된 mix manifest SHA를 config에 고정하고 base checkpoint 경로를 지정한다. base SHA는 별도 config field가 아니라 runtime이 immutable bytes에서 계산해 fingerprint와 data manifest에 결속한다.
2. 전체 row를 두 번 tokenization해 digest를 확인한 뒤 연속 cache를 할당한다.
3. micro batch의 assistant target token 수로 loss를 가중한다.
4. validation subset과 best 기준을 고정한다.
5. pilot과 full run directory를 분리하고 둘 다 같은 base에서 fresh start한다.
6. 학습 전 preflight, 학습 뒤 eval/generate를 수행한다.

```bash
uv run llmex sft preflight --config <pilot.yaml> --measure-baseline
uv run llmex sft train --config <pilot.yaml>
uv run llmex sft eval --config <pilot.yaml> --checkpoint <pilot-best.pt>
uv run llmex sft generate --config <pilot.yaml> --checkpoint <pilot-best.pt> --prompt "안녕하세요"
uv run pytest -q tests/test_g003_chat.py
```

pilot checkpoint를 full에 resume하지 않는다. pilot은 설정·메모리·loss·checkpoint 주기를 검증하고, full은 동일 base에서 새 run으로 시작한다.

## 11단계. 자동 대화 품질 gate

1. checkpoint, SFT config, scenario suite 세 SHA를 quality config에 고정한다.
2. 정보·추론·안전·멀티턴 profile별 시나리오를 작성한다.
3. 실제 이전 assistant 응답을 다음 turn history에 넣어 rollout한다.
4. EOS, 반복, 빈 응답, 민감 출력, 지시 준수, contamination을 계산한다.
5. 전체 평균과 profile/scenario worst case를 모두 gate한다.

```bash
uv run llmex sft quality-preflight --config <quality.yaml>
uv run llmex sft quality-eval --config <quality.yaml>
uv run llmex sft quality-validate --config <quality.yaml>
uv run pytest -q tests/test_sft_quality.py
```

실패하면 “통과 기준을 낮추는” 대신 해당 row, decoding, data mix, 학습 step을 원인별로 수정하고 새 artifact SHA로 다시 평가한다.

## 12단계. 수동 blind review와 릴리스

1. 자동 gate 통과 artifact에서 blind review template을 만든다.
2. reviewer가 model identity를 모르는 상태로 정확성·관련성·한국어 자연스러움·안전을 채점한다.
3. disagreement는 독립 adjudicator가 처리한다.
4. 서로 다른 역할의 서명 statement와 target SHA를 검증한다.
5. release audit, build, checksum, SBOM, provenance를 만든다.
6. 법무·baseline·release gate는 실제 책임자의 외부 증거 없이는 통과시키지 않는다.

```bash
uv run llmex sft quality-review-template --config <quality.yaml>
uv run llmex sft quality-review-validate \
  --config <quality.yaml> \
  --repository . \
  --quality-review <quality-reviewer-1.json> \
  --quality-review <quality-reviewer-2.json> \
  --safety-review <safety-reviewer.json> \
  --adjudication <adjudication.json>
uv run llmex release audit
uv build
uv run llmex release bundle --output dist/reproducibility
```

`--adjudication`은 disagreement가 있을 때만 추가한다. 각 review path는 실제 독립 reviewer가 서명한 파일이어야 한다. 개발자가 만든 unsigned review나 자기 승인은 학습 기록일 수는 있어도 production 승인 증거가 아니다.

## Capstone 산출물 폴더

```text
data/
  raw/                 # 원 dump + 공식 checksum 근거
  processed/           # 정제 split + provenance
  chat/                # public, teacher, mixed chat JSONL
artifacts/
  tokenizer/           # tokenizer.json + manifest
  packed/              # token shards + manifest
runs/
  pretrain/            # base checkpoint와 학습 기록
  distill/             # request inventory, spool, export
  sft-pilot/           # 짧은 검증 실행
  sft-full/            # fresh full SFT
  quality/             # 자동·수동 품질 artifact
dist/
  reproducibility/     # wheel/sdist, checksum, SBOM, provenance
```

각 폴더의 manifest에는 upstream artifact SHA가 있어야 한다. 파일명 `latest`나 디렉터리 이름만으로 upstream을 선택하지 않는다.

## 장별 학습 기록표

| 단계 | 구현 commit | 입력 SHA | 설정 fingerprint | 테스트 | artifact SHA | 실패와 수정 |
|---|---|---|---|---|---|---|
| 0 기반 |  |  |  |  |  |  |
| 1 원자 I/O |  |  |  |  |  |  |
| 2 데이터 |  |  |  |  |  |  |
| 3 토크나이저 |  |  |  |  |  |  |
| 4 모델 |  |  |  |  |  |  |
| 5 사전학습 |  |  |  |  |  |  |
| 6 평가 |  |  |  |  |  |  |
| 7 chat |  |  |  |  |  |  |
| 8 증류 |  |  |  |  |  |  |
| 9 혼합 |  |  |  |  |  |  |
| 10 SFT |  |  |  |  |  |  |
| 11 자동 품질 |  |  |  |  |  |  |
| 12 수동·릴리스 |  |  |  |  |  |  |

## 최종 완주 판정

- [ ] CPU fixture와 전체 정적 품질 gate가 통과한다.
- [ ] 데이터→tokenizer→base→SFT→quality artifact SHA 사슬이 끊기지 않는다.
- [ ] pretrain과 SFT를 중단·재개해 연속 실행과 같은 상태를 얻는다.
- [ ] 실제 한국어 멀티턴에서 EOS·반복·안전 자동 gate를 통과한다.
- [ ] 독립 수동 review는 자동 gate 이후의 정확한 target을 평가한다.
- [ ] 외부 승인 부재를 로컬 성공으로 대체하지 않는다.

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
uv run llmex release audit
git diff --check
```

위 명령은 코드 품질과 도구 무결성을 증명한다. 실제 모델의 대화 품질은 11~12단계 artifact로 별도 증명해야 한다.
