# 학습·추론·평가 모듈 구현 교재

이 문서는 packed token shard에서 결정적 사전학습을 수행하고, checkpoint를 tokenizer·모델 형상과 결속해 평가 artifact까지 만드는 과정이다. “파일이 존재한다”가 아니라 중단·재개 동등성, 안전 로드, 입력 fingerprint, 유한 tensor, 원자 게시를 완료 조건으로 삼는다.

## 1부. 결정적 사전학습

### `src/llmex/train/__init__.py`

- **책임:** M4 학습 패키지의 공개 진입점을 제한한다.
- **먼저 구현할 계약:** `Trainer`, `train`을 re-export하고 `__all__`에 고정한다.
- **단계별 구현:** ① data/runtime/checkpoint/engine 순으로 내부를 완성한다. ② engine의 두 심볼만 공개한다. ③ import가 학습이나 장치 선택을 시작하지 않는지 확인한다.
- **반드시 실패해야 할 사례:** import 순환, package import 시 run directory 생성, 내부 checkpoint helper를 우연히 공개하는 경우다.
- **관련 테스트와 명령:** `uv run python -c 'from llmex.train import Trainer, train'`; `uv run pytest -q tests/test_m4_training.py`.
- **완료 산출물:** Python 호출자가 사용할 `Trainer` class와 `train(config, resume=None)` 함수다.

### `src/llmex/train/data.py`

- **책임:** checksum 검증된 memmap shard를 하나의 연속 token stream으로 읽고, 완전 재개 가능한 결정적 batch 순서를 제공한다.
- **먼저 구현할 계약:** `TokenShardDataset(manifest_path, split, sequence_length)`, `window(start)`, `DeterministicBatchSampler(size, batch_size, seed)`, `next`, `state_dict`, `load_state_dict`, `batch(dataset, sampler)`다.
- **단계별 구현:** ① manifest와 split/shard 목록 구조를 검증한다. ② 각 shard 파일 SHA와 token 수를 확인해 read-only memmap으로 연다. ③ 누적 end offset과 `window_count=total-sequence_length+1`을 계산한다. ④ bisect로 shard를 넘나드는 window를 int64 tensor로 조립한다. ⑤ sampler는 `seed+epoch` CPU generator의 `randperm`과 batch-aligned cursor를 사용한다. ⑥ state load 시 key set, int/bool 구분, seed/epoch/cursor 범위를 검사한다.
- **반드시 실패해야 할 사례:** split 없음, shard SHA·길이 불일치, sequence보다 token이 적음, window index 범위 밖, dataset보다 큰 batch, state key 누락/추가, bool을 int로 허용, seed 불일치, cursor가 batch 경계 아님이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m4_training.py -k 'shard_boundary_window_sampler_state'`.
- **완료 산출물:** shard 경계를 투명하게 가로지르는 `[sequence_length]` tensor와 checkpoint 가능한 sampler state다.

### `src/llmex/train/optim.py`

- **책임:** tied parameter를 중복 없이 AdamW decay/no-decay group으로 나누고 warmup+cosine learning rate를 계산한다.
- **먼저 구현할 계약:** `parameter_groups(model, weight_decay)`, `learning_rate(step, max_steps, config)`다.
- **단계별 구현:** ① `named_parameters()`를 순회하며 `requires_grad`와 object id 중복을 제거한다. ② 2차원 이상이면서 embedding weight가 아닌 parameter만 decay group에 둔다. ③ 나머지는 weight decay 0 group에 둔다. ④ warmup은 `(step+1)/warmup_steps`, 이후 cosine으로 minimum까지 내려간다. ⑤ progress를 0~1로 clamp한다.
- **반드시 실패해야 할 사례:** tied embedding/LM head를 두 번 최적화, embedding decay, warmup 첫 step 0 LR, 마지막 step이 min LR이 아님, warmup이 전체 step 이상일 때 division 오류다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m4_training.py -k 'adamw_groups_and_scheduler_boundaries'`.
- **완료 산출물:** 중복 없는 두 optimizer group과 step별 재현 가능한 LR 값이다.

### `src/llmex/train/runtime.py`

