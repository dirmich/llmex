# 실패 모드와 대응

| 실패 | 탐지 | 대응 |
|---|---|---|
| checksum 불일치 | 종료 5 | 입력 격리, 재다운로드, 덮어쓰기 금지 |
| 설정 오류 | 종료 2 | 설정 수정 후 새 fingerprint 실행 |
| 출력 충돌 | 종료 4 | 다른 run ID, 기존 artifact 보존 |
| 데이터 누출·귀속 손실 | report gate | 중단 후 원인 단계부터 재생성 |
| OOM·예산 초과 | preflight·metric | 변경은 새 config로 승인 |
| NaN/Inf | failure artifact | 정상 checkpoint와 입력 검증 |
| 개인정보·암기 | 평가·사람 검토 | 공개 gate 실패 |
| 외부 승인 누락 | release gate | 외부 공개 금지 유지 |
| 공급망·비밀 탐지 | CI audit | credential 폐기·회전, 재빌드 |
