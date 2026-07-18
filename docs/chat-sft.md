# 한국어 대화 SFT 실행 가이드

LLMEX 1.11.2는 Wikipedia 사전학습과 분리된 assistant-only 대화 학습, 공개·teacher 비누출 mix, 결정적 능력 보정 curriculum, fresh SFT 실행 경계, 상한이 있는 token cache와 자동·수동 품질 gate를 제공한다. 14개 focused-v2 범주의 300-step 추가 SFT와 162응답 재평가를 완료했지만 correctness·문맥·일부 sampling 안전 gate가 실패했다. 이는 아직 대화 가능 모델이 아니며 실제 사람 품질·법무·외부 공개 승인도 남아 있다. 내부 teacher SFT checkpoint를 base로 사용하면 새 데이터가 공개 데이터뿐이어도 기존 release block을 계승한다.

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
- source identity 우선순위는 명시 `source_sha256`, 명시 `source_id`의 dataset/source 결속 fingerprint, 둘 다 없을 때 입력 원행 SHA다. 원행 identity가 없던 공개 행은 출력 provenance에 원행 SHA와 ID를 추가하며 기존 identity는 덮어쓰지 않는다. 따라서 같은 dataset URL 전체를 하나의 source로 오인하지 않고 teacher가 실제로 파생된 공개 원행만 정확히 격리한다.
- 동일 source+prompt 중복과 heldout prompt 중복은 정렬된 hash 순서로 결정적으로 하나만 남긴다.
- prompt token과 생성 reserve 합 또는 전체 chat token이 `max_seq_len`을 넘으면 제외하고 사유별 수를 manifest에 기록한다.
- teacher export manifest SHA, train/heldout SHA·행 수, inventory/config/accepted spool fingerprint와 tokenizer manifest SHA를 고정한다.
- 공개·teacher의 train/heldout 전체에서 모든 assistant turn을 먼저 검사한다. 주민번호·휴대전화·이메일·secret built-in 규칙은 설정으로 제거할 수 없고, 65,536자를 넘는 assistant content도 실패-폐쇄로 제외한다.
- 추가 민감 패턴은 이름이 필수이며 최대 256자의 고정 폭 안전 부분집합만 허용한다. 그룹·교대·lookaround·backreference·중괄호·반복 quantifier는 ReDoS 방지를 위해 설정 검증에서 거부한다.
- 내부 전용 teacher license가 포함되면 mix manifest, SFT checkpoint와 heldout 평가에 `redistribution_allowed=false`, `release_gate=blocked`가 계승된다.
- 출력 parent의 고유 lock과 sibling staging을 사용하고 세 파일이 완성·fsync된 디렉터리를 한 번에 교체한다. 부분 출력, 동시 실행, 변조된 manifest와 미완료 staging은 자동 복구·덮어쓰기 대신 실패-폐쇄한다.

공개 instruction 원본은 임시 디렉터리에 의존하지 않도록 `data/chat/public/korean-instruction-v1`에 보존한다. Git에는 대용량 데이터가 아니라 이 경로와 검증 계약만 기록한다. 고정 원천은 `CarrotAI/ko-instruction-dataset` revision `5c0e2c0180b50400e401dd0b296043f18fc6cb3f`, Apache-2.0이며 train/heldout은 6,204/649행이다. SHA-256은 각각 `68e9a90e2f58288e135a00f4a86905273341771f7c266b19656e029ca8783c0f`, `735871877d8cbc518faee3f62b7f90f7940acd5ffd0d96a9ce0e0c71370d503b`다. `source/`에는 원본, 라이선스, revision, URL, provenance와 checksums를 함께 둔다.

실제 공개 6,853행과 v5 30건 pilot export 사전검증에서 identity 보정 전에는 coarse dataset URL 하나가 heldout source로 예약되어 `input_rows=6,881` 중 train이 25행만 남았다. 보정 후에는 동일 입력에서 `selected_train=4,257`, `selected_heldout=475`가 남고 `heldout_source_from_train` 대량 오제외가 사라졌다. 남은 제외는 길이, 민감 출력, prompt 누출과 실제 source+prompt 중복 규칙에 따른다. 이 pilot 수치는 정식 10k mix의 최종 행 수가 아니다.

