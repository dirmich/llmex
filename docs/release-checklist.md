# 1.0.1 릴리스 체크리스트

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
**1.0.1 로컬 릴리스 준비 완료, 외부 공개 금지**다.
