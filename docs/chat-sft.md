# 한국어 대화 SFT 실행 가이드

LLMEX 1.7.0은 Wikipedia 사전학습과 분리된 assistant-only 대화 학습과 공개·teacher 비누출 mix 경로를 제공한다. 전체 Wikipedia corpus/tokenizer와 100k baseline 학습을 완료했으며, 동일 조건 평가에서 100k `latest`를 SFT 시작점으로 선택했다. teacher 데이터는 [teacher 증류 데이터 실행 가이드](teacher-distillation.md)의 정식 v5 내부 전용 export 검증과 mix 검증을 모두 통과한 뒤에만 학습한다. SFT 실행이나 checkpoint 선택이 대화 품질 또는 외부 공개 승인을 대신하지 않는다.

## JSONL 계약

입력은 UTF-8 JSONL이며 빈 행을 허용하지 않는다. 각 행은 `schema_version=1`, 고유 `id`, `train` 또는 `heldout` split, 번갈아 나오는 `user`/`assistant` messages, provenance와 `sha256`를 포함한다. 선택적인 `system`은 첫 turn에만 둔다. provenance에는 dataset, 원 출처, license, `YYYY-MM-DD` 수집일이 필수다.

행 hash는 `id`, `messages`, `provenance`, `split`의 canonical JSON fingerprint다. loader는 파일 SHA-256, 행 hash, 중복 ID, split, 허용 license를 실패-폐쇄로 검증한다. runtime은 행 hash뿐 아니라 NFC·공백 정규화한 마지막 user prompt hash와 provenance source key도 train/heldout 사이에서 비교한다. 원문 라이선스를 직접 검토해 `allowed_licenses`에 명시해야 하며, 이 설정은 법률 자문이나 재배포 허가를 자동 생성하지 않는다.

## Template와 masking

고정 template는 `<|system|>`, `<|user|>`, `<|assistant|>` 역할 머리말과 줄바꿈을 사용한다. system/user/역할 머리말/padding은 label `-100`으로 마스킹하고 assistant 본문과 assistant EOS만 loss에 포함한다. 1.7.0 runtime은 train과 heldout의 모든 행을 미리 tokenization해 `sequence_length`를 넘는 행을 학습 전 거부하며 묵시적 truncation을 허용하지 않는다.

## 공개·teacher 결정적 mix

실측 결과 공개 instruction 자체의 train/heldout canonical prompt overlap은 152개다. 공개 train과 정식 v5 teacher heldout의 교차 overlap은 658개 고유 prompt이며 공개 train 879행이 영향을 받으므로 네 입력 파일을 단순 concat하지 않는다.

`SFTMixConfig`는 공개·teacher train/heldout, teacher export manifest와 그 예상 SHA-256, tokenizer, 출력 디렉터리, 허용 라이선스와 길이 gate를 받는다. `preflight-mix`는 출력 없이 입력 결속과 선택 결과를 계산하고, `prepare-mix`는 배타 lock과 staging에서 train/heldout/manifest를 만든다. `status-mix`와 `validate-mix`는 pending·ready 상태와 현재 입력에서 재유도한 byte/hash 일치를 확인한다.

```bash
uv run llmex sft preflight-mix --help
uv run llmex sft prepare-mix --help
uv run llmex sft status-mix --help
uv run llmex sft validate-mix --help
```

- 어느 입력에서든 heldout인 canonical prompt와 provenance source는 train보다 우선해 격리한다.
- 동일 source+prompt 중복과 heldout prompt 중복은 정렬된 hash 순서로 결정적으로 하나만 남긴다.
- prompt token과 생성 reserve 합 또는 전체 chat token이 `max_seq_len`을 넘으면 제외하고 사유별 수를 manifest에 기록한다.
- teacher export manifest SHA, train/heldout SHA·행 수, inventory/config/accepted spool fingerprint와 tokenizer manifest SHA를 고정한다.
- 내부 전용 teacher license가 포함되면 mix manifest, SFT checkpoint와 heldout 평가에 `redistribution_allowed=false`, `release_gate=blocked`가 계승된다.
- 부분 출력, 동시 실행, 변조된 manifest와 미완료 staging은 자동 복구·덮어쓰기 대신 실패-폐쇄한다.

