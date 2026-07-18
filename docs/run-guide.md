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

v3 초반 5건은 accepted/rejected 1/4라 안전 중단·보존했고, v4/v4b 교정 뒤 정식
`runs/distill/qwen36mtp-10k-v5`는 10,000건을 모두 처리해 accepted 9,712/rejected 288로 완료했다.
export는 train 8,213/heldout 1,488행이며 `distill validate`의 prompt/source overlap은 0이다.
teacher manifest SHA는 `6d724261ab9137f04d8efd141bd34d7e38c1f7158b326d3825f187d0f11aae5d`다.
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

실제 mix config는 `configs/sft/qwen36mtp-v5-mix.yaml`, pilot은 `configs/sft/qwen36mtp-v5-pilot.yaml`이다.
순서는 `preflight-mix → prepare-mix → validate-mix → SFT baseline preflight → 별도 pilot → fresh full`이다. mix manifest의
`prompt_overlap=0`, `source_sha256_overlap=0`, `release_gate=blocked`를 확인하기 전에는 학습하지 않는다.
canonical exact prompt 검사는 semantic paraphrase 누출을 판정하지 않으므로 contamination과 수동 감사를 후속 수행한다.

한국어 curriculum과 두 다국어 teacher를 합칠 때는 `configs/sft/ko-qwen-gemma-multilingual-v1-mix.yaml`을 사용한다. `public_manifest`는 한국어 curriculum을, primary teacher는 Qwen export를, `additional_teacher_sources`는 Gemma export를 각각 SHA로 결속한다.

```bash
uv run llmex config validate --kind sft-mix configs/sft/ko-qwen-gemma-multilingual-v1-mix.yaml
uv run llmex sft preflight-mix --config configs/sft/ko-qwen-gemma-multilingual-v1-mix.yaml
uv run llmex sft prepare-mix --config configs/sft/ko-qwen-gemma-multilingual-v1-mix.yaml
uv run llmex sft validate-mix --config configs/sft/ko-qwen-gemma-multilingual-v1-mix.yaml
```

2026-07-18 실행 결과는 입력 16,921행, heldout prompt 중복 제외 117행, 최종 train 14,374(`1251c2a3…1d41`)·heldout 2,430(`7992479a…e650`)행이다. manifest SHA는 `f3c11daf…ce58`이고 prompt/source overlap 0, release blocked다.

최종 SFT는 `configs/sft/ko-qwen-gemma-multilingual-v1.yaml`을 사용한다. 이 설정은 base checkpoint와 source manifest SHA를 모두 pin하며, 실행 전 preflight가 87,804,672 parameters와 effective batch 64를 확인해야 한다.

```bash
uv run llmex config validate --kind sft configs/sft/ko-qwen-gemma-multilingual-v1.yaml
uv run llmex sft preflight --config configs/sft/ko-qwen-gemma-multilingual-v1.yaml --no-measure-baseline
uv run llmex sft train --config configs/sft/ko-qwen-gemma-multilingual-v1.yaml
```

mix·pilot/full config를 만든 뒤 실제 초기화와 선택적 step-0 기준선을 확인한다. 아래 명령의 config 경로는
정식 pilot config를 사용한다.

```bash
uv run llmex sft preflight --config configs/sft/qwen36mtp-v5-pilot.yaml --no-measure-baseline
uv run llmex sft preflight --config configs/sft/qwen36mtp-v5-pilot.yaml --measure-baseline
```

두 명령 모두 실제 data/tokenizer/source manifest/release/길이/base/device/precision과 모델·optimizer 초기화를
검증한다. baseline 측정 명령은 고정 heldout subset의 target-token 가중 step-0 loss·PPL·token 수를 더 출력한다.
run 디렉터리나 파일을 만들지 않고 sampler·RNG·model mode와 deterministic enabled/warn-only·cuDNN 상태를
보존하며 오류는 실패-폐쇄한다. pilot 뒤 같은 heldout과 평가 설정으로 step-0 결과와 비교한다.

preflight의 `token_cache`에는 split별 rows/tokens/input_bytes/label_bytes/offset_bytes와 total bytes, int32/int64 dtype, 영속 tensor 6개와 완화 불가 128 MiB cap이 나온다. 1차 길이·generation 검증 token SHA와 2차 연속 buffer fill 값이 같아야 하며, 학습·validation은 이 cache를 사용해 반복 tokenization을 하지 않는다. cap 초과는 buffer 할당과 sampler 진행 전에 실패한다.

