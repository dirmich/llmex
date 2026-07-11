# 보안·개인정보 정책

보안 문제는 공개 issue에 비밀이나 개인정보를 붙이지 않고 관리자에게 비공개로 전달한다. 저장소는
credential을 요구하지 않으며 `.env`, key, raw data, checkpoint를 Git에서 제외한다.

- 날짜·checksum 고정 입력, 원자적 출력, fingerprint 충돌 거부
- 엄격한 YAML과 안정된 오류 코드
- 선택적 network 차단, SBOM·checksum·provenance, CI secret 감사
- 개인정보·암기·contamination 발견 시 공개 gate 즉시 실패

scanner 결과는 완전한 안전 보장이 아니다. 의심 artifact는 격리하고 checksum과 실행 이력을 보존한다.

## 1.2.0 보호 CI 권위 경계

권위 있는 외부 판정은 명시한 subject repository의 Git 최상위 root와 canonical HEAD commit을
사용한다. `.llmex/trust-policy.json`은 해당 HEAD의 blob과 byte 단위로 같고 group/other 쓰기
권한이 없어야 한다. 실행 환경의 `LLMEX_PROTECTED_SIGNING_KEYS`는 policy에 기록된 key digest와
일치하는 보호 secret만 운반하며, 환경변수만 바꿔 만든 local self-signed issuer/policy는 권위 있는
승인으로 인정하지 않는다. 실제 공개 job은 branch protection과 승인자가 설정된 CI protected
environment에서만 이 secret과 approval artifact를 제공해야 한다.
