# 변경 기록

## 1.9.4 - 2026-07-18

- 검증된 train/heldout token을 split별 연속 int32 input/label과 int64 offsets, 총 6개 tensor에 cache해 학습·validation 반복 tokenization을 제거했다.
- 1차 길이·generation 검증의 input/label SHA와 2차 buffer fill 값을 결속해 동일 길이 token 변조도 실패-폐쇄한다.
- offsets를 포함한 persistent storage에 완화 불가 128 MiB 상한을 적용하고 preflight에 split·total 행/token/byte·dtype·tensor 수를 노출한다.
- 실제 pilot mix 4,732행·3,435,621 token·27,522,840 bytes preflight와 batch 준비 약 55배 micro benchmark를 기록했다.
- 전체 165 tests, Ruff, Pyright와 두 차례 메모리 MEDIUM을 폐쇄한 독립 재검토 `APPROVE`를 통과했다.

## 1.9.3 - 2026-07-18

- 새 `sft train`이 빈 디렉터리를 포함한 모든 기존 run 경로를 실패-폐쇄하고 과거 파일·checkpoint를 보존하도록 했다.
- trainer 초기화 전 선검사와 쓰기 직전 배타 `mkdir`로 동시 fresh 실행에서 정확히 하나만 경로를 선점한다.
- strict checkpoint 복원에 성공한 resume/restore만 기존 run을 이어가며, 동일 baseline에서 pilot/full 별도 fresh run을 시작하는 계약을 회귀로 고정했다.
- 실행 가이드와 모듈별 SFT 교재에 pilot/full 분리, 약 3 epoch step 계산과 중단 복구 명령을 동기화했다.
- 전체 162 tests, Ruff, Pyright와 독립 2-thread 경합 재검토 `APPROVE`를 통과했다.

## 1.9.2 - 2026-07-18

- 공개 행에 source identity가 없을 때 dataset/source 전체를 하나로 묶던 혼합 결함을 교정했다. `source_sha256 → 명시 source_id → 검증된 입력 행 SHA` 순서로 원행을 결속한다.
- 기존 provenance identity는 보존하고 둘 다 없는 출력 행에만 원행 ID/SHA를 승격해 mixer와 SFT runtime의 split 누출 검사를 일치시켰다.
- 모듈별 실습 교재의 혼합 장을 같은 원행 우선순위와 fallback 계약으로 동기화했다.
- 실제 public 6,853 + teacher pilot 28 입력을 재유도해 train 25행의 비정상 결과를 train 4,257행, heldout 475행으로 회복했고 source/prompt overlap 0과 입력 수 보존을 확인했다.
- 원행 하나만 teacher heldout에 결속되는 회귀를 포함해 전체 160 tests, Ruff, Pyright와 독립 재검토 `APPROVE`를 통과했다.

## 1.9.1 - 2026-07-18

- 공개·teacher train/heldout의 모든 assistant turn에 완화 불가능한 주민번호·휴대전화·이메일·secret built-in 선필터를 추가했다.
- 한국어 접미 탐지와 식별자 substring 오탐 방지, 65,536자 초과 실패-폐쇄, 원문을 노출하지 않는 source/split/rule 집계를 구현했다.
- 추가 민감/품질 패턴은 256자 고정 폭 안전 부분집합만 허용한다. 품질 suite assertion은 기존 표현력을 유지하면서 중첩·인접 모호 반복, backreference, lookaround와 `{,m}` 우회를 거부하고 예약 규칙 이름 충돌도 설정 단계에서 차단한다.
- SFT mix와 자동 quality 산출물을 parent 고유 lock과 sibling staging에서 만든 뒤 완성 디렉터리 하나로 원자 publish한다.
- Apache-2.0 공개 instruction 6,204/649행과 고정 revision·원본·provenance·SHA를 `data/chat/public/korean-instruction-v1`에 보존했다.
- 전체 테스트, Ruff, Pyright, 실패 주입·경계·ReDoS probe를 통과하고 독립 재검토를 수행했다. 정식 teacher 수집과 실제 SFT는 계속 진행 중이다.

## 1.9.0 - 2026-07-18

- README와 00~15장, 총 17개 Markdown으로 된 [수학 기반 이론·Python 실습 교재](book/README.md)를 추가했다. 모든 장은 11개 공통 학습 섹션을 가지며 실제 코드·설정·CLI를 현재 권위로 사용한다.
- 결정적 corpus 생성기와 tokenizer/pretrain/evaluation YAML 3종으로 production과 분리된 `book-smoke-bpe` E2E를 제공한다.
- 실제 pack·assistant-only chat, artifact 경로, 최소 100개 blind review·단일 trust context와 네 release gate 계약을 교재 전 장에 동기화했다.
- split 6/6/6, requested/actual vocab 16,000, CPU 10-step 학습과 validation/test 평가를 실행하고 독립 재검토 APPROVE, 157개 링크, 표적 45 tests, Ruff·Pyright·config schema 통과를 확인했다.

