# M4 학습 엔진 보고서

## 범위와 데이터 계약

학습 입력은 M2 `shards/manifest.json`이다. 각 shard는 열기 전에 SHA-256과 token 수를 검증하며 little-endian `uint16`/`uint32` memmap을 읽는다. context는 split의 전역 연속 token stream에서 뽑으므로 문서 끝 EOS와 shard 경계를 모두 보존한다. 모델에는 길이 `sequence_length` token window를 입력과 target으로 함께 전달하고 M3 모델이 내부에서 한 칸 shift한 next-token cross entropy를 계산한다.

train sampler는 `seed + epoch`의 CPU `randperm`을 사용하고 epoch와 cursor를 checkpoint에 저장한다. validation은 별도 seed와 sampler 상태를 사용해 train 순서와 독립적이다. 현재 production 재현 기준은 단일 프로세스 worker 0이며, prefetch worker의 미소비 queue 상태는 지원 범위에 넣지 않았다.

## 최적화와 정밀도

- AdamW decay group은 행렬 파라미터이며 embedding, RMSNorm 등 나머지는 no-decay다. tied embedding/LM head Parameter는 한 번만 등록한다.
- LR은 optimizer update 단위 선형 warmup 뒤 최저 LR까지 cosine decay한다.
- micro batch loss를 accumulation 횟수로 나눠 역전파하고 update 직전에 global norm clipping을 적용한다.
- `auto` 정밀도는 CUDA bf16 지원 시 bf16, 그 외 CUDA는 fp16, CPU/MPS는 fp32다. 명시적 bf16 CPU autocast를 지원하며 bf16에는 scaler를 쓰지 않는다. CUDA fp16에서만 GradScaler를 사용한다.
- train loss, LR, gradient norm, 누적 token, 처리량, 장치/정밀도와 CUDA peak allocation을 JSONL로 기록한다. validation NLL/perplexity와 고정 token prompt의 greedy 생성 token ID도 기록한다.

## checkpoint와 중단 복구

schema v1 checkpoint는 모델, optimizer, scheduler step, scaler, train/validation sampler, Python·NumPy·PyTorch CPU/CUDA RNG, step, best validation loss, 정밀도와 fingerprint를 포함한다. 임시 파일을 flush·`fsync`한 다음 atomic rename하고 디렉터리도 `fsync`한다. 보존형 `step-N.pt`, `latest.pt`, validation 최저점의 `best.pt`를 생성한다.

재개 시 config, corpus, tokenizer, model, shard manifest fingerprint를 모두 비교한다. 불일치, checksum 손상, schema 또는 필수 상태 누락은 무결성 오류로 즉시 거부한다. SIGTERM handler는 현재 optimizer update를 마친 뒤 checkpoint와 중단 metric을 남긴다. loss 또는 gradient norm NaN/Inf는 step과 batch/gradient 진단을 `failure.json`에 남기고 실패한다.

## CLI

```bash
uv run llmex train run --config configs/training/smoke.yaml
uv run llmex train resume --config configs/training/smoke.yaml
uv run llmex train resume --config configs/training/smoke.yaml --checkpoint runs/smoke/checkpoints/step-00000025.pt
uv run llmex train smoke --config configs/training/smoke.yaml
```

설정의 shard 경로는 먼저 M2 pack 결과를 가리켜야 한다. 저장소의 smoke 설정은 표준 경로 계약을 보여 주며 데이터 artifact 자체는 Git에 포함하지 않는다.

## 자동 검증

- shard 사이를 가로지르는 window와 손상 shard checksum 거부
- sampler cursor/epoch 완전 복구와 동일 다음 batch
- AdamW group 중복 없음과 warmup/cosine 경계값
- 두 micro batch accumulation과 하나의 큰 batch update 수치 동등성
- 연속 학습과 step checkpoint 재개의 모델 state bitwise 동일성
- config fingerprint 충돌, 손상 checkpoint와 NaN loss 오류주입
- CPU 50-step loss 감소와 train/resume/smoke CLI E2E
- bf16 가능 CUDA 장치의 실제 학습 smoke

최종 명령별 결과는 `docs/history.md` M4 마감 검증 기록에 보존한다.
