# 운영 runbook

1. `uv sync --frozen`, `make release-check`로 입력과 환경을 검증한다.
2. 장기 실행 전 disk/memory/swap/전력 예산과 immutable config를 보존한다.
3. systemd/container restart와 host bind mount를 사용해 metrics·checkpoint를 감시한다.
4. checksum 불일치, NaN/Inf, 누출, 귀속 손실, 개인정보, 예산 120% 초과 시 중단한다.
5. 장애 시 입력을 보존하고 pipeline status/drill/export와 fingerprint를 확인해 동일 입력만 재개한다.
6. 공개 사고 시 배포를 철회하고 provenance, 승인 기록, 영향 artifact를 보존한다.

외부 gate 실패는 정상적인 보호 상태이며 우회하지 않는다.