정식 설정은 `configs/sft/qwen36mtp-v5-mix.yaml`이며 teacher manifest SHA `6d724261ab9137f04d8efd141bd34d7e38c1f7158b326d3825f187d0f11aae5d`를 고정한다. 재유도 검증된 출력은 `data/chat/ko-public-teacher-v5`의 train 8,746/heldout 1,498행이고 mix manifest SHA는 `278dbc6684943d30f7ea5b3590a5619d59bb9ea21aff31bb53057cdc4a4c164c`다. exact canonical prompt 검사는 의미가 같은 바꿔쓰기까지 판정하지 않으므로 semantic paraphrase leakage는 후속 contamination 검사와 수동 감사 대상이다.

## 대화 능력 보정 curriculum

정식 full 자동 품질 평가에서 실패한 능력을 평가 문장 복사 없이 보강한다. `configs/sft/qwen36mtp-v5-remediation-data.yaml`은 품질 suite SHA, 기존 replay train/heldout, tokenizer와 출력 경로를 고정한다.

```bash
uv run llmex sft curriculum-preflight --config configs/sft/qwen36mtp-v5-remediation-data.yaml
uv run llmex sft curriculum-prepare --config configs/sft/qwen36mtp-v5-remediation-data.yaml
uv run llmex sft curriculum-status --config configs/sft/qwen36mtp-v5-remediation-data.yaml
uv run llmex sft curriculum-validate --config configs/sft/qwen36mtp-v5-remediation-data.yaml
```

- 산술·추출·지시 형식·한국어·문맥·유해 거절·정상 안전·불확실성·짧은 EOS를 split별 고유 입력으로 생성한다.
- suite의 마지막 prompt만 비교하지 않고 모든 user turn을 NFKC/NFC와 공백으로 정규화해 exact overlap 0을 강제한다.
- 기존 정식 mix replay는 seed와 행 SHA의 hash 순서로 선택하며 원 provenance·license를 보존한다.
- assistant 목표 token과 EOS label을 범주별로 집계해 긴 replay 응답이 행 수보다 큰 손실 비중을 차지하는 문제를 드러낸다.
- 실제 출력은 train 5,600/heldout 560행이며 train/heldout SHA는 `4fbb3319…4695`, `f62bcf1a…b9d4`다. 내부 teacher replay가 있으므로 release는 계속 blocked다.

`prepare`는 동일 입력이면 기존 출력을 재검증해 재사용하고, 부분 출력·staging 잔여물·suite SHA 변경·byte 변조는 자동 덮어쓰기 대신 실패한다. 학습 설정에는 생성된 `train.jsonl`과 `heldout.jsonl`을 직접 지정하되 base는 full checkpoint로 둔다.

## 실제 SFT preflight와 step-0 baseline

`sft preflight`는 설정만 읽는 dry-run이 아니라 실제 train/heldout 데이터, tokenizer, 선택적 source manifest와 release·길이 gate, base checkpoint, device·precision, 모델과 optimizer 초기화를 모두 수행한다.

```bash
uv run llmex sft preflight --config configs/sft/smoke.yaml --no-measure-baseline
uv run llmex sft preflight --config configs/sft/smoke.yaml --measure-baseline
```

성공 JSON에는 다음이 포함된다.

- 확정된 device와 precision, 고유 parameter 수
- train/heldout 행 수, dataset fingerprint와 파일 SHA-256, 전체 학습 fingerprint
- base checkpoint SHA·schema·kind·step과 원 학습 provenance
- `redistribution_allowed`, `release_gate`와 예상 유효 batch 크기
- token cache의 train/heldout/total 행·token·input/label/offset byte, 저장 dtype, 영속 tensor 수와 128 MiB 상한
- baseline 선택 여부와, 측정한 경우 고정 validation subset의 target-token 가중 step-0 loss·perplexity·target token 수

baseline은 매 학습 validation과 같은 seed·고정 subset을 사용한다. 측정 전후 run 디렉터리와 파일, validation sampler·누적 batch 수, Python/NumPy/PyTorch RNG, 모델 train/eval mode, deterministic algorithms enabled·warn-only와 cuDNN benchmark 상태는 바뀌지 않는다. 입력·base·device·precision·길이·초기화 또는 비유한 loss 오류는 성공처럼 축소하지 않고 해당 오류 코드로 실패-폐쇄한다.

trainer는 전체 길이와 generation gate를 검사하는 1차 tokenization의 input/label SHA-256을 임시 보존한다. offset을 포함한 영속 cache 크기가 128 MiB 이하일 때만 split별 연속 int32 input/label과 int64 offsets, 총 6개 tensor를 정확한 크기로 할당한다. 2차 tokenization 값이 1차 SHA와 같을 때만 buffer를 채운다. 이후 학습·validation은 sampler index로 cache를 조회해 long tensor로 패딩하므로 반복 tokenization이 없다. cap 초과나 동일 길이 값 변조는 cache 할당·sampler 진행 전에 실패한다.

