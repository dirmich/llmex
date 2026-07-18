# 변경 기록

## 1.21.3 - 2026-07-18

- 빈 내부망 teacher allowlist가 필드 도입 전 loopback 증류 설정 fingerprint를 보존하도록 호환성을 복구했다. 비어 있지 않은 내부망 host 목록은 계속 fingerprint에 결속한다.
- 현재 CLI에서 정식 Qwen v5 10k의 completed 10,000, accepted 9,712, pending 0과 export train 8,213·heldout 1,488, prompt·source overlap 0을 재검증했다.
- 호환 회귀 테스트와 실행 결과·SHA를 한국어 문서에 추가했다.

## 1.9.0 - 2026-07-18

- [《LLMEX 수학 기반 이론과 Python 실습》](docs/book/README.md)을 추가했다. README와 00~15장까지 17개 Markdown이 환경·재현성·데이터·tokenizer·Transformer·사전학습·평가·증류·SFT·자동/수동 품질·release capstone을 실제 구현 계약과 연결한다.
- 각 장은 학습 목표부터 연습문제까지 11개 공통 학습 섹션을 제공한다. 외부 `knowledge_base` 계획은 날짜·SHA가 고정된 역사 참고이며 현재 저장소 코드·설정·문서·CLI를 권위로 명시했다.
- 결정적 smoke corpus 생성기와 YAML 3종을 추가했다. production tokenizer와 분리된 `artifacts/tokenizers/book-smoke-bpe`에서 split 6/6/6, requested/actual vocab 16,000 일치와 tokenizer→10-step CPU pretrain→validation/test 평가 실행을 검증했다.
- pack/chat template, 장 사이 artifact 경로, 최소 100개 수동 review와 단일 trust context, 법무·baseline·quality-release·release 네 gate 계약을 실제 코드에 맞춰 교정했다.
- 독립 아키텍처 재검토에서 APPROVE를 받았고 교재 링크 157개, 표적 45 tests, Ruff, Pyright와 예제 config schema 검증을 통과했다.

## 1.8.1 - 2026-07-18

- `sft quality-review-template`, `quality-gate`, `quality-review-validate`를 추가해 자동 평가의 full-row hash·artifact SHA·sampling challenge에 결속된 blind review를 생성·검증한다.
- population 100 미만을 거부하고 최소 100개와 safety-critical 전수를 선택하면서 profile·seed·category·multi-turn coverage를 보존한다. template에는 대화 context와 응답만 제공하고 decoding·teacher·자동 판정 정보는 가린다.
- quality reviewer 2명, safety reviewer 1명과 필요한 경우 adjudicator 1명이 서로 다른 identity·issuer·Ed25519 authority를 사용해야 한다. 단일 서명 trust snapshot, RFC3339 유효기간, exact item/hash 집합을 실패-폐쇄로 검증한다.
- adjudication 또는 두 reviewer 평균으로 만든 단일 effective matrix를 전체·항목·dimension·category 판정에 공통 사용한다. dimension/category 평균 4.0 이상, 핵심 항목 4점 이상 비율 90% 이상을 요구하고 critical flag와 safety 불일치는 veto한다.
- 수동 artifact를 lock·staging·fsync·원자 publish하고 변조를 재검증한다. release의 네 번째 필수 gate로 연결해 strict schema·fingerprint·표본·점수·교차 필드 의미와 release target을 검증한다.
- production trust policy에는 새 quality 역할을 임의 등록하지 않았다. 고정 root private key 없이 policy를 훼손하지 않으며 실제 운영 승인은 의도적으로 실패-폐쇄된다.
- 독립 코드·아키텍처 재검토에서 승인받고 전체 148 tests, Ruff lint/format, Pyright를 통과했다. 수동 gate 구현은 완료됐지만 실제 학습 모델의 사람 검토는 아직 실행하지 않았고 정식 qwen36mtp v5 수집은 동적 상태로 계속된다.

## 1.8.0 - 2026-07-18

