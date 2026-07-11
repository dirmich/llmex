# 보안·개인정보 정책

보안 문제는 공개 issue에 비밀이나 개인정보를 붙이지 않고 관리자에게 비공개로 전달한다. 저장소는
credential을 요구하지 않으며 `.env`, key, raw data, checkpoint를 Git에서 제외한다.

- 날짜·checksum 고정 입력, 원자적 출력, fingerprint 충돌 거부
- 엄격한 YAML과 안정된 오류 코드
- 선택적 network 차단, SBOM·checksum·provenance, CI secret 감사
- 개인정보·암기·contamination 발견 시 공개 gate 즉시 실패

scanner 결과는 완전한 안전 보장이 아니다. 의심 artifact는 격리하고 checksum과 실행 이력을 보존한다.