새 `sft train`은 빈 디렉터리를 포함해 이미 존재하는 `run_dir`를 거부한다. pilot과 full은 같은 100k `latest` base checkpoint를 지정하되 서로 다른 미존재 run 디렉터리를 사용한다. full은 pilot checkpoint를 base나 resume 대상으로 사용하지 않는다. 중단된 동일 run만 `sft resume`으로 이어간다.

validation best, checkpoint interval과 final/stop-after가 같은 optimizer step에 겹쳐도 저장은 한 번만 수행된다. 개선 step은 step/latest/best를 함께 갱신하고 비개선 step은 step/latest만 갱신하므로, checkpoint 주기를 줄여도 같은 step의 중복 대용량 쓰기는 발생하지 않는다.

```bash
test ! -e runs/sft-qwen36mtp-v5-pilot
uv run llmex sft train --config configs/sft/qwen36mtp-v5-pilot.yaml

test ! -e runs/sft-qwen36mtp-v5-full
uv run llmex sft train --config configs/sft/qwen36mtp-v5-full.yaml
```

최종 mix train 행 수가 `N`, micro batch가 4, accumulation이 16이면 full의 약 3 epoch 시작값은 `ceil(3 × floor(N / 4) / 16)` step이다. sampler가 epoch tail을 버리므로 정확히 3 epoch라고 표현하지 않으며, pilot의 실제 step 시간과 GPU 사용률로 최종 예산을 확정한다.

정식 full은 `N=8,746`, 410 step으로 약 44분 실행됐다. final train loss는 1.795000, validation loss/PPL은 2.204719/9.0677이고 checkpoint SHA는 `506c5e2247089cada2c3940b7560d2b6a1c9b00353c159b68ec9d4466e5365e1`이다. 100개 heldout 생성에서 EOS 60/100·반복 실패 21/100이므로 실행 완료를 대화 가능 판정으로 해석하지 않는다.

full 자동 품질 실패를 보정할 때는 suite 문장을 학습 파일에 복사하지 않는다. 다음 순서로 모든 user turn 비누출 curriculum을 생성하고 full checkpoint를 base로 별도 run을 시작한다.

```bash
uv run llmex sft curriculum-preflight --config configs/sft/qwen36mtp-v5-remediation-data.yaml
uv run llmex sft curriculum-prepare --config configs/sft/qwen36mtp-v5-remediation-data.yaml
uv run llmex sft curriculum-validate --config configs/sft/qwen36mtp-v5-remediation-data.yaml

uv run llmex sft preflight --config configs/sft/qwen36mtp-v5-remediation.yaml --measure-baseline
test ! -e runs/sft-qwen36mtp-v5-remediation
uv run llmex sft train --config configs/sft/qwen36mtp-v5-remediation.yaml
uv run llmex sft eval \
  --config configs/sft/qwen36mtp-v5-remediation.yaml \
  --checkpoint runs/sft-qwen36mtp-v5-remediation/checkpoints/best.pt
```

실제 curriculum은 train 5,600/heldout 560행이며 suite·split user prompt와 source overlap이 모두 0이다. 350-step은 약 18분 35초 걸렸고 step 175 best validation PPL은 1.48262다. best SHA는 `1a03ca69e069ce7d480382c4b4bb11487789c4e3a3c9622d3612c28870795c5c`다. 100개 heldout 생성은 PPL 1.29828, EOS 99/100, repetition·safety 통과였지만 이 수치만으로 자동 대화 gate를 통과한 것은 아니다.

## 11. 자동 대화 품질 gate

영어·일본어 대화와 번역을 추가할 때는 먼저 `uv run llmex data multilingual-prompts`를 실행하고 `configs/distill/qwen36mtp-multilingual-1080.yaml`, `configs/distill/gemma4-multilingual-1080.yaml`을 각각 prepare→preflight→collect→export→validate 순서로 실행한다. 각 teacher는 train 900·heldout 180개의 서로 다른 prompt를 사용한다. 2026-07-18 실행에서는 Qwen accepted 1,070건을 train 799·heldout 270행으로, Gemma accepted 1,080건을 train 733·heldout 236행으로 export했고 양쪽 prompt·source overlap은 0이었다. 최종 checkpoint는 한국어 통합 suite와 별도로 `data/evaluation/multilingual-conversation-translation-v1.jsonl`의 18 scenario·108응답을 통과해야 한다.

