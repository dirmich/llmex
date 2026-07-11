# 위협 모델

| 자산 | 위협 | 통제 | 잔여 위험 |
|---|---|---|---|
| dump/corpus | 변조·rollback | 날짜 URL, checksum, manifest | upstream 오류 |
| 설정·실행 | 오타·덮어쓰기 | strict schema, fingerprint, atomic rename | 권한 탈취 |
| checkpoint | 손상·입력 혼합 | checksum과 전체 fingerprint | 악성 pickle |
| 공급망 | 의존성 변조 | `uv.lock --frozen`, SBOM, pinned CI | runner 침해 |
| 개인정보 | 암기·재노출 | canary/long-match, 사람 검토 | 미검출 정보 |
| release | 미승인 공개 | 실패-폐쇄 외부 gate | 승인자 계정 침해 |
| 참조 코드 | 라이선스 경계 침범 | import/패키지 제외 감사 | 유사성 판단 |

외부 Wikimedia, package index, CI runner, 운영자, 승인자를 별도 신뢰 경계로 본다. 임의 checkpoint는
Python 역직렬화 위험 때문에 신뢰하지 않는 출처에서 열지 않는다.
