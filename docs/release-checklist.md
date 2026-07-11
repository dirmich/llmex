# 1.3.0 릴리스 체크리스트

## 자동 통과 항목

- [x] 한국어 data/model/tokenizer card와 NOTICE
- [x] 보안·개인정보·위협 모델, 운영·실패 모드 문서
- [x] checksum·SBOM·provenance 생성기와 테스트
- [x] sdist/wheel 빌드와 새 venv 설치 smoke 계약
- [x] API/CLI, migration/changelog, acceptance matrix
- [x] 비밀·절대 경로·`0.ref` import/패키지 경계 감사

## 외부 승인 없이는 통과 불가

- [ ] 법무 검토: Wikipedia 귀속, 문서별 고지, 생성 가중치와 배포 조건
- [ ] 장기 baseline: 전체 dump, 사람 감사, pilot, 장기 학습, best/final 안전 평가
- [ ] 공개 배포 결정: 승인된 대상·채널·버전·철회 책임자

세 항목은 승인자, ISO 8601 시각, 근거 artifact를 가진 JSON과 `release gate`가 필요하다. 현재 판정은
**1.3.0 로컬 릴리스 준비 완료, 외부 공개 금지**다.

## 1.3.0 보호 gate 추가 검증

- 승인 bundle은 pinned root가 서명한 HEAD policy와 policy의 issuer Ed25519 공개키로 검증한다.
- 각 gate는 서로 다른 승인자, UTC RFC3339 발급·만료, evidence 파일 SHA-256, 버전·Git commit·config fingerprint를 요구한다.
- wheel/sdist digest는 artifact manifest와 provenance subject가 일치해야 하며 SBOM은 wheel METADATA의 runtime dependency만 기술한다.
- canary provenance가 없거나 에너지/token telemetry를 검증할 수 없는 외부 실행은 통과가 아니라 대기/실패다.
- external stage는 실행 전 final telemetry를 재사용하지 않고 종료 후 새로 생성된 final 진술의 stage/run-id/예산 결속과 최종 사용량을 권위 있게 재검증한다.

## 1.3.0 권위 있는 승인 입력

`release gate`에는 approval 파일 위치와 독립적인 `--repository-root`를 명시한다. Git root/HEAD 확인
실패, 빈 값, abbreviated/noncanonical commit은 거부한다. 세 gate의 role/kind는 각각
`legal/legal-approval`, `baseline/baseline-evidence`, `release/release-approval`과 정확히 일치해야 한다.
정책은 HEAD에 봉인된 `.llmex/trust-policy.json`만 사용하며 로컬 self-signed 결과는 공개 권한이 없다.