- **책임:** 장치·정밀도·난수·autocast 정책을 한 곳에서 확정한다.
- **먼저 구현할 계약:** `resolve_device`, `resolve_precision`, `seed_everything`, `autocast_context`다.
- **단계별 구현:** ① auto device를 CUDA→MPS→CPU 순으로 고른다. ② 요청 장치가 실제 지원되는지 검사한다. ③ auto precision은 CUDA bf16 가능 시 bf16, 그 외 CUDA fp16, 나머지 fp32로 정한다. ④ bf16/fp16 지원 범위와 GradScaler 사용 여부를 함께 반환한다. ⑤ Python·NumPy·PyTorch·모든 CUDA seed 및 deterministic algorithm/cudnn benchmark 정책을 설정한다. ⑥ fp32에는 nullcontext, 혼합 정밀도에는 `torch.autocast`를 반환한다.
- **반드시 실패해야 할 사례:** CUDA/MPS 미지원인데 선택, MPS fp16 학습 허용, 지원하지 않는 bf16, seed 중 일부만 설정, deterministic인데 cudnn benchmark 활성이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m4_training.py -k 'cpu_overfit or deterministic_resume'`; `uv run llmex train smoke --config docs/book/examples/pretrain-smoke.yaml`.
- **완료 산출물:** 실제 device, precision 이름, autocast dtype, scaler flag와 재현된 RNG 정책이다.

### `src/llmex/train/checkpoint.py`

- **책임:** 학습 전체 상태를 원자 저장하고 untrusted pickle code 실행 없이 immutable snapshot으로 로드·감사한다.
- **먼저 구현할 계약:** 상태 key 집합 `TRAIN_CHECKPOINT_REQUIRED_STATE`, `SFT_CHECKPOINT_REQUIRED_STATE`, `CHECKPOINT_REQUIRED_STATE`; `rng_state`, `restore_rng_state`, `atomic_save`, `save_checkpoint`, `load_checkpoint_bytes`, `load_checkpoint`, `validate_model_state`, `checkpoint_fingerprints`, `audit_checkpoints`다.
- **단계별 구현:** ① Python/NumPy/CPU/CUDA RNG를 직렬화 가능한 구조로 수집·복원한다. ② `torch.save` bytes를 같은 directory 임시 파일에 쓰고 fsync/replace한다. ③ step checkpoint를 저장하고 `latest.pt`, 개선 시 `best.pt`를 원자 복사하며 checksum sidecar를 쓴다. ④ load 시작 시 immutable bytes와 SHA를 snapshot으로 잡고 `torch.load(..., weights_only=True)`만 사용한다. ⑤ schema version, 정확한 required key set, expected fingerprints를 검사한다. ⑥ model key/shape/dtype/finite, optimizer param group/state, sampler cursor/expected position, scheduler step, scaler 구조, RNG 길이와 CUDA device 수를 감사한다. ⑦ 완료 step pointer, latest/best SHA와 metrics의 validation step까지 교차 검증한다.
- **반드시 실패해야 할 사례:** 악성 pickle, SHA가 다른 latest/best, config/corpus/tokenizer/model/shard fingerprint 불일치, NaN/Inf model·optimizer tensor, model key/shape/dtype 변조, scheduler-step 불일치, sampler cursor 오류, malformed fp16 scaler, CUDA RNG state 개수·정확한 byte 길이 불일치다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m4_training.py -k 'checkpoint or audit or malicious_pickle or corruption'`; `uv run llmex train audit --config docs/book/examples/pretrain-smoke.yaml`.
- **완료 산출물:** `step-NNNNNNNN.pt`, `latest.pt`, optional `best.pt`, checksum/pointer와 완전 재개 가능한 검증 상태다.

### `src/llmex/train/engine.py`