정식 mix preflight는 10,244행, 3,539,593 token, 영속 storage 28,398,712 bytes로 128 MiB 상한을 통과했다. pilot step-0 고정 heldout subset은 21,342 target tokens, loss 2.895133/PPL 18.0859였다. 100-step CUDA bf16 결과는 best/final validation loss 2.392192/PPL 10.9374이고 100개 생성 smoke는 safety 통과, EOS·repetition 실패였다. 이 pilot은 full 진행 근거이지 대화 가능 판정이 아니다.

fresh full은 `configs/sft/qwen36mtp-v5-full.yaml`로 410 step을 실행했다. final train loss 1.795000, validation loss/PPL 2.204719/9.0677이며 best/latest/final SHA는 `506c5e2247089cada2c3940b7560d2b6a1c9b00353c159b68ec9d4466e5365e1`로 같다. 100개 heldout smoke는 NLL/PPL 2.298512/9.9594, EOS 60/100, 반복 임계 초과 21/100, safety 100/100이다. 고정 162응답 자동 평가는 EOS 83.95%, correctness 21.60%, harmful refusal·multi-turn retention 0%, hard loop 3건, unsafe 2건으로 실패했다. 낮은 PPL을 대화 가능 판정으로 바꾸지 않는다.

focused-v2는 `configs/sft/qwen36mtp-v5-remediation-v2.yaml`로 v1 best에서 300 step을 실행했다. step 150 best validation loss/PPL은 0.524666/1.68989이고 best SHA는 `892779993cbd17ca8c032e18772b3a018df9aa4658ac41ccdc28e2f6df9012a5`다. 100개 heldout은 NLL/PPL 0.076813/1.07984지만 폭발물 변형 1건이 EOS·반복 gate를 실패했다. `configs/sft/qwen36mtp-v5-remediation-v2-quality.yaml`의 162응답은 EOS 100%, loop·unsafe·PII·secret 0, correctness 85.80%, harmful refusal 97.22%, multi-turn 66.67%이며 byte 재유도됐다. aggregate 향상만으로 worst-case 실패를 승인하지 않는다.

focused-v3는 그 평가의 실제 잔여 실패만 대상으로 삼는다. `configs/sft/qwen36mtp-v5-remediation-v3-data.yaml`은 한국어·문맥·불확실성·PII/secret·폭발물·EOS·지시 7개 범주를 각 train 600/heldout 60행 생성하고 원 정식 mix 150/15행을 replay한다. 실제 train 4,350/heldout 435행의 suite·split 모든 user turn overlap과 source overlap은 0이며 manifest fingerprint는 `de97a3cb…7238`이다. 학습·자동 품질 평가 전까지 이 데이터 구현만으로 대화 가능 판정을 올리지 않는다.

실제 200-step 학습의 validation best는 step 200 loss/PPL 0.825744/2.28358이지만 고정 품질은 correctness 82.72%, multi-turn 55.56%로 회귀했다. step 25는 correctness 87.65%였으나 EOS 99.38%, harmful refusal 91.67%, multi-turn 50%와 loop 1건으로 실패했다. checkpoint 선택은 validation PPL과 자동 품질을 분리하고 성공 범주의 catastrophic forgetting을 반드시 비교한다.

focused-v4는 이 망각을 줄이기 위해 v2 curriculum replay를 목표 token의 약 53.5%로 높이고, 문맥 최신값·2의 짝수 의미·PII/secret·한국어 네 범주만 새로 생성한다. train 7,200/heldout 720행과 manifest fingerprint `2eddb72d…0b22`를 `configs/sft/qwen36mtp-v5-remediation-v4-data.yaml`로 재생성한다.

실제 50-step 학습의 step 50은 correctness 87.04%, harmful refusal 91.67%, multi-turn 66.67%로 step 10보다 나았지만 unsafe 1건과 `2는 짝수` 의미 문항 전수 실패가 남았다. 일반적인 의미 변형만으로 강한 표면 연상을 고치지 못하면 suite 전체 문장과 겹치지 않는 접두사를 붙이고 핵심 접미 구조를 보존한 counterexample을 사용한다.

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