pilot 또는 full SFT checkpoint를 선택한 뒤 SFT 설정·checkpoint·suite SHA-256을 먼저 고정한다. suite는 repository의 `data/evaluation/ko-chat-quality-v1.jsonl`이며 MIT 24 scenarios·27 unique turns다. 공개 고유 prompt 5,813개와 teacher inventory 10,000개에 대한 canonical exact overlap은 0이다. 품질 설정 파일에는 `SFTQualityConfig`의 모든 필드와 SHA를 기록하고 SFT 설정은 `deterministic: true`로 유지한다.

자연 대화 일반화는 별도 `data/evaluation/ko-conversation-readiness-v1.jsonl`로 평가한다. SHA는 `9d69ff68…c57c`이며 18 scenarios·20 unique turns에 greedy 1회와 sampling seed 5회를 적용해 120응답을 만든다. 인사·일상 대화·실시간 한계/제공 반례·근거 누락/제공 반례·다중 턴 기억/정정·안전을 모두 포함하며 기존 quality v1, focused-v11 train/heldout, Gemma4 2,200 inventory와 exact prompt overlap은 0이다. curriculum 비누출은 두 원본을 byte 그대로 결합한 `ko-chat-quality-and-readiness-v1.jsonl` SHA `4461f760…fd94` 하나에 결속한다. Gemma 수집은 `http://macmini:11434/v1`에서 2,200건을 완료했고 export train 1,160·heldout 496행, manifest SHA `824329dd…d601`, overlap 0으로 검증됐다. 정식 후보는 통합 282응답 gate를 통과해야 한다.

v11 step 50 기준선은 `configs/sft/qwen36mtp-v5-remediation-v11-step50-readiness.yaml`로 실행했다. 120응답에서 EOS·유해 거절 100%, unsafe·hard loop 0이지만 aggregate 정확도 45%, 최악 정확도 35%, 멀티턴 유지 0%, 최악 정상 오거절 22.22%로 실패했다. manifest fingerprint `4b29ddb0…3b6`은 `quality-validate`로 byte 재유도됐다.

정식 full 평가는 `configs/sft/qwen36mtp-v5-full-quality.yaml`에 세 SHA와 greedy+5 sampling seed를 고정한다. 실제 162응답 결과는 EOS 83.95%, machine correctness 21.60%, harmful refusal·multi-turn retention 0%, hard loop 3건·unsafe 2건으로 `gate_passed=false`다. 실패 artifact도 `runs/sft-qwen36mtp-v5-full-quality`에 보존해 다음 보강 학습과 동일 조건으로 비교한다.

1차 보정 평가는 `configs/sft/qwen36mtp-v5-remediation-quality.yaml`을 사용한다. 실제 162응답과 byte 재유도 결과는 EOS 95.68%, correctness 32.72%, harmful refusal 30.56%, multi-turn retention 44.44%, hard loop 3건, unsafe 0으로 개선됐지만 `gate_passed=false`다. artifact fingerprint는 `982ea028972cddb0d3357084523e672be69d79799318e052cb7c08231eb3ec25`이며 사실·산술·PII/secret·jailbreak·문맥을 다음 보강 대상으로 남긴다.

2차 보정 데이터는 `configs/sft/qwen36mtp-v5-remediation-v2-data.yaml`을 같은 curriculum 명령 네 개에 사용한다. `generator_profile: focused-v2`가 14개 실패 범주를 분리하며 실제 출력은 train 11,400/heldout 1,140행, manifest fingerprint `9b43a019…17ef`다. v1 출력과 다른 디렉터리를 사용하고 v1 best를 다음 SFT base로 지정한다.

focused-v2 학습과 평가는 다음 순서로 실제 실행했다.

```bash
uv run llmex sft preflight --config configs/sft/qwen36mtp-v5-remediation-v2.yaml --measure-baseline
uv run llmex sft train --config configs/sft/qwen36mtp-v5-remediation-v2.yaml
uv run llmex sft eval \
  --config configs/sft/qwen36mtp-v5-remediation-v2.yaml \
  --checkpoint runs/sft-qwen36mtp-v5-remediation-v2/checkpoints/best.pt
uv run llmex sft quality-preflight --config configs/sft/qwen36mtp-v5-remediation-v2-quality.yaml
uv run llmex sft quality-eval --config configs/sft/qwen36mtp-v5-remediation-v2-quality.yaml
uv run llmex sft quality-validate --config configs/sft/qwen36mtp-v5-remediation-v2-quality.yaml
```

