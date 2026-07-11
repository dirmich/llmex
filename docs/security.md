# 보안·개인정보 정책

보안 문제는 공개 issue에 비밀이나 개인정보를 붙이지 않고 관리자에게 비공개로 전달한다. 저장소는
credential을 요구하지 않으며 `.env`, key, raw data, checkpoint를 Git에서 제외한다.

- 날짜·checksum 고정 입력, 원자적 출력, fingerprint 충돌 거부
- 엄격한 YAML과 안정된 오류 코드
- 선택적 network 차단, SBOM·checksum·provenance, CI secret 감사
- 개인정보·암기·contamination 발견 시 공개 gate 즉시 실패

scanner 결과는 완전한 안전 보장이 아니다. 의심 artifact는 격리하고 checksum과 실행 이력을 보존한다.

## 1.3.0 Ed25519 보호 CI 권위 경계

권위 있는 외부 판정은 명시한 subject repository의 Git 최상위 root와 canonical HEAD commit을
사용한다. `.llmex/trust-policy.json`은 해당 HEAD의 blob과 byte 단위로 같고 group/other 쓰기
권한이 없어야 한다. 패키지에 고정된 root Ed25519 공개키로 policy 서명을 먼저 검증하고, 검증된
policy의 issuer Ed25519 공개키만 개별 진술 검증에 사용한다. verifier는 signing secret 환경변수를
읽지 않는다. 테스트 root 대체는 공개 함수의 명시 인자 경계에서만 가능하며 production 기본값은
pinned root다. 실제 공개 job은 branch protection과 승인자가 설정된 CI protected environment에서
issuer가 서명한 approval artifact를 제공해야 한다.

### 1.3.0 긴급 키 폐기 및 재프로비저닝

기존 1.3.0 root/issuer 키는 private key 로그 노출로 즉시 폐기되었으며 더 이상 신뢰할 수 없다.
비밀키는 저장소, 로그 또는 명령 인자에 저장하지 않는다. 새 production policy는 유효한 서명이
없으면 거부하는 fail-closed provisioning anchor이며, 실제 issuer private key는 보호된 CI의
KMS/HSM에서 별도로 provisioning해야 한다.
