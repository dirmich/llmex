# M6 전체 데이터·baseline 보고서

## 판정

**로컬 실행 가능 계약은 완료했고 실제 외부 baseline은 대기 중이다.** 전체 dump, 사람 감사, 100-step DGX benchmark, 1% pilot, 장기 학습·평가 증거가 없으므로 baseline 완료라고 표시하지 않는다.

## 확정 프로파일과 예산

| 항목 | 값 |
|---|---:|
| 파라미터 | 87,804,672 |
| 구조 | 12층, 768폭, 12/4 GQA, SwiGLU 2,048 |
| context | 1,024 |
| tokenizer 기본 선택 | 16k(실제 32k 비교 승인 전 조건부) |
| optimizer token 상한 | 6,553,600,000 |
| wall time 상한 | 168시간 |
| 에너지 상한 | 35 kWh |
| 정상 메모리 최소 여유 | 16 GiB |
| 사전 저장공간 최소 여유 | 40 GiB |

2026-07-11 실제 preflight는 aarch64 DGX Spark에서 총 RAM 119.63 GiB, available 27.61 GiB, swap 16 GiB 중 free 4.26 GiB, NVMe free 1.90 TiB를 기록해 통과했다. 모델 inspect는 가중치 351,218,688 bytes, AdamW 학습 추정 1,404,874,752 bytes를 기록했다. context 256, micro batch 1의 실제 100-step CUDA bf16 benchmark는 41.12초, 마지막 2,479.94 token/s, PyTorch peak 1,788,401,152 bytes, process peak RSS 2,319,409,152 bytes였다. 이는 기능 benchmark이며 본학습 context 1,024 scale 승인을 대신하지 않는다.

## tokenizer 선택 gate

실제 dump 선두 1,000문서 중 정제된 997문서 canary에서 16k/32k를 모두 학습했다. 16k는 2,887,717 token·2.1666 chars/token, 32k는 2,643,299 token·2.3669 chars/token으로 32k가 token을 8.46% 줄였다. 다만 vocab/embedding 비용이 두 배이므로 전체 corpus와 DGX 처리량 비교 전에는 16k를 유지한다. 결과와 두 tokenizer SHA-256은 `tokenizer-comparison.json`에 보존했다.

## 데이터·법적·안전 gate

- 날짜 고정 `20260701` dump의 실제 checksum과 byte 수를 증거로 보존한다.
- 1,000문서 canary의 attribution 필드 누락, exact 중복, split 누출은 0이어야 한다.
- `audit-sample.json` 100건은 사람이 `승인/거부/보류`를 모두 채운 별도 승인 JSON 없이는 통과하지 않는다.
- 각 문서는 title, page/revision ID, source/dump URL, dump date, `CC BY-SA / GFDL; verify page-specific notices`를 유지한다.
- 평가 artifact의 exact/near contamination, canary exposure, 긴 train substring 결과가 기준과 함께 존재해야 한다. 위험 검출 시 공개 gate는 실패한다.
- 가중치 라이선스는 자동 단정하지 않으며 법률 검토 전 외부 공개를 금지한다.

## baseline 완료 기준

1. 모든 required evidence SHA-256이 run manifest에 포함된다.
2. 전체 data report와 100건 사람 감사가 승인된다.
3. tokenizer 16k/32k 비교가 승인된다.
4. 100-step benchmark와 1% pilot이 시간·메모리·전력 예산의 120% 이내다.
5. SIGTERM checkpoint 후 동일 fingerprint로 재개되고 loss가 유한하다.
6. best/final checkpoint 평가, contamination·암기 보고서, attribution·license gate가 통과한다.
7. pipeline 상태가 `완료`이며 JSON/Markdown dashboard와 immutable run manifest가 존재한다.

## 현재 증거

- 통과: 1,398,909,939-byte 실제 dump 다운로드, 공식 SHA-1 일치, 로컬 SHA-256 `991b26…5582`, 실제 1,000문서 canary(997 통과, exact 중복 0), 16k/32k canary 비교, DGX 87.8M 100-step, NGC container CUDA bf16, 자원 preflight, inspect, recovery drill, dashboard와 fixture pipeline E2E.
- 외부 대기: 100건 사람 감사, 전체 dump 전체 문서 정제·tokenizer 비교, context 1,024 scale, 1% pilot, 장기 baseline, best/final 평가와 공개 라이선스 승인.
- 네트워크 메모: Python metadata 수집의 무 User-Agent 요청은 HTTP 403, 일반 `SHA256SUMS`는 HTTP 404였다. 공식 제공 SHA-1과 실제 다운로드를 비교하고 별도 로컬 SHA-256을 계산했다.
