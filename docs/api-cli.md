# API와 CLI 문서

공개 Python API는 `llmex.__version__`과 안정된 CLI 계약이다. 내부 모듈은 호환성을 보장하지 않는다.

| 명령군 | 목적 |
|---|---|
| `config`, `fingerprint`, `run` | 설정·입력·실행 identity |
| `data`, `tokenizer` | corpus와 token shard 생성 |
| `model`, `train` | inspect, private HF Llama·GGUF 내보내기, 학습, 재개, smoke |
| `sft` | 공개·teacher mix, 실제 SFT preflight, train/resume/eval/generate, SHA 고정 자동·서명 수동 품질 gate |
| `eval`, `generate`, `benchmark` | 품질·안전 평가와 추론 |
| `distill` | teacher preflight/prepare/collect/resume/status/export/validate |
| `pipeline` | preflight/run/status/drill/export |
| `release` | audit/bundle/gate |

사용자 출력과 오류는 한국어다. JSON 결과는 stdout, 로그는 stderr이며 종료 코드는 0 성공, 2 설정,
3 입력, 4 충돌, 5 무결성, 70 내부 오류다. option은 `llmex <명령> --help`로 확인한다.

## 모델 내보내기 CLI

| 명령 | 계약 |
|---|---|
| `llmex model export-hf` | SFT config와 checkpoint SHA·fingerprint·release 차단을 검증하고 private HF Llama 디렉터리를 0700/0600 권한으로 원자 게시한다. |
| `llmex model export-gguf` | 예상 HF manifest SHA와 모든 artifact SHA를 검증한 뒤 llama.cpp 공식 converter로 GGUF를 만들고 0600 권한으로 충돌 없이 게시한다. |

Q/K projection은 LLMEX의 인접쌍 RoPE 배열에서 HF Llama의 half-split 배열로 바꾼다. HF chat template는 학습과 같은 BOS, assistant EOS, trailing CR/LF 제거를 보존한다. GGUF는 현재 `f32`, `f16`, `bf16`, `q8_0`을 지원하지만, 모델 동등성 기준은 먼저 F16 Transformers/llama.cpp parity를 통과하는 것이다.

## SFT mix CLI

| 명령 | 계약 |
|---|---|
| `llmex sft preflight-mix --config <경로>` | 입력 JSONL, teacher manifest SHA, tokenizer 길이와 최종 split 선택을 출력 생성 없이 검증한다. |
| `llmex sft prepare-mix --config <경로>` | 배타 lock·staging에서 결정적 train/heldout/manifest를 원자 publish한다. |
| `llmex sft status-mix --config <경로>` | 출력이 없으면 pending, 현재 입력에 결속된 완전 출력이면 ready를 반환한다. |
| `llmex sft validate-mix --config <경로>` | 출력을 현재 입력/config에서 재유도해 byte/hash와 release 상태를 검증한다. |

실제 옵션과 현재 설치된 명령은 다음으로 확인한다.

```bash
uv run llmex sft preflight-mix --help
uv run llmex sft prepare-mix --help
uv run llmex sft status-mix --help
uv run llmex sft validate-mix --help
```

정식 v5 수집이 완료되기 전에는 mix config에 임시 manifest SHA를 넣지 않는다. export/validate 뒤 생성된 teacher manifest의 SHA-256을 `expected_teacher_manifest_sha256`에 고정한다.

## SFT 실제 preflight CLI

```bash
uv run llmex sft preflight --config configs/sft/smoke.yaml --no-measure-baseline
uv run llmex sft preflight --config configs/sft/smoke.yaml --measure-baseline
```

`--no-measure-baseline`은 실제 data/tokenizer/source manifest/release/length/base/device/precision와 모델·optimizer 초기화까지만 검증한다. 기본값이다. `--measure-baseline`은 같은 검증에 고정 validation subset의 assistant target-token 가중 step-0 loss, perplexity와 target token 수를 추가한다.

성공 결과는 device, precision, `unique_parameter_count`, train/heldout rows·fingerprint·file SHA, 전체 fingerprints, base checkpoint provenance, release 상태, `expected_effective_batch_size`, baseline 측정 여부와 결과를 JSON으로 출력한다. run 디렉터리·sampler·RNG·model mode·deterministic enabled/warn-only·cuDNN 상태는 성공과 오류 모두 변경하지 않으며 입력 또는 초기화 오류는 기존 종료 코드로 실패-폐쇄한다.

## SFT 자동 품질 gate CLI

| 명령 | 계약 |
|---|---|
| `llmex sft quality-preflight --config <경로>` | SHA 고정 SFT 설정·schema 2 checkpoint·suite, deterministic/release/overlap/coverage와 decoding 계획을 출력 없이 검사한다. |
| `llmex sft quality-eval --config <경로>` | 실제 멀티턴 rollout과 고정 decoding matrix를 실행하고 불변 artifact를 원자 publish한다. |
| `llmex sft quality-status --config <경로>` | 출력이 없으면 `pending`, 완전하고 재유도 검증된 출력이면 `ready`를 반환한다. |
| `llmex sft quality-validate --config <경로>` | 현재 SHA 고정 snapshot에서 결과를 다시 유도해 기존 artifact와 byte 단위로 검증한다. |

```bash
uv run llmex config validate <quality-config.yaml> --kind sft-quality
uv run llmex sft quality-preflight --config <quality-config.yaml>
uv run llmex sft quality-eval --config <quality-config.yaml>
uv run llmex sft quality-status --config <quality-config.yaml>
uv run llmex sft quality-validate --config <quality-config.yaml>
```

설정은 `expected_sft_config_sha256`, `expected_checkpoint_sha256`, `expected_suite_sha256`을 필수로 요구한다. greedy는 temperature 0·seed 하나, sampling은 양의 temperature·합계 최소 5개 고정 seed다. repository suite의 canonical 계획은 24 scenarios·27 turns에 greedy 1회와 sampling 5회를 적용한 162 responses다. 실행 결과는 `output_dir/results.jsonl`, `report.json`, `manifest.json`이며 lock·staging·manifest-last publish와 전체 재유도로 부분 출력·동시 실행·ABA 교체·변조를 실패-폐쇄한다.

`report.json`의 `gate_passed`는 자동 판정일 뿐 실제 사람 품질이나 공개 승인 결과가 아니다. teacher judge는 비활성화되어 있고 향후 advisory-only다.

## SFT 수동 품질 gate CLI

| 명령 | 계약 |
|---|---|
| `llmex sft quality-review-template --config <경로>` | 자동 full-row·artifact·challenge에 결속된 최소 100개 blind template과 safety-critical 전수를 원자 생성한다. |
| `llmex sft quality-gate ...` | 독립 quality 2명·safety 1명·필요 adjudicator의 서명과 exact item/hash, effective score gate를 검증해 report/manifest를 원자 생성한다. |
| `llmex sft quality-review-validate ...` | 현재 template·submission·단일 trust context에서 수동 artifact를 재유도해 byte 단위로 검증한다. |

CLI는 trust root override를 노출하지 않는다. 명시적인 Git 최상위 `--repository`와 production pinned root를 사용하며, production policy에 신규 quality 역할이 아직 없으므로 보호 환경이 서명 policy를 갱신하기 전 실제 운영은 실패-폐쇄된다. 구현 완료는 실제 모델의 사람 검토 완료를 의미하지 않는다.