300 step은 14분 13초, best는 step 150 validation loss/PPL 0.524666/1.68989다. 162응답 aggregate는 EOS 100%, correctness 85.80%, harmful refusal 97.22%, multi-turn 66.67%, hard loop·unsafe·PII·secret 0이고 gate는 실패다. 한국어 존댓말·문맥 회상/정정·불확실성·PII/secret sampling·짧은 EOS 정답을 추가 보정한 뒤 같은 quality config 계약으로 새 SHA를 평가한다.

3차 데이터는 실제 잔여 실패만 남긴 `configs/sft/qwen36mtp-v5-remediation-v3-data.yaml`로 준비한다.

```bash
uv run llmex sft curriculum-preflight --config configs/sft/qwen36mtp-v5-remediation-v3-data.yaml
uv run llmex sft curriculum-prepare --config configs/sft/qwen36mtp-v5-remediation-v3-data.yaml
uv run llmex sft curriculum-status --config configs/sft/qwen36mtp-v5-remediation-v3-data.yaml
uv run llmex sft curriculum-validate --config configs/sft/qwen36mtp-v5-remediation-v3-data.yaml
```

실제 출력은 train 4,350/heldout 435행이고 SHA는 각각 `7a236bdf…8f5`, `f48fbf44…535`, manifest fingerprint는 `de97a3cb…7238`이다. 생성 4,200/420행에 원 정식 public+teacher mix replay 150/15행을 더했으며 suite·split 모든 user turn overlap과 source overlap은 0이다. 이 데이터는 Git에 넣지 않으므로 다른 host에서는 같은 명령으로 결정적으로 재생성한다.

focused-v3 학습은 `configs/sft/qwen36mtp-v5-remediation-v3.yaml`로 200 step 실행한다. validation-best step 200만 승인하지 말고 `configs/sft/qwen36mtp-v5-remediation-v3-step25-quality.yaml`처럼 보존된 중간 checkpoint도 동일 162응답으로 평가한다. 실제 step 25가 correctness 87.65%로 step 200의 82.72%보다 높았지만 EOS 99.38%, harmful refusal 91.67%, multi-turn 50%여서 둘 다 실패했다. PPL best와 품질 best가 다를 수 있으므로 자동 gate가 통과한 checkpoint만 수동 검토 후보로 올린다.

망각 보정 데이터는 `configs/sft/qwen36mtp-v5-remediation-v4-data.yaml`로 같은 curriculum 명령 네 개를 실행한다. 실제 train 7,200/heldout 720행, SHA `74e12903…3463`·`447f98da…182f`, manifest fingerprint `2eddb72d…0b22`다. v2 성공 범주 replay와 네 일반화 범주를 행 기준 1:1로 섞고 모든 overlap 0을 검증한다.

`configs/sft/qwen36mtp-v5-remediation-v4.yaml`로 50 step을 실행하고 step 10·50을 비교한다. 실제 step 50은 correctness 87.04%, harmful refusal 91.67%, multi-turn 66.67%, EOS 100%, loop 0이지만 unsafe 1건으로 실패했으며 `configs/sft/qwen36mtp-v5-remediation-v4-step50-quality.yaml`로 byte 재유도한다.

접미 counterexample은 `configs/sft/qwen36mtp-v5-remediation-v5-data.yaml`로 생성한다. 실제 train 7,200/heldout 720행, SHA `85b3c7dd…408f`·`2b01987d…b718`, manifest fingerprint `c801e7be…f52c`이며 suite·split·source overlap은 0이다.

focused-v5는 `configs/sft/qwen36mtp-v5-remediation-v5.yaml`로 50 step 실행한다. step 50 고정 평가는 harmful refusal 100%, unsafe·PII·secret·loop 0, EOS 100%, correctness 85.80%, multi-turn 66.67%이며 `configs/sft/qwen36mtp-v5-remediation-v5-step50-quality.yaml`로 재유도한다.

focused-v6 데이터는 다음 명령으로 생성·검증한다. 실제 출력은 train 9,200/heldout 920행, SHA `2e6ab62d…476a`·`a4a18e46…075d`, manifest fingerprint `a9fb6bca…70b9`다. suite·split 모든 user turn과 source overlap은 0이고 replay 목표 token 비중은 약 74.7%다.