- `sft quality-preflight/eval/status/validate`로 SHA 고정 SFT 설정·schema 2 checkpoint·한국어 suite를 실제 멀티턴 rollout과 greedy+고정 sampling seed로 자동 평가한다.
- release·overlap·deterministic·coverage를 실패-폐쇄하고 EOS/context/max 종료, target-token 가중 heldout NLL/PPL, 정확도·거부·오거부·PII·secret·Unicode·distinct·3회 연속 n-gram loop를 category/profile/seed 최악값으로 판정한다.
- MIT `data/evaluation/ko-chat-quality-v1.jsonl` 24 scenarios·27 unique turns를 추가했다. canonical greedy 1회+sampling seed 5회 계획은 162 responses이며 공개 고유 prompt 5,813개·teacher inventory 10,000개와 exact overlap 0이다.
- lock·staging·manifest-last 원자 publish와 현재 pinned snapshot에서 artifact 전체 재유도로 동시 실행·부분 출력·ABA 교체·변조를 차단한다.
- teacher judge는 비활성화하고 향후 advisory-only로 제한했다. 독립 수동 review/approval gate는 1.8.1 후속 작업이다.
- 자동 품질 gate는 독립 검토에서 승인됐고 전체 145 tests를 통과했다. 정식 qwen36mtp v5 수집은 계속 진행 중이다.

## 1.7.1 - 2026-07-17

- `llmex sft preflight --config ... --measure-baseline|--no-measure-baseline`으로 실제 SFT 전체 초기화와 선택적 step-0 기준선을 출력 생성 없이 검증한다.
- device·precision·고유 파라미터 수, train/heldout 행·fingerprint, base provenance, release 상태와 유효 batch를 출력한다.
- baseline은 고정 validation subset의 assistant target token 가중 loss·PPL·token 수를 기록하고 run 디렉터리, sampler·RNG·model mode와 deterministic/cuDNN 상태를 보존한다.
- 독립 리뷰의 `warn_only` 상태 복원 MEDIUM 지적을 수정한 뒤 승인받고 전체 137 tests, Ruff와 Pyright를 통과했다.

## 1.7.0 - 2026-07-17

- 공개 instruction 자체의 train/heldout canonical prompt overlap 152개와 공개 train·teacher heldout overlap 658개(공개 train 879행 영향)를 실측해 단순 concat을 금지했다.
- `sft prepare-mix/preflight-mix/status-mix/validate-mix`로 teacher manifest SHA와 입력을 고정하고 heldout prompt·원천 우선 격리, tokenizer 길이 gate와 결정적 출력을 구현했다.
- mix 출력을 배타 lock·staging·fsync·원자 publish로 보호하고 내부 teacher 라이선스의 release blocked를 SFT checkpoint와 평가까지 계승한다.
- SFT runtime이 canonical prompt·원천 overlap과 모든 학습 truncation을 실패-폐쇄로 거부하면서 기존 source manifest 없는 checkpoint 재개 호환성을 유지한다.
- 독립 리뷰의 최초 HIGH 3건과 MEDIUM 지적, 추가 HIGH 지적을 모두 수정해 승인받고 전체 133 tests, Ruff와 Pyright를 통과했다.

## 1.6.1 - 2026-07-17

- v3 초반 5건 결과를 근거로 안전 중단하고 v3/v4 산출물을 보존한 채 별도 pilot에서 prompt와 copy filter를 교정했다.
- 정상 요약은 허용하면서 연속 발췌·한 단어 변경 복사를 차단하고 teacher 응답에 500자 hard gate를 적용했다.
- v5 30건 실제 pilot이 전체 CLI 단계를 통과해 accepted 28건(93.3%), rejected 2건, failed/incomplete/duplicate 0을 기록했다.
- 정식 v5 10k run은 preflight 통과·pending 10,000 상태이며 pilot 처리율 단순 환산 약 11.3시간으로 예상한다.
- 독립 재검토 승인과 전체 129 tests, Ruff lint/format, Pyright, 참조 코드 checksum 검증을 통과했다.

## 1.6.0 - 2026-07-17

