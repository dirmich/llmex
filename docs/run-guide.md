# 데이터 확보부터 학습·추론까지 실행 가이드

이 문서는 저장소 루트에서 한국어 Wikipedia dump를 확보하고 데이터 처리, 토크나이저 생성,
모델 검사, 학습, 평가와 추론을 순서대로 실행하는 절차다. 먼저 `uv sync --frozen`으로 잠긴
환경을 준비한다. 기존 산출물과 fingerprint가 충돌하면 원인을 확인하고 별도 경로를 사용하며,
무조건 `--force`로 덮어쓰지 않는다.

## 1. Wikimedia dump와 checksum

- 공식 dump:
  [kowiki-20260701-pages-articles-multistream.xml.bz2](https://dumps.wikimedia.org/kowiki/20260701/kowiki-20260701-pages-articles-multistream.xml.bz2)
- 공식 checksum 목록:
  [kowiki-20260701-sha1sums.txt](https://dumps.wikimedia.org/kowiki/20260701/kowiki-20260701-sha1sums.txt)
- 공식 SHA-1: `291b502dbdd54b4374e5614f34a9ca91089e1f98`
- 다운로드 후 고정한 SHA-256:
  `991b26eb4588d2eddafd472a3b7dd2a8503740fb3e6c46d14baeef60d83e5582`
- 예상 크기: `1,398,909,939` bytes

Wikimedia의 해당 dump 디렉터리는 SHA-1 목록을 제공한다. 위 SHA-256은 공식 URL에서 받은
파일을 2026-07-11에 로컬 계산해 `configs/data/sample.yaml`에 고정한 값이다. 다운로드 명령은
이 SHA-256이 다르면 실패한다.

```bash
uv sync --frozen
uv run llmex data download --config configs/data/sample.yaml \
  --output data/raw/kowiki-20260701-pages-articles-multistream.xml.bz2
uv run llmex fingerprint file \
  data/raw/kowiki-20260701-pages-articles-multistream.xml.bz2
```

다운로드 결과는 원본과 함께
`data/raw/kowiki-20260701-pages-articles-multistream.xml.bz2.manifest.json`에 기록된다.

## 2. 1,000문서 canary E2E

전체 처리를 시작하기 전에 같은 원본의 선두 1,000문서로 extract, clean, dedup, split, report와
감사 표본 생성을 한 번에 검증한다.

```bash
uv run llmex data sample-e2e --config configs/data/sample.yaml \
  --input data/raw/kowiki-20260701-pages-articles-multistream.xml.bz2 \
  --output-dir data/processed/canary-1000 \
  --max-documents 1000
```

주요 결과는 `data/processed/canary-1000/corpus-v1.jsonl.zst`, `data-manifest.json`,
`data-report.md`, `audit-sample.json`, `audit-sample.md`다. 다음 전체 실행 전에 보고서와 감사
표본을 확인한다.

## 3. 전체 데이터 extract, clean, dedup, split, report

전체 dump에서는 `extract`에 `--max-documents`를 지정하지 않는다. 각 단계는 압축 JSONL을 다음
단계로 넘기며, 최종 corpus 경로는 토크나이저 설정과 같은
`data/processed/corpus-v1.jsonl.zst`다.

```bash
uv run llmex data extract --config configs/data/sample.yaml \
  --input data/raw/kowiki-20260701-pages-articles-multistream.xml.bz2 \
  --output data/interim/extracted.jsonl.zst

uv run llmex data clean --config configs/data/sample.yaml \
  --input data/interim/extracted.jsonl.zst \
  --output data/interim/cleaned.jsonl.zst

uv run llmex data dedup --config configs/data/sample.yaml \
  --input data/interim/cleaned.jsonl.zst \
  --output data/interim/deduplicated.jsonl.zst

uv run llmex data split --config configs/data/sample.yaml \
  --input data/interim/deduplicated.jsonl.zst \
  --output data/processed/corpus-v1.jsonl.zst

uv run llmex data report --config configs/data/sample.yaml \
  --input data/processed/corpus-v1.jsonl.zst \
  --output data/processed/data-manifest.json
```

보고서는 `data/processed/data-manifest.json`과 `data/processed/data-manifest.md`에 생성된다.

## 4. 토크나이저 train, evaluate, pack

16k byte-level BPE는 train split만 학습하고 모든 split을 같은 토크나이저로 평가·패킹한다.

```bash
uv run llmex tokenizer train --config configs/tokenizer/bpe-16k.yaml
uv run llmex tokenizer evaluate --config configs/tokenizer/bpe-16k.yaml
uv run llmex tokenizer pack --config configs/tokenizer/bpe-16k.yaml
```

토크나이저는 `artifacts/tokenizers/bpe-16k/`에 생성되며, 학습 입력 manifest는
`artifacts/tokenizers/bpe-16k/shards/manifest.json`이다.

## 5. 모델 inspect

장기 학습 전 파라미터 수, weight tying과 가중치·AdamW 메모리 추정치를 기록한다.

```bash
uv run llmex model inspect --config configs/model/baseline-100m.yaml \
  --output artifacts/model/baseline-100m/inspect.json
```

## 6. smoke train과 resume

현재 smoke 학습·평가 설정은 호환 경로 `artifacts/tokenizer/kowiki-bpe-16k`를 참조한다. 새로 만든
16k 토크나이저를 그 경로에 연결한 뒤 50-step smoke를 실행한다.

```bash
mkdir -p artifacts/tokenizer
ln -sfn ../tokenizers/bpe-16k artifacts/tokenizer/kowiki-bpe-16k

uv run llmex train smoke --config configs/training/smoke.yaml
uv run llmex train resume --config configs/training/smoke.yaml \
  --checkpoint runs/smoke/checkpoints/latest.pt
```

첫 명령은 `runs/smoke/`에 metric과 `checkpoints/latest.pt`, `checkpoints/best.pt`를 만든다.
완료된 50-step checkpoint는 같은 설정으로 더 진행되지 않으므로, resume 명령은 실제 중단 복구
또는 `max_steps`를 늘린 별도 설정을 검증할 때 사용한다. 장기 CUDA 학습은 smoke와 평가가 통과한
뒤 `uv run llmex train run --config configs/training/baseline-100m.yaml`로 시작한다.

## 7. 장기 학습 checkpoint audit

100k 학습이 끝나면 평가 전에 완료 step, latest, best checkpoint를 엄격히 감사한다. 이 명령은
각 파일의 SHA-256, schema, config/corpus/model/shards/tokenizer fingerprint, optimizer·scheduler·
scaler·sampler·RNG 상태와 모델 tensor의 NaN/Inf 부재를 확인한다.

```bash
uv run llmex train audit --config configs/training/baseline-100m.yaml
```

audit가 통과해야 checkpoint를 baseline 평가 입력으로 사용한다. 현재 완료 step/latest는 100,000,
best는 82,000이다.

## 8. baseline eval, generate, benchmark

smoke 평가는 기존 설정을 사용한다.

```bash
uv run llmex eval --config configs/evaluation/smoke.yaml
uv run llmex generate --config configs/evaluation/smoke.yaml \
  --prompt "대한민국의 수도는"
uv run llmex benchmark --config configs/evaluation/smoke.yaml
```

100k baseline의 best checkpoint는 다음 명령으로 평가하고 생성한다.

```bash
uv run llmex eval --config configs/evaluation/baseline-100m.yaml
uv run llmex generate --config configs/evaluation/baseline-100m.yaml \
  --prompt "대한민국의 수도는"
uv run llmex benchmark --config configs/evaluation/baseline-100m.yaml
```

JSON·Markdown 결과와 checksum manifest는 각 run의 `evaluation/`에 생성된다. `eval`은
validation/test 손실과 품질 지표, `generate`는 생성 및 오염 지표, `benchmark`는 cache 추론
latency·처리량과 사용 가능한 경우 CUDA peak memory를 기록한다.

현재 baseline 설정의 `batch_size: 1`, `max_batches: 1` 결과는 실행 경로 확인용이다. canary
provenance와 corpus 경로를 설정하지 않으면 canary exposure, contamination, long train match는
미실행이며 최종 gate로 해석하지 않는다. 전체 평가에서는 해당 입력을 설정하고 split 전체,
생성·암기·오염·수동 품질을 별도로 검증한다.

100k latest의 전체 shard 평가는 `runs/baseline-100m/evaluation-full-latest`에 보존했다. validation은
4,223,967 predicted token, loss 2.553663, PPL 12.854105이고 test는 3,976,401 predicted token,
loss 2.549981, PPL 12.806864다.

## 9. teacher 10k 준비·수집·검증

full latest 평가와 SFT 시작 checkpoint 선택 뒤 로컬 qwen36mtp teacher를 확인하고 정식 v5 inventory를
준비한다. 실제 수집은 장시간 실행이므로 status로 진행률과 ETA를 확인하고 중단 시 resume한다.

```bash
uv run llmex config validate configs/distill/qwen36mtp-10k.yaml --kind distillation
uv run llmex distill preflight --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill prepare --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill status --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill collect --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill resume --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill export --config configs/distill/qwen36mtp-10k.yaml
uv run llmex distill validate --config configs/distill/qwen36mtp-10k.yaml
```

v3 초반 5건은 accepted/rejected 1/4라 안전 중단·보존했고, v4/v4b 교정 뒤 v5 30건 pilot은
accepted 28건(93.3%)으로 prepare부터 validate까지 통과했다. 정식 `runs/distill/qwen36mtp-10k-v5`는
현재 수집 중이므로 변하는 completed 수를 문서에 고정하지 않고 위 `distill status` 명령으로 확인한다.
collect 완료 전에는 정식 export/validate를 완료로 기록하지 않는다.
상세 설정, 재개, 보안과 내부 전용 라이선스 경계는 [teacher 증류 데이터 실행 가이드](teacher-distillation.md)를 따른다.

## 10. 공개·teacher SFT mix 준비

공개 데이터 자체 train/heldout 사이에 canonical prompt 152개가 겹치고, 공개 train과 teacher heldout
사이에도 658개 고유 prompt가 겹쳐 공개 train 879행이 영향을 받는다. 따라서 JSONL을 직접 이어 붙이지 않는다.
정식 export와 `distill validate` 완료 뒤 teacher `manifest.json`의 SHA-256을 새 mix config에 고정하고
다음 명령 계약으로 heldout prompt·원천, tokenizer 길이와 입력 결속을 검증한다.

```bash
uv run llmex sft preflight-mix --help
uv run llmex sft prepare-mix --help
uv run llmex sft status-mix --help
uv run llmex sft validate-mix --help
```

실제 mix config와 pilot/full SFT config는 export가 완료되어 경로와 manifest SHA가 확정된 뒤 만든다.
순서는 `preflight-mix → prepare-mix → validate-mix → 별도 pilot → fresh full`이다. mix manifest의
`prompt_overlap=0`, `source_sha256_overlap=0`, `release_gate=blocked`를 확인하기 전에는 학습하지 않는다.
canonical exact prompt 검사는 semantic paraphrase 누출을 판정하지 않으므로 contamination과 수동 감사를 후속 수행한다.

## 11. 실행 전후 점검

명령 계약은 각 단계의 `--help`로 확인하고 문서 변경 뒤 Markdown 링크와 공백 오류를 검사한다.

```bash
uv run llmex data --help
uv run llmex tokenizer --help
uv run llmex model --help
uv run llmex train --help
uv run llmex eval --help
uv run llmex generate --help
uv run llmex benchmark --help
uv run llmex sft --help
uv run llmex distill --help
git diff --check -- docs/
```

데이터 라이선스·고지 경계는 [데이터 카드](data-card.md), 장애와 복구 절차는
[운영 runbook](operations-runbook.md), 장기 baseline gate는 [M6 runbook](baseline-runbook.md)을
함께 확인한다.