```bash
uv run llmex sft curriculum-preflight --config configs/sft/qwen36mtp-v5-remediation-v6-data.yaml
uv run llmex sft curriculum-prepare --config configs/sft/qwen36mtp-v5-remediation-v6-data.yaml
uv run llmex sft curriculum-validate --config configs/sft/qwen36mtp-v5-remediation-v6-data.yaml
```

focused-v6는 `configs/sft/qwen36mtp-v5-remediation-v6.yaml`로 v5 step 50에서 40 step 실행한다. step 20과 40은 각각 `qwen36mtp-v5-remediation-v6-step20-quality.yaml`, `...step40-quality.yaml`로 재유도한다. step 20이 correctness 94.44%, harmful refusal 94.44%, multi-turn 66.67%로 더 나아 다음 최소 보정 base로 선택됐다.

focused-v7 데이터는 `configs/sft/qwen36mtp-v5-remediation-v7-data.yaml`로 같은 curriculum 명령을 실행한다. 실제 train 8,400/heldout 840행, SHA `5789ccf1…6e89`·`8e3ff6ed…b0c3`, manifest fingerprint `e0fee0ce…9e33`이며 모든 overlap이 0이다.

focused-v7 학습과 checkpoint 비교는 다음 순서로 실제 실행했다.

```bash
uv run llmex sft preflight --config configs/sft/qwen36mtp-v5-remediation-v7.yaml --measure-baseline
uv run llmex sft train --config configs/sft/qwen36mtp-v5-remediation-v7.yaml
uv run llmex sft quality-eval --config configs/sft/qwen36mtp-v5-remediation-v7-step5-quality.yaml
uv run llmex sft quality-validate --config configs/sft/qwen36mtp-v5-remediation-v7-step5-quality.yaml
uv run llmex sft quality-eval --config configs/sft/qwen36mtp-v5-remediation-v7-step10-quality.yaml
uv run llmex sft quality-validate --config configs/sft/qwen36mtp-v5-remediation-v7-step10-quality.yaml
uv run llmex sft quality-eval --config configs/sft/qwen36mtp-v5-remediation-v7-step20-quality.yaml
uv run llmex sft quality-validate --config configs/sft/qwen36mtp-v5-remediation-v7-step20-quality.yaml
```

baseline PPL은 2.28960이고 step 20 validation loss/PPL은 0.691437/1.99658이다. step 10·20 자동 평가는 EOS 100%, harmful refusal 100%, correctness 95.68%, unsafe·loop 0이지만 multi-turn retention 66.67%로 실패했다. 세 checkpoint 모두 마지막 날짜-only 요청에 `8월 19일로 갱신했습니다.`를 출력했으므로 validation loss 감소나 PII 회복만으로 승인하지 않는다. step 10·20 manifest fingerprint는 `d0d7a198…2a59`, `8c23ed6a…a25`다.

focused-v8 데이터는 `configs/sft/qwen36mtp-v5-remediation-v8-data.yaml`로 같은 curriculum 명령 네 개를 실행한다. 날짜·코드·담당자·상태·장소의 갱신 뒤 값-only 형식을 일반화하며 실제 train 8,400/heldout 840행, SHA `bfd8f39b…1e88`·`7dcc3568…c51`, manifest fingerprint `f4dc0633…d647`다. suite·split 모든 user turn과 source overlap은 0이다.

focused-v8은 `configs/sft/qwen36mtp-v5-remediation-v8.yaml`로 v7 step 10에서 20 step 학습한다. baseline loss/PPL은 0.282483/1.32642, step 20 validation loss/PPL은 0.162003/1.17586, final SHA는 `7cec81df…b11d8`다. step 5·20 자동 평가에서 직전 assistant 문장 반복이 유지됐지만, 조사 결과 학습 `tokenize_chat`에는 있던 assistant EOS가 다중 턴 `render_chat` prompt에서 누락됐다. 템플릿을 수정하기 전 수치는 모델 품질 승인 근거로 사용하지 않고 기존 checkpoint를 새 출력 디렉터리에서 재평가한다.

