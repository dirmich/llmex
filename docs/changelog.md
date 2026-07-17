# 변경 기록

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