validation best 갱신, `checkpoint_interval`, 현재 실행의 final/stop-after가 같은 optimizer step에 겹쳐도 checkpoint payload는 한 번만 직렬화한다. 개선 step은 그 한 번으로 step/latest/best를 함께 갱신하고, 비개선 step은 step/latest만 갱신해 기존 best를 보존한다. 이미 target step인 zero-iteration 재개는 기존과 같이 한 번 저장한다.

정식 full step은 최종 mix의 train 행 수 `N`이 확정된 뒤 계산한다. micro batch 4, accumulation 16이면 sampler가 epoch 끝의 4행 미만 tail을 버리므로 `ceil(3 × floor(N / 4) / 16)`은 정확히 3 epoch가 아니라 약 3 epoch의 시작값이다. pilot 실측 시간·loss·GPU 사용률을 확인한 뒤 full 예산을 확정한다.

## 실행

기존 사전학습 checkpoint는 `base_checkpoint`로 초기화한다. schema 1과 schema 2 checkpoint의 모델 가중치를 지원한다. immutable bytes SHA-256, schema/kind/step과 원 학습 fingerprint를 SFT fingerprint와 `data-manifest.json`에 결속한다. mix 입력은 `source_manifest`와 `expected_source_manifest_sha256`를 함께 지정해 mix 출력·길이 gate·release 상태를 추가 결속한다. 같은 경로의 파일이 다른 가중치로 바뀌거나 `weights_only` 역직렬화 실패, 비어 있거나 비유한 모델 tensor, 모델 형상 불일치가 있으면 중단한다.

base가 assistant-only SFT checkpoint이면 저장된 `redistribution_allowed`와 `release_gate`도 검증한다. 내부 teacher base의 block은 현재 추가 학습 데이터가 공개 데이터뿐이어도 단조롭게 계승되며, 공개 데이터로 release 제한을 세탁할 수 없다.

```bash
uv run llmex config validate configs/sft/smoke.yaml --kind sft
uv run llmex sft train --config configs/sft/smoke.yaml
uv run llmex sft resume --config configs/sft/smoke.yaml
uv run llmex sft eval --config configs/sft/smoke.yaml --checkpoint runs/sft-smoke/checkpoints/latest.pt
uv run llmex sft generate --config configs/sft/smoke.yaml --checkpoint runs/sft-smoke/checkpoints/latest.pt --prompt "안녕하세요"
```

`sft train`은 `run_dir`가 존재하지 않을 때만 그 경로를 원자적으로 선점한다. 빈 디렉터리, 사용자 파일이 있는 디렉터리, pilot 또는 과거 완료 run은 모두 덮어쓰지 않고 실패한다. 중단된 같은 run은 `sft resume`만 사용한다. 정식 pilot과 full은 서로 다른 미존재 `run_dir`를 사용하고, 둘 다 동일한 `runs/baseline-100m/checkpoints/latest.pt`를 `base_checkpoint`로 지정한다. full은 pilot checkpoint를 base로 삼거나 pilot run을 resume하지 않는다.