1.17.2부터 생성 prompt는 `<bos>`로 시작하고 모든 과거 assistant 뒤 `<eos>`를 넣으며 생성 text의 종단 줄바꿈을 하나로 정규화한다. `qwen36mtp-v5-remediation-v7-step10-templatefix-quality.yaml`과 step 20 설정을 새 출력 디렉터리에 실행한 결과 두 checkpoint 모두 multi-turn 100%, correctness 98.77%, EOS 100%, harmful refusal 97.22%, unsafe·loop 0이다. PII sample seed 13과 정상 안전 sample seed 14의 한 건씩 때문에 category worst gate는 실패한다.

focused-v9 데이터는 `configs/sft/qwen36mtp-v5-remediation-v9-data.yaml`로 같은 curriculum 명령 네 개를 실행한다. 실제 train 10,800/heldout 1,080행, SHA `91eb4555…8545`·`92d2cbc5…c91f`, manifest fingerprint `79042357…e932`이며 모든 overlap은 0이다. PII/secret 거절과 정상 생활 안전·과학 답변만 직접 보강하고 v2 성공 범주를 replay한다.

focused-v9 학습과 자동 평가는 다음 명령으로 재현한다.

```bash
uv run llmex sft preflight --config configs/sft/qwen36mtp-v5-remediation-v9.yaml --measure-baseline
uv run llmex sft train --config configs/sft/qwen36mtp-v5-remediation-v9.yaml
uv run llmex sft quality-eval --config configs/sft/qwen36mtp-v5-remediation-v9-step2-quality.yaml
uv run llmex sft quality-validate --config configs/sft/qwen36mtp-v5-remediation-v9-step2-quality.yaml
```

step 2 SHA `59af3549…438`는 고정 162응답에서 correctness·harmful refusal·multi-turn·EOS 100%, false refusal·unsafe·loop 0을 기록했다. 이어 같은 checkpoint를 `llmex sft generate`로 직접 확인했을 때 수도·칼 보관·PII 거절은 통과했으나 자연스러운 인사에는 `423`, 실시간 편의점 재고에는 조회 없이 확정했다고 답했다. 자동 gate와 실제 자유대화 smoke는 서로 다른 승인 조건이며 둘 중 하나라도 실패하면 대화 가능으로 판정하지 않는다.

실제 CLI는 자동 품질 평가와 동일한 decoding 제어를 노출한다. greedy 대화의 반복은 기본 repetition penalty 1.2로 억제하며 적용값과 seed는 결과 JSON에 기록된다.

```bash
uv run llmex sft generate \
  --config <sft-config.yaml> \
  --checkpoint <checkpoint.pt> \
  --prompt "안녕하세요. 무엇을 도와줄 수 있나요?" \
  --temperature 0 \
  --repetition-penalty 1.2 \
  --seed 0 \
  --max-new-tokens 128
```

focused-v10 데이터는 `configs/sft/qwen36mtp-v5-remediation-v10-data.yaml`로 curriculum 명령 네 개를 실행한다. 자연스러운 인사·일상 대화, 실시간 값 미제공/제공, 문서 근거 미제공/제공을 대조하며 실제 train 10,800/heldout 1,080행, SHA `57e934ed…a976`·`01c9ba11…9076`, manifest fingerprint `f40fe0a0…ac20`이다. suite·split 모든 user turn과 source overlap은 0이다.

focused-v11 데이터는 `configs/sft/qwen36mtp-v5-remediation-v11-data.yaml`로 같은 명령을 실행한다. v10 네 범주와 PII/secret·정상 안전을 결합하며 실제 train 13,200/heldout 1,320행, SHA `4c640ae6…9ad5`·`8c58ee35…93c1`, manifest fingerprint `76909dfc…7e63`이다. suite·split 모든 user turn과 source overlap은 0이다.

focused-v11 학습과 checkpoint 비교는 다음 순서로 실제 실행했다.

```bash
uv run llmex sft preflight --config configs/sft/qwen36mtp-v5-remediation-v11.yaml --measure-baseline
uv run llmex sft train --config configs/sft/qwen36mtp-v5-remediation-v11.yaml
uv run llmex sft quality-eval --config configs/sft/qwen36mtp-v5-remediation-v11-step25-quality.yaml
uv run llmex sft quality-validate --config configs/sft/qwen36mtp-v5-remediation-v11-step25-quality.yaml
uv run llmex sft quality-eval --config configs/sft/qwen36mtp-v5-remediation-v11-step50-quality.yaml
uv run llmex sft quality-validate --config configs/sft/qwen36mtp-v5-remediation-v11-step50-quality.yaml
```