## 1.8.1 - 2026-07-18

- 자동 full-row·artifact SHA·sampling challenge에 결속된 `quality-review-template`, `quality-gate`, `quality-review-validate`를 추가했다.
- 최소 100개와 safety-critical 전수, profile/seed/category/multi-turn coverage를 결정적으로 선택하고 context·response 외 decoding/teacher/자동 판정 정보를 blind 처리한다.
- 독립 quality 2명·safety 1명·필요 adjudicator의 identity·issuer·key 분리, 서명·만료·단일 trust context를 검증한다.
- 단일 effective matrix로 전체·항목·dimension·category를 계산해 dimension/category 4.0 이상과 핵심 90%를 요구하며 critical 및 safety disagreement를 veto한다.
- 원자 publish·변조 검증과 release 네 번째 필수 gate의 strict schema·fingerprint·점수·교차 의미·target 결속을 구현했다.
- production trust policy에는 신규 quality 역할을 등록하지 않아 root private key 없는 운영 승인은 실패-폐쇄된다. 실제 모델 사람 검토는 미실행이며 정식 v5 수집 상태는 `distill status`로 확인한다.
- 독립 재검토 승인과 전체 148 tests, Ruff, Pyright 통과를 확인했다.

## 1.8.0 - 2026-07-18

- `sft quality-preflight/eval/status/validate`로 SHA 고정 SFT 설정·schema 2 checkpoint·한국어 suite의 실제 멀티턴 자동 품질 gate를 추가했다.
- greedy 1회와 sampling 고정 seed 최소 5회에서 EOS/context/max 종료, target-token 가중 heldout NLL/PPL, 정확도·거부·오거부·PII·secret·Unicode·distinct·3회 연속 n-gram loop를 category/profile/seed 최악값으로 판정한다.
- MIT suite 24 scenarios·27 unique turns와 canonical 162 responses 계획을 고정하고 공개 5,813 unique prompts·teacher inventory 10,000 prompts와 exact overlap 0을 확인했다.
- release·overlap·deterministic·coverage, lock·staging·manifest-last 원자 publish, pinned snapshot 전체 재유도 검증을 실패-폐쇄한다.
- teacher judge는 비활성화·향후 advisory-only이며 수동 review/approval gate는 1.8.1로 분리했다.
- 독립 리뷰 승인과 전체 145 tests 실행 결과를 확인했다. 정식 qwen36mtp v5 수집은 진행 중이다.

## 1.7.1 - 2026-07-17

- `llmex sft preflight`에 `--measure-baseline/--no-measure-baseline` 선택을 추가해 실제 데이터·tokenizer·source manifest·release·길이·base checkpoint·device·precision과 모델/optimizer 초기화를 검증한다.
- 출력에 확정 device·precision, 고유 파라미터 수, train/heldout 행·fingerprint·파일 SHA, base provenance, release 상태와 예상 유효 batch를 포함한다.
- 선택적 step-0 baseline은 고정 validation subset의 assistant target token 가중 loss, perplexity와 target token 수를 결정적으로 측정한다.
- 성공과 오류 모두 run 디렉터리·sampler·validation count·RNG·모델 mode와 deterministic enabled/warn-only·cuDNN benchmark 상태를 바꾸지 않고 오류를 실패-폐쇄한다.
- 독립 리뷰의 `warn_only` 복원 MEDIUM 지적을 수정한 뒤 최종 승인받고 전체 137 tests, Ruff와 Pyright를 통과했다.

## 1.7.0 - 2026-07-17

- 공개 instruction 자체의 canonical prompt train/heldout overlap 152개와 공개 train·teacher heldout overlap 658개 및 영향 공개 train 879행을 확인해 직접 concat을 차단했다.
- `sft prepare-mix`, `preflight-mix`, `status-mix`, `validate-mix` 명령과 `sft-mix` 설정 schema를 추가했다.
- teacher export manifest의 예상 SHA-256, 입력 JSONL·tokenizer manifest와 mix 출력을 결속하고 heldout prompt·원천 우선 격리와 길이 초과 제외를 결정적으로 수행한다.
- 동시 실행·부분 publish를 배타 lock과 staging으로 거부하고 내부 전용 라이선스의 `redistribution_allowed=false`, `release_gate=blocked`를 checkpoint·평가에 계승한다.
- SFT runtime에 canonical prompt·원천 cross-split 검사와 전 데이터 truncation 금지를 적용하되 legacy checkpoint 재개 계약은 유지했다.
- 독립 리뷰의 최초 HIGH 3건과 MEDIUM 지적, 후속 HIGH 지적을 수정한 뒤 승인받고 전체 133 tests, Ruff와 Pyright를 통과했다.

