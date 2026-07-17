# 변경 기록

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
