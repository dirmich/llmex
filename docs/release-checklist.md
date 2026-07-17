# 1.9.3 릴리스 체크리스트

## 자동 통과 항목

- [x] 한국어 data/model/tokenizer card와 NOTICE
- [x] 보안·개인정보·위협 모델, 운영·실패 모드 문서
- [x] checksum·SBOM·provenance 생성기와 테스트
- [x] sdist/wheel 빌드와 새 venv 설치 smoke 계약
- [x] API/CLI, migration/changelog, acceptance matrix
- [x] 비밀·절대 경로·`0.ref` import/패키지 경계 감사
- [x] SHA 고정 자동 대화 품질 gate 구현·독립 리뷰·회귀 검증
- [x] 최소 100개 blind sample과 safety-critical 전수·coverage 수동 gate 구현
- [x] quality 2명·safety 1명·필요 adjudicator의 독립 identity/issuer/key 및 서명 만료 검증
- [x] effective matrix, dimension/category 4.0, 핵심 90%, critical/safety veto
- [x] 수동 artifact 원자 publish·tamper 검증과 release 네 번째 gate strict semantic 결속
- [x] SFT mix의 완화 불가 assistant 민감 출력 선필터와 단일 디렉터리 원자 publish
- [x] 공개 원행·teacher 파생행의 행별 provenance identity와 source overlap 0
- [x] 새 SFT의 미존재 run 디렉터리 원자 선점과 strict resume 전용 기존 run 재사용

## 외부 승인 없이는 통과 불가

- [ ] 법무 검토: Wikipedia 귀속, 문서별 고지, 생성 가중치와 배포 조건
- [ ] 장기 baseline: 전체 dump, 사람 감사, pilot, 장기 학습, best/final 안전 평가
- [ ] 수동 대화 품질 실행: 실제 학습 모델 blind sample, 독립 quality·safety 검토와 필요 adjudication
- [ ] 공개 배포 결정: 승인된 대상·채널·버전·철회 책임자

네 항목은 승인자, ISO 8601 시각, 근거 artifact를 가진 JSON과 각 품질·`release gate`가 필요하다. 현재 판정은
**1.9.3 교재·민감 출력/원천 결속·fresh SFT·자동/수동 품질 gate 구현 완료, 실제 사람 검토와 외부 공개 승인 전 공개 금지**다.

release gate의 필수 집합은 법무, 장기 baseline, 수동 품질 평가, 공개 배포 결정 네 개다. 수동 품질 manifest/report는 exact key, canonical fingerprint, report SHA, 최소 표본, 모든 점수와 worst 값, reviewer/submission/adjudication 교차 의미, release version·commit·config target을 검증한다. 네 gate는 한 invocation에서 한 번 snapshot한 Git commit·서명 trust policy·issuer map으로 검증한다. production `.llmex/trust-policy.json`에는 `quality-release`, `quality-reviewer`, `safety-reviewer`, `quality-adjudicator` 역할이 아직 없으며 고정 root private key 없이 policy를 수정하지 않는다.

## 1.4.0 차단 수정 검증

- [x] external stage별 실행 직전 nonce 생성과 환경 계약 전달
- [x] 사후 telemetry subject의 nonce/run-id/stage/예산/commit/config fingerprint 결속
- [x] stage 시작 이후 발급 및 현재 만료 유효성 검증
- [x] 서로 다른 유효 과거 telemetry replay 거부
- [x] 후속 stage 뒤 digest·서명·subject·예산 최종 재검증과 TOCTOU 거부

## 1.3.0 보호 gate 추가 검증

- 승인 bundle은 pinned root가 서명한 HEAD policy와 policy의 issuer Ed25519 공개키로 검증한다.
- 각 gate는 서로 다른 승인자, UTC RFC3339 발급·만료, evidence 파일 SHA-256, 버전·Git commit·config fingerprint를 요구한다.
- wheel/sdist digest는 artifact manifest와 provenance subject가 일치해야 하며 SBOM은 wheel METADATA의 runtime dependency만 기술한다.
- canary provenance가 없거나 에너지/token telemetry를 검증할 수 없는 외부 실행은 통과가 아니라 대기/실패다.
- external stage는 실행 전 final telemetry를 재사용하지 않고 종료 후 새로 생성된 final 진술의 stage/run-id/예산 결속과 최종 사용량을 권위 있게 재검증한다.

## 1.3.0 권위 있는 승인 입력

`release gate`에는 approval 파일 위치와 독립적인 `--repository-root`를 명시한다. Git root/HEAD 확인
실패, 빈 값, abbreviated/noncanonical commit은 거부한다. 네 gate의 role/kind는 각각
`legal/legal-approval`, `baseline/baseline-evidence`, `quality-release/manual-quality-gate-approval`, `release/release-approval`과 정확히 일치해야 한다.
정책은 HEAD에 봉인된 `.llmex/trust-policy.json`만 사용하며 로컬 self-signed 결과는 공개 권한이 없다.