## 1.6.1 - 2026-07-17

- v3 초반 수용률 저하를 5건에서 안전 중단하고 기존 v3/v4 계열 run을 변경 없이 보존했다.
- v4/v4b에서 teacher prompt와 copy 오탐을 교정하고 정상 요약 허용, 연속 발췌·근접 복사 차단과 500자 hard gate를 고정했다.
- 최종 v5 30건 pilot의 prepare/preflight/collect/export/validate를 통과해 accepted 28건(93.3%), rejected 2건, failed/incomplete/duplicate 0을 확인했다.
- 정식 v5 10k inventory와 config fingerprint를 고정하고 preflight 통과, pending 10,000과 pilot 단순 환산 약 11.3시간을 기록했다.
- 실제 수집부터 export/validate, 공개 instruction 혼합 SFT와 대화 품질 gate까지의 후속 순서를 갱신했다.
- 독립 재검토 승인과 전체 129 tests, Ruff lint/format, Pyright, 참조 코드 checksum 검증을 통과했다.

## 1.6.0 - 2026-07-17

- `distill preflight/prepare/collect/resume/status/export/validate` schema 2 teacher 수집 파이프라인과 qwen36mtp 10k v3 설정을 추가했다.
- 결정적 10k inventory, 원자 spool, 진행률·ETA, bounded concurrency/RPS/retry, 중단 재개와 stale lock 회수를 구현했다.
- current inventory/spool에 결속된 provenance export와 내부 전용 라이선스·release blocked 검증을 추가했다.
- loopback endpoint, redirect·proxy 차단, secret echo 비보존, 응답 body/retry 상한과 strict teacher 응답 schema를 적용했다.
- 100k latest full validation/test 평가와 v3 inventory 준비·preflight 실행 결과를 기록했다. 실제 10k collect는 대기 중이다.
- 독립 리뷰 14개 지적 수정 뒤 승인받고 전체 123 tests, Ruff, Pyright와 diff 검사를 통과했다.

## 1.5.3 - 2026-07-17

- SFT에 `auto`/`bf16`/`fp16`/`fp32` 정밀도, gradient accumulation, 주기적 heldout validation과 validation loss 기준 `best.pt`를 추가했다.
- schema 2 SFT checkpoint로 모델·optimizer·scheduler·scaler·train/validation sampler·RNG·실제 precision·best 상태를 완전 재개하고, 무결성 및 NaN/Inf 검사를 강화했다.
- 매 validation에 동일한 고정 heldout subset을 사용해 best 비교 기준을 고정하고, `max_steps` 연장 시 원 scheduler horizon과 이후 최소 학습률을 보존한다.
- schema 1/2 `base_checkpoint`의 immutable SHA-256과 원 학습 provenance를 결속하고, 평가·생성도 schema 2 전체 상태를 strict 검증한다.
- 동일한 split별 128 batch 평가에서 모든 측정 축이 우세한 100k `latest`를 SFT 시작점으로 선택했으며, 이 선택과 대화 품질 gate를 분리했다.

## 1.5.2 - 2026-07-17

- 100,000-step CUDA bf16 baseline 학습을 완료하고 best checkpoint를 step 82,000으로 확정했다.
- 완료 step/latest/best checkpoint의 SHA-256, strict fingerprint, schema, 필수 재개 상태와 NaN/Inf 부재를 검사하는 `llmex train audit` 명령을 추가했다.
- best checkpoint의 CUDA 1-batch validation/test 평가, cloze와 고정 prompt 생성 결과를 기록하고 corpus/canary 미설정으로 미실행된 항목을 후속 전체 평가 gate와 분리했다.
- 다음 실행 순서를 SFT engine 강화, teacher 10k pilot, 혼합 SFT, 대화 gate, GGUF/llama.cpp parity로 갱신했다.

## 1.5.1 - 2026-07-17