- 로컬 OpenAI 호환 qwen36mtp teacher의 10k 데이터를 준비·수집·재개·export·검증하는 schema 2 CLI를 추가했다.
- 원자 spool, bounded 동시성·요청률·retry, progress/ETA, stale lock과 current spool 결속으로 장기 수집을 안전하게 재개한다.
- redirect·환경 proxy·secret echo·과대 body·무제한 retry를 차단하고 teacher 출력은 내부 전용·release blocked로 고정했다.
- full latest baseline 평가와 v3 10k inventory·preflight 실행 결과를 보존했으며 실제 collect와 혼합 SFT는 후속으로 남겼다.
- 독립 리뷰의 14개 지적을 수정하고 123 tests, Ruff, Pyright와 diff 검증을 통과했다.

## 1.5.3 - 2026-07-17

- SFT에 명시적 정밀도 선택, gradient accumulation, 주기적 heldout validation과 validation loss 기준 best/latest checkpoint를 추가했다.
- schema 2 SFT checkpoint가 학습·검증 sampler, optimizer, RNG, 실제 precision과 best 상태를 포함해 완전 재개되며 손상·NaN/Inf를 실패-폐쇄로 거부한다.
- 동일한 고정 heldout subset으로 best를 비교하고, `max_steps` 연장 시 원 scheduler horizon과 이후 최소 학습률을 보존한다.
- schema 1/2 base checkpoint의 immutable SHA-256과 원 학습 provenance를 결속하며 평가·생성도 전체 schema 2 상태를 strict 검증한다.
- 동일한 split별 128 batch 비교에서 validation/test PPL, 평균 repetition, EOS가 모두 우세한 100k latest를 SFT 시작점으로 선택했다. 이는 대화 품질 gate 통과를 뜻하지 않는다.

## 1.5.1 - 2026-07-17

- 전체 Wikipedia corpus와 16k tokenizer 실측을 완료하고, 87,804,672-parameter baseline의 100,000-step 장기 학습 진행 상황을 기록했다.
- CarrotAI SFT와 qwen36mtp teacher/distillation 실험 결과를 보존했다. 실행과 safety gate는 통과했지만 repetition 0.96875, EOS 실패, newline 붕괴로 대화 가능 모델은 아니다.
- 100k 종료 후 checkpoint 무결성, 평가·생성, SFT·대규모 teacher·mixed distillation, 대화 품질 gate, 필요 시 DPO와 API packaging 순으로 후속 작업을 동기화했다.

## 1.5.0 - 2026-07-11

- provenance/license/행 hash/파일 SHA-256 검증 JSONL chat loader와 assistant-only SFT template를 추가했다.
- 사전학습 checkpoint 재사용, 원자적 SFT 재개, heldout safety/repetition/EOS 평가와 chat 생성 CLI를 구현했다.
- Wikipedia 장기 baseline·외부 공개 gate와 대화 SFT 로컬 기능 검증을 분리했다.

## 1.4.0 - 2026-07-11

- external stage마다 실행 직전 암호학적 난수를 생성해 환경 계약으로 전달하고, 사후 서명 telemetry의 nonce·run-id·stage·예산·Git commit·설정 fingerprint에 결속한다.
- telemetry 발급 시각이 stage 시작 이후이고 만료 시각이 검증 현재 시점에 유효한지 확인해, digest와 서명이 다른 과거 telemetry 재생도 거부한다.
- 모든 후속 stage 뒤 최종 성공 직전에 권위 telemetry의 digest와 서명·subject·예산을 다시 검증해 TOCTOU 변조를 실패-폐쇄한다.

## 1.3.0 - 2026-07-11

- external stage 실행 전 final telemetry 재사용을 금지하고, 실행 후 새로 생성된 final 진술을 commit/config/stage/run-id/token·energy 예산과 Ed25519 서명에 결속해 재검증한다.
- 코드에 고정된 root Ed25519 공개키로 HEAD의 policy 서명을 먼저 검증한 뒤 issuer 공개키로 evidence/승인을 검증한다. verifier의 비밀 환경변수 의존을 제거했다.
- cloze/canary를 결합 문자열 한 번의 tokenization과 offset mapping으로 점수화해 prefix/candidate/suffix BPE 경계 merge를 정확히 처리한다.


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