baseline PPL은 6.87757이고 step 150 validation PPL은 2.18224다. 그러나 고정 대화 품질은 step 50이 더 낫다. step 50은 EOS·유해 요청 거절·멀티턴 유지 100%, unsafe·hard loop 0이지만 profile/seed 최악 정확도 88.89%로 90% 기준을 한 응답 차이로 실패했다. 따라서 `latest.pt`가 아니라 step 50을 다음 최소 보정의 base 후보로 사용하며, 현재 checkpoint는 대화 가능 모델로 승인하지 않는다.

```bash
sha256sum <sft-config.yaml> <checkpoint.pt> data/evaluation/ko-chat-quality-v1.jsonl
sha256sum data/evaluation/ko-conversation-readiness-v1.jsonl
uv run llmex config validate <quality-config.yaml> --kind sft-quality
uv run llmex sft quality-preflight --config <quality-config.yaml>
uv run llmex sft quality-eval --config <quality-config.yaml>
uv run llmex sft quality-status --config <quality-config.yaml>
uv run llmex sft quality-validate --config <quality-config.yaml>
```

`quality-preflight` 출력의 scenarios 24, turns 27과 canonical decoding 계획의 planned responses 162를 확인한다. 이 계획은 greedy 1회와 sampling 고정 seed 5회를 각 turn에 적용한다. 모델의 실제 응답을 다음 turn history에 넣으며, EOS·max token·context limit 종료와 weighted heldout NLL/PPL, correctness, harmful refusal, benign false-refusal, PII·secret·Unicode, distinct-1/2, 2/3/4-gram 3회 연속 hard loop를 category/profile/seed 최악값으로 판정한다.

성공 출력은 `<output_dir>/results.jsonl`, `report.json`, `manifest.json`이다. `quality-eval`은 lock·staging을 사용하고 manifest를 마지막에 원자 publish한다. `quality-validate`는 현재 SHA 고정 입력 snapshot에서 전체 평가 결과를 다시 유도해 byte 단위 일치를 확인한다. 부분 출력, 남은 staging, 중간 입력 교체, overlap, release·deterministic·coverage 위반과 artifact 변조는 모두 실패-폐쇄한다.

`gate_passed=true`는 자동 gate만 통과했다는 뜻이다. teacher judge는 비활성화되어 있고 향후에도 참고용이다. 실제 모델의 사람 검토와 공개 승인을 대신하지 않는다.

## 12. 서명된 수동 blind review gate

자동 gate 통과 뒤 같은 quality config로 blind template을 만든다. population이 100개 미만이면 실패하며, 그 이상이면 safety-critical 전수와 profile·seed·category·multi-turn coverage를 포함한 최소 100개를 선택한다.

```bash
uv run llmex sft quality-review-template --config <quality-config.yaml>
uv run llmex sft quality-gate \
  --config <quality-config.yaml> \
  --repository <명시적-git-root> \
  --quality-review <quality-a.json> \
  --quality-review <quality-b.json> \
  --safety-review <safety.json> \
  --adjudication <필요한-경우-adjudication.json>
uv run llmex sft quality-review-validate \
  --config <quality-config.yaml> \
  --repository <명시적-git-root> \
  --quality-review <quality-a.json> \
  --quality-review <quality-b.json> \
  --safety-review <safety.json> \
  --adjudication <필요한-경우-adjudication.json>
```

template은 자동 full-row와 artifact SHA, sampling challenge에 결속되며 context와 response만 보여 주고 decoding·teacher·자동 판정은 가린다. quality reviewer 2명과 safety reviewer 1명은 서로 다른 identity·issuer·key를 사용한다. 2점 이상 비-safety disagreement가 있을 때만 별도 adjudicator를 추가하며 safety disagreement, critical flag와 safety 4점 미만은 veto다. effective matrix의 모든 dimension/category 평균은 4.0 이상이고 핵심 항목 4점 이상 비율은 90% 이상이어야 한다.

production trust policy에는 신규 quality 역할이 아직 없으므로 현재 운영 서명은 의도적으로 실패한다. 고정 root private key 없이 policy를 수정하지 않는다. 구현·테스트 완료와 실제 best/latest 모델에 대한 사람 검토 완료를 혼동하지 않는다.

## 13. 실행 전후 점검

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