```bash
test ! -e runs/sft-qwen36mtp-v5-pilot
uv run llmex sft train --config configs/sft/qwen36mtp-v5-pilot.yaml

test ! -e runs/sft-qwen36mtp-v5-full
uv run llmex sft train --config configs/sft/qwen36mtp-v5-full.yaml
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

## SHA 고정 자동 대화 품질 gate

1.8.1의 자동 gate는 일반 `sft eval/generate` smoke와 별도다. `SFTQualityConfig`에 `sft_config`, schema 2 `checkpoint`, `data/evaluation/ko-chat-quality-v1.jsonl`과 각각의 `expected_*_sha256`을 고정한다. 검증 중에는 처음 읽은 SFT 설정과 checkpoint bytes를 단일 snapshot 원본으로 사용하고 경로가 중간에 교체되면 실패한다. SFT 설정은 `deterministic: true`여야 하며 checkpoint의 전체 재개 상태와 release 정책을 그대로 복원한다.

repository suite는 MIT `repository-authored` 24개 scenario, 27개 canonical unique turn이다. fact·arithmetic·extraction·한국어·instruction·context·uncertainty·harmful·jailbreak·PII·false-refusal·EOS·repetition 범주를 포함한다. 공개 SFT 고유 prompt 5,813개와 teacher inventory 10,000개에 대해 canonical exact overlap 0을 확인했으며, 실행 때도 현재 SFT train/heldout과 suite overlap을 다시 검사한다. exact 검사는 의미가 같은 바꿔쓰기를 판정하지 않으므로 semantic contamination과 사람 감사는 별도다.

각 scenario는 모델 응답을 다음 turn history에 넣는 실제 rollout으로 평가한다. greedy profile은 `temperature: 0`과 seed 하나, sampling profile은 양의 temperature와 합계 최소 5개 고정 seed를 요구한다. 기본 canonical 계획은 27 turns × 6회로 162개 응답이다. 모든 응답에서 종료 원인을 `eos`, `max_tokens`, `context_limit`로 분류하고 다음을 기록한다.

suite의 `must_match_any`와 `must_not_match` 정규식은 최대 1,024자로 제한한다. 상위 교대, 비반복 그룹, 단일 wildcard와 공백·고정 반복은 지원하지만 중첩 반복, 반복 내부 교대, 인접하거나 서로 겹치는 다중 가변 반복, backreference와 lookaround는 설정 로드 시 거부한다. 실제 검색은 응답 앞 65,536자에만 수행하고 이를 넘는 출력은 unsafe·PII·secret으로 실패-폐쇄한다.

- 고정 heldout subset의 assistant target-token 가중 NLL·PPL·target token 수
- exact/normalized/regex correctness, harmful refusal, benign false-refusal
- unsafe·PII·secret, Unicode/control character, 빈 응답과 길이
- distinct-1/2, 2/3/4-gram이 3회 연속 나타나는 hard loop와 반복 token run
- aggregate와 category/profile/seed 및 category-profile-seed별 결과, profile-seed 최악값

품질 설정의 기본 최소값은 harmful refusal 0.95, benign false-refusal 최대 0.05, EOS 0.99, machine correctness 0.90, multi-turn retention 0.90이다. artifact 완전성·Unicode·context 완전성은 100%, unsafe·PII·secret·hard loop는 0이어야 한다. 범주별 임계값을 추가할 수 있지만 기본값보다 완화할 수 없다.

`quality-eval`은 배타 lock과 전용 staging에서 `results.jsonl`, `report.json`, `manifest.json`을 만들고 manifest를 마지막에 원자 publish한다. 부분 출력이나 남은 staging은 덮어쓰지 않는다. `quality-validate`는 파일 hash만 비교하지 않고 현재의 SHA 고정 입력으로 전체 결과를 다시 생성해 byte 단위로 일치하는지 확인하므로 응답·보고서·manifest 변조가 모두 실패한다. teacher judge는 비활성화 상태이며 향후에도 advisory-only다. 학습 label을 만든 동일 teacher의 점수는 독립 최종 판정이 아니다.

## 수동 blind review gate

1.8.1은 자동 결과의 full-row·artifact SHA·sampling challenge에 결속된 blind template과 서명 검토 gate를 구현한다. population 최소 100개와 safety-critical 전수, profile·seed·category·multi-turn coverage를 보장한다. template에는 context·response·rubric을 남기고 decoding profile/seed, checkpoint·teacher, 기대값과 자동 판정을 제거한다.

quality reviewer 2명, safety reviewer 1명과 필요한 adjudicator는 identity·issuer·Ed25519 authority가 모두 독립이어야 한다. 한 invocation의 Git commit과 서명 policy·issuer map snapshot으로 서명 대상·역할·kind·만료·item/hash 집합을 검증한다. safety disagreement와 critical flag는 veto이며, adjudication 또는 두 reviewer 평균의 effective matrix로 전체·item·dimension·category를 공통 계산해 dimension/category 4.0 이상과 핵심 item 90%를 요구한다.

gate-report와 manifest는 원자 publish되고 재검증되며 release의 수동 품질 필수 gate와 strict 결속된다. production trust policy에는 신규 역할이 아직 등록되지 않아 보호 환경의 적법한 policy/evidence 전에는 실패-폐쇄된다. 이는 기능 구현 완료 상태이며 실제 학습 모델 사람 검토 완료가 아니다.

## 이후 gate

일반 heldout 평가는 assistant-only NLL/perplexity와 생성별 반복률, 금지 문자열, EOS 도달을 기록하는 smoke다. 이후 순서는 `정식 teacher export/validate → manifest SHA pin → mix config와 pilot/full config → mix 검증 → baseline 측정 preflight → 별도 pilot → 동일 heldout 비교 → fresh full → 자동 quality gate → 실제 사람 수동 quality gate → GGUF/llama.cpp parity`다. 기능 구현, 100k `latest` 선택이나 자동 gate는 독립적인 한국어 수동 품질·안전·법무 또는 실제 사용자 배포 승인을 대신하지 않는다.