- 전체 Wikipedia corpus/tokenizer 실측과 진행 중인 87,804,672-parameter baseline의 기록 시점 snapshot을 문서화했다.
- CarrotAI SFT 및 qwen36mtp 증류 수치를 기록하고 repetition 0.96875, EOS 실패, newline 붕괴 때문에 대화 가능 상태가 아님을 명시했다.
- 100k 종료 뒤 checkpoint 검증부터 평가·생성, SFT·확대 증류, 대화 gate, 필요 시 DPO, API packaging까지의 순서를 동기화했다.

## 1.5.0 - 2026-07-11

- provenance/license/hash JSONL loader, assistant-only SFT, 원자 재개, heldout gate와 chat 생성을 추가했다.
- `llmex sft train/resume/eval/generate`와 한국어 실행 가이드, 합성 CPU 검증을 제공한다.

## 1.4.0 - 2026-07-11

- external stage별 실행 직전 nonce와 사후 발급시각을 서명 telemetry에 결속해 과거 재생을 차단했다.
- 후속 stage 완료 뒤 권위 telemetry를 전부 재검증해 최종 성공 직전 TOCTOU 변조를 거부한다.

## 1.3.0 - 2026-07-11

- external stage 종료 뒤 새로 생성된 `final=true` telemetry만 권위 있게 승인하며 서명·commit/config/stage/run-id·예산 결속과 최종 사용량 상한을 재검증한다.
- self-declared policy를 폐기하고 pinned root → 서명 policy → issuer Ed25519의 공개키 신뢰 체인으로 전환했다. verifier는 signing secret 환경변수를 읽지 않는다.
- 결합 sequence offset을 기준으로 cloze/canary likelihood와 rank를 계산하고 BPE 경계 merge 회귀를 추가했다.


## 1.2.0 - 2026-07-11

- release gate를 명시 repository root의 canonical Git commit과 HEAD에 봉인된 보호 CI trust policy에 결속했다. gate별 역할은 legal/baseline/release와 정확히 일치해야 한다.
- pipeline external evidence와 최종 token/energy telemetry에 같은 서명·issuer-role-kind·RFC3339 만료·commit/config/artifact 결속을 적용했다. telemetry 부재·비최종·변조는 실패-폐쇄한다.
- canary 미제공은 미실행/실패, 평가 contamination은 exact 5-gram Jaccard, JSONL.ZST와 dashboard는 fsync/atomic 계약임을 동기화했다.

## 1.1.1 - 2026-07-11

- `acf2841..45bd4ff` 변경 파일을 52개 회귀 테스트로 잠근 뒤 smell별 정리를 수행했다.
- 호출되지 않는 artifact sidecar 검증 helper와 전용 import를 삭제했다.
- 평가 Markdown의 중복 원자적 쓰기를 공통 `atomic_write_bytes` 경로로 통합하고 preflight 이름을 명확히 했다.
- fallback-like 코드는 masking 경로 없이 OS 호환·resume·recovery·checkpoint 보안 경계의 fail-safe임을 재확인했다.

## 1.0.1 - 2026-07-11

- M0–M7 변경 범위의 최종 AI slop 정리를 수행했다.
- downloader의 도달 불가능한 대체 오류 경로를 삭제하고 재시도 소진 회귀 테스트를 추가했다.
- 공개 계약은 유지하고 버전·lock·릴리스 검증 기록을 동기화했다.

## 1.0.0 - 2026-07-11

- 재현성 bundle, checksum, CycloneDX SBOM, provenance 생성 CLI를 추가했다.
- 법무·장기 baseline·공개 배포의 실패-폐쇄 외부 gate를 추가했다.
- 카드, NOTICE, 보안·위협, 운영·API/CLI·실패·이전 문서를 추가했다.
- sdist/wheel clean-room 설치와 공급망·참조 경계 CI 검증을 확대했다.

## 0.7.0

- M6 pipeline orchestration, preflight, 복구 drill과 외부 증거 gate를 추가했다.

## 1.1.0 - 2026-07-11

### 보안과 무결성
- 외부 승인을 보호 CI 신뢰 저장소 서명과 RFC3339 만료, issuer/role allowlist, 서로 다른 승인자, evidence SHA-256 및 release target에 결속했다.
- 모든 checkpoint 로드를 `weights_only=True`로 제한하고 악성 pickle 실행을 차단했다.
- pipeline evidence/output/recovery와 artifact sidecar를 실패-폐쇄·원자적 계약으로 강화했다.

### 평가와 운영
- cloze 조건부 likelihood/rank/accuracy, canary exposure rank, streaming bounded contamination을 실제 계산한다.
- time/token/energy budget을 실행 중 강제하고 재개 session delta 처리량을 기록한다.
- wheel/sdist digest와 wheel 내용 기반 SBOM/SLSA provenance를 생성한다.
