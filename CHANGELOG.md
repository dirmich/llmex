# 변경 기록

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