- **책임:** 모델·dataset·optimizer·scaler·검증·checkpoint를 한 결정적 상태 기계로 조립한다.
- **먼저 구현할 계약:** `Trainer(config)`의 `save`, `resume`, `validate`, `run`; 편의 함수 `train(config, resume=None)`다.
- **단계별 구현:** ① seed/device/precision을 확정하고 shard manifest fingerprint를 만든다. ② train/validation dataset과 서로 다른 고정 seed sampler를 만든다. ③ `CausalLM`, AdamW group, GradScaler를 초기화한다. ④ micro batch마다 loss를 accumulation step으로 나눠 backward하고 원 loss 평균을 기록한다. ⑤ step LR 적용→unscale→gradient clip/finite 검사→optimizer/scaler update 순서를 지킨다. ⑥ interval마다 JSONL train metric, validation loss/PPL, 고정 token 생성 표본을 fsync한다. ⑦ best/periodic/latest checkpoint를 저장한다. ⑧ SIGTERM은 flag만 세우고 현재 update 뒤 checkpoint와 중단 event를 남긴다. ⑨ resume는 optimizer/scaler/sampler/validation sampler/RNG/step/wall time을 모두 복구한다.
- **반드시 실패해야 할 사례:** train token 부족, non-finite loss/gradient를 계속 진행, accumulation loss scaling 누락, validation 중 train mode 유지, scheduler state가 step과 다름, SIGTERM에 checkpoint 없음, resume가 RNG/sampler 일부만 복원하는 경우다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m4_training.py -k 'gradient_accumulation or deterministic_resume or nan_diagnostic or cpu_overfit'`; `uv run llmex train run --config docs/book/examples/pretrain-smoke.yaml`; `uv run llmex train resume --config docs/book/examples/pretrain-smoke.yaml`.
- **완료 산출물:** `resolved-config.json`, `fingerprints.json`, `metrics.jsonl`, checkpoints와 step/loss/best/terminated 결과 dict다.

## 2부. 추론 runtime

### `src/llmex/inference/__init__.py`

- **책임:** checkpoint 추론의 공개 API를 runtime loader로 제한한다.
- **먼저 구현할 계약:** `LoadedRuntime`, `load_runtime`과 정확한 `__all__`다.
- **단계별 구현:** ① runtime 호환성 검사를 먼저 완성한다. ② dataclass와 loader만 re-export한다. ③ import 시 checkpoint를 읽지 않는지 확인한다.
- **반드시 실패해야 할 사례:** import만으로 device/checkpoint load, private resolve helper 공개, 순환 import다.
- **관련 테스트와 명령:** `uv run python -c 'from llmex.inference import LoadedRuntime, load_runtime'`; `uv run pytest -q tests/test_m5_evaluation.py`.
- **완료 산출물:** 평가와 별도 애플리케이션이 공유할 두 이름의 API다.

### `src/llmex/inference/runtime.py`

- **책임:** training config, shard manifest, tokenizer, checkpoint, model shape와 device를 엄격히 결속해 ready-to-eval runtime을 만든다.
- **먼저 구현할 계약:** frozen dataclass `LoadedRuntime(model, tokenizer, device, checkpoint, fingerprints, training)`, `resolve_device`, `load_runtime(config)`다.
- **단계별 구현:** ① evaluation config가 가리키는 training YAML을 strict load한다. ② shard/tokenizer manifest JSON을 읽는다. ③ training의 shard 경로와 평가 shard 경로가 같은지 확인한다. ④ tokenizer fingerprint가 shard fingerprint와 같고 vocab size/special ID가 model 계약과 같은지 확인한다. ⑤ config/corpus/tokenizer/model/shards fingerprint를 재계산한다. ⑥ required train state와 schema 1로 checkpoint를 안전 로드한다. ⑦ `CausalLM`에 state dict를 strict load한다. ⑧ checksum 검증 tokenizer를 읽고 device로 옮겨 eval mode로 만든다. ⑨ checkpoint SHA를 fingerprints에 추가한다.
- **반드시 실패해야 할 사례:** manifest 읽기/JSON 오류, training과 다른 shard, tokenizer/shard fingerprint 불일치, vocab/special ID 불일치, checkpoint fingerprint 또는 model shape 불일치, 요청 CUDA/MPS 미지원이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m5_evaluation.py -k 'e2e or limits'`; `uv run llmex generate --config docs/book/examples/evaluation-smoke.yaml --prompt '한국어는'`.
- **완료 산출물:** model/tokenizer/device/checkpoint/training과 모든 upstream SHA가 결속된 `LoadedRuntime`이다.

## 3부. 평가와 benchmark

### `src/llmex/evaluation/__init__.py`

