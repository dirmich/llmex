# 최종 acceptance matrix

| 영역 | 자동 증거 | 판정 |
|---|---|---|
| 버전·lock | 1.8.0, frozen sync | 통과 가능 |
| 품질 | Ruff, Pyright strict, pytest | 통과 가능 |
| 패키지 | sdist/wheel, 새 venv smoke | 통과 가능 |
| 기능 | CLI와 fixture pipeline E2E | 통과 가능 |
| 공급망 | checksum, SBOM, provenance | 통과 가능 |
| 보안·경계 | secret·경로·`0.ref` 감사 | 통과 가능 |
| 귀속 | NOTICE와 source schema | 로컬 계약 통과 |
| 자동 대화 품질 | SHA 고정 suite·checkpoint, 실제 rollout, decoding matrix, 재유도 artifact | 구현 통과, 실제 SFT별 실행 필요 |
| 수동 대화 품질 | blind review, 응답 hash, 독립 검토자·안전 승인 | 1.8.1 대기 |
| 장기 baseline | 전체 corpus/train/eval | 외부 대기 |
| 법적 판단 | 독립 법무 승인 | 외부 대기 |
| 공개 | 책임자·대상·채널 승인 | 외부 대기 |

자동 대화 품질의 `gate_passed=true`는 수동 품질·법무·공개 승인을 대신하지 않는다. 현재 stop condition은 로컬 영역 통과와 외부 영역의 실패 상태가 자동 검증되는 것이다.