정식 v5 export가 완료된 뒤 실제 teacher manifest SHA를 pin한 mix config와 별도 pilot/full SFT config를 작성한다. exact canonical prompt 검사는 의미가 같은 바꿔쓰기까지 판정하지 않으므로 semantic paraphrase leakage는 후속 contamination 검사와 수동 감사 대상이다.

## 시작 checkpoint 선택

100k `best`와 `latest`를 동일한 validation/test split별 128 batch와 같은 생성 평가 조건으로 비교했다.

| 100k checkpoint | validation PPL | test PPL | 평균 repetition | EOS 도달 |
|---|---:|---:|---:|---:|
| best | 13.288556 | 14.080648 | 0.549716 | 2/6 |
| latest | 13.178043 | 13.952660 | 0.529836 | 3/6 |

낮을수록 좋은 validation/test PPL과 평균 repetition, 높을수록 좋은 EOS 도달 수에서 모두 우세한 100k `latest`를 `base_checkpoint`로 선택한다. 이는 두 checkpoint 사이의 상대 선택이며 대화 품질 gate 통과를 뜻하지 않는다.

## 학습 설정

`configs/sft/smoke.yaml`의 경로, 모델 형상과 허용 라이선스를 실제 artifact에 맞춘다. 주요 학습 설정은 다음과 같다.

| 설정 | 의미 |
|---|---|
| `precision` | `auto`, `bf16`, `fp16`, `fp32` 중 하나다. `auto`는 CUDA bf16 지원 시 bf16, 그 밖의 CUDA에서는 fp16, CPU·MPS에서는 fp32를 선택한다. |
| `gradient_accumulation_steps` | 한 optimizer step에 누적할 micro-batch 수다. 각 micro-batch loss는 assistant target token 수로 가중된다. |
| `validation_interval` | 몇 optimizer step마다 heldout validation을 실행할지 정한다. 마지막 `max_steps`에서도 validation을 실행한다. |
| `validation_batches` | validation 한 번에 소비할 heldout batch 수다. |
| `checkpoint_interval` | 최신 진행 상태를 저장할 optimizer step 간격이다. |
| `max_steps` | 목표 optimizer step이다. 같은 run을 재개할 때 이 값만 늘릴 수 있다. |

bf16은 CUDA 또는 CPU에서 사용하며 gradient scaler를 사용하지 않는다. fp16은 CUDA 전용이고 gradient scaler를 사용한다. fp32는 autocast와 scaler를 사용하지 않는다. 지원하지 않는 장치·정밀도 조합은 학습 전에 중단한다.

`micro_batch_size × gradient_accumulation_steps`는 한 optimizer step의 batch 수를 결정한다. 누적 도중에는 checkpoint를 저장하지 않으며 optimizer 경계에서만 원자적으로 저장한다. `max_steps`를 늘려 재개하면 checkpoint에 저장된 원래 scheduler horizon을 유지하고, horizon을 지난 추가 step에서는 `min_learning_rate`를 유지한다.

## 실행

기존 사전학습 checkpoint는 `base_checkpoint`로 초기화한다. schema 1과 schema 2 checkpoint의 모델 가중치를 지원한다. immutable bytes SHA-256, schema/kind/step과 원 학습 fingerprint를 SFT fingerprint와 `data-manifest.json`에 결속한다. mix 입력은 `source_manifest`와 `expected_source_manifest_sha256`를 함께 지정해 mix 출력·길이 gate·release 상태를 추가 결속한다. 같은 경로의 파일이 다른 가중치로 바뀌거나 `weights_only` 역직렬화 실패, 비어 있거나 비유한 모델 tensor, 모델 형상 불일치가 있으면 중단한다.