- **책임:** M5 runner의 세 공개 작업을 노출한다.
- **먼저 구현할 계약:** `benchmark`, `evaluate`, `generate`와 `__all__`다.
- **단계별 구현:** ① runner 내부 helper를 먼저 검증한다. ② 세 함수만 re-export한다. ③ import가 runtime load나 artifact write를 하지 않게 한다.
- **반드시 실패해야 할 사례:** import side effect, helper를 공개 API로 약속, 세 함수 이름과 CLI 동작 불일치다.
- **관련 테스트와 명령:** `uv run python -c 'from llmex.evaluation import benchmark, evaluate, generate'`; `uv run pytest -q tests/test_m5_evaluation.py`.
- **완료 산출물:** root CLI `eval`, `generate`, `benchmark`가 호출할 공개 함수다.

### `src/llmex/evaluation/runner.py`

- **책임:** checkpoint 기반 NLL/PPL, 조건부 cloze, canary·contamination, 생성 품질과 latency/memory benchmark를 checksum 있는 JSON/Markdown으로 게시한다.
- **먼저 구현할 계약:** 고정 `FROZEN_CLOZE`; 공개 `generate`, `evaluate`, `benchmark`; 내부 `_generation`, `_generator`, `_finalize`, `_distinct`, `_repetition`, `_contamination`, `_conditional_score`, `_canary`다.
- **단계별 구현:** ① EvaluationConfig를 model `GenerationConfig`로 변환하고 device-local seeded generator를 만든다. ② `_finalize`가 payload fingerprint, JSON/Markdown, 두 파일 checksum manifest를 원자 게시하게 한다. ③ generation에서 prompt encode·문맥 제한을 검사하고 token IDs, EOS, context limit, repetition, distinct-1/2, Unicode 유효성을 기록한다. ④ 평가 split의 non-overlapping start에서 sum cross entropy를 누적해 NLL/token, PPL, NLL/byte, bits/byte를 계산한다. ⑤ cloze는 `prefix+candidate+suffix`를 한 번에 tokenize하고 character offsets와 겹치는 candidate token만 conditional mean log-likelihood로 score한다. ⑥ train corpus에서 exact와 bounded 문자 5-gram Jaccard contamination을 single pass로 측정한다. ⑦ canary provenance의 secret 후보 rank를 계산하고 threshold 이내면 gate 실패로 둔다. ⑧ benchmark는 warmup을 제외하고 CUDA synchronize 전후 latency, token/s, peak memory를 측정한다.
- **반드시 실패해야 할 사례:** 빈/인코딩 불가 prompt, max context 초과, 평가 token/decoded byte 0, BPE 경계에서 candidate만 따로 tokenize, corpus 없음 상태를 오염 0으로 위장, canary 파일 없음인데 gate 통과, 손상 canary schema·secret 후보 누락, benchmark prompt 없음이다.
- **관련 테스트와 명령:** `uv run pytest -q tests/test_m5_evaluation.py`; `uv run llmex eval --config docs/book/examples/evaluation-smoke.yaml`; `uv run llmex generate --config docs/book/examples/evaluation-smoke.yaml --prompt '한국어는'`; `uv run llmex benchmark --config docs/book/examples/evaluation-smoke.yaml`.
- **완료 산출물:** `generation-report.*`, `evaluation-report.*`, `benchmark-report.*`와 각 `.checksums.json`; upstream fingerprints, 지표, contamination/canary 상태가 포함된다.

## 묶음 완료 기준

1. `uv run pytest -q tests/test_m4_training.py tests/test_m5_evaluation.py`가 통과한다.
2. `uv run ruff check src/llmex/train src/llmex/inference src/llmex/evaluation tests/test_m4_training.py tests/test_m5_evaluation.py`가 통과한다.
3. 같은 seed에서 연속 N step과 K step+resume의 model·optimizer·sampler·RNG 상태 및 metric이 같다.
4. 악성 pickle과 checkpoint/model/manifest 한 byte 변조는 성공 경로에 들어가지 않는다.
5. `eval`, `generate`, `benchmark` JSON의 checkpoint SHA가 실제 파일 SHA와 같고 checksum manifest를 재계산할 수 있다.
6. corpus 또는 canary가 제공되지 않은 검사는 숫자 0이나 통과가 아니라 명시적인 `미실행`/실패-폐쇄 상태다.