```bash
uv run llmex config validate configs/sft/smoke.yaml --kind sft
uv run llmex sft train --config configs/sft/smoke.yaml
uv run llmex sft resume --config configs/sft/smoke.yaml
uv run llmex sft eval --config configs/sft/smoke.yaml --checkpoint runs/sft-smoke/checkpoints/latest.pt
uv run llmex sft generate --config configs/sft/smoke.yaml --checkpoint runs/sft-smoke/checkpoints/latest.pt --prompt "안녕하세요"
```

## validation과 checkpoint 선택

학습은 `validation_interval`마다 `validation_batches`개의 heldout batch에서 assistant-only token loss를 가중 집계하고 perplexity를 `metrics.jsonl`에 기록한다. 매 validation 전에 sampler를 같은 seed의 시작 상태로 되돌려 동일한 고정 subset과 순서를 평가하므로 step 간 validation loss와 `best.pt`를 같은 기준으로 비교한다.

- `checkpoints/latest.pt`: 가장 최근 optimizer 경계의 진행 상태다. 중단 복구와 연장 재개에 사용한다.
- `checkpoints/best.pt`: 지금까지 validation loss가 가장 낮아진 optimizer step의 상태다. validation 기준 모델 비교에 사용한다.
- `checkpoints/step-XXXXXXXX.pt`: 해당 optimizer step의 보존 checkpoint다.

최종 SFT 모델은 best/latest를 동일한 대화·EOS·repetition·safety·수동 평가 조건으로 비교한 뒤 선택한다. 파일 이름만으로 배포 모델을 결정하지 않는다.

## schema 2 완전 재개와 무결성 검사

schema 2 SFT checkpoint는 다음 상태를 원자적으로 저장한다.

- 모델, optimizer, scheduler와 fp16 scaler
- train sampler와 validation sampler의 epoch·cursor
- Python, NumPy, PyTorch CPU와 사용 가능한 CUDA RNG
- optimizer step, accumulation micro-step, 실제 확정 precision
- best validation loss와 누적 validation batch 수
- config, model, tokenizer, train, heldout fingerprint
- source mix manifest provenance와 redistribution/release 상태

재개 시 config fingerprint는 `max_steps`만 제외하고 비교하므로 같은 실행의 `max_steps`를 늘려 연장할 수 있다. 모델·토크나이저·데이터·optimizer 설정·precision 등 다른 설정을 바꾸면 fingerprint 또는 상태 검증에서 거부한다.

loader는 schema 2 전용 재개 상태의 필수 키, optimizer parameter group과 step tensor, scheduler step·원 horizon·연장 정책, train/validation sampler cursor, RNG 구조, accumulation 경계와 모델·optimizer tensor의 NaN/Inf 부재를 검사한다. `sft eval`과 `sft generate`도 같은 전체 strict 상태 검증을 통과한 checkpoint만 사용한다. source manifest를 사용하지 않던 기존 checkpoint는 기존 공개 상태로 재개할 수 있지만, mix checkpoint의 release blocked를 제거하거나 완화할 수 없다. 일부 상태만 복원하거나 모델만 정상인 손상 checkpoint를 평가·생성에 사용하는 것은 허용하지 않는다. checkpoint 복구 실패가 발생하면 즉시 중단하고 손상 파일을 우회해 부분 재개하지 않는다.

## 이후 gate

heldout 평가는 assistant-only NLL/perplexity와 생성별 반복률, 금지 문자열, EOS 도달을 기록한다. step-0 loss를 별도 기준선으로 비교하는 평가는 아직 설계 대기다. 이후 순서는 `정식 teacher export/validate → manifest SHA pin → mix config와 pilot/full config → mix 검증 → 별도 pilot → fresh full → 대화/EOS/repetition/safety/manual gate → GGUF/llama.cpp parity`다. 기능 smoke와 100k `latest` 선택은 독립적인 한국어 안전성 평가나 실제 사용자 배포 승인을 대신하지 않는다.
