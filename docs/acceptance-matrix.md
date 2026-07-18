# 최종 acceptance matrix

| 영역 | 자동 증거 | 판정 |
|---|---|---|
| 버전·lock | 1.14.0, frozen sync | 통과 가능 |
| 품질 | Ruff, Pyright strict, pytest | 통과 가능 |
| 패키지 | sdist/wheel, 새 venv smoke | 통과 가능 |
| 기능 | CLI와 fixture pipeline E2E | 통과 가능 |
| 공급망 | checksum, SBOM, provenance | 통과 가능 |
| 보안·경계 | secret·경로·`0.ref` 감사 | 통과 가능 |
| 귀속 | NOTICE와 source schema | 로컬 계약 통과 |
| 자동 대화 품질 | focused-v4 step 50: EOS 100%, correctness 87.04%, harmful refusal 91.67%, multi-turn 66.67%, unsafe 1 | 실패, counterexample 보정 필요 |
| 수동 대화 품질 | 최소 100 blind review, full-row/응답 hash, 독립 서명 quality·safety 검토 | 구현 통과, 실제 모델 사람 검토 필요 |
| SFT 민감 출력 | built-in 완화 불가, 안전한 추가 규칙, 전 assistant turn 선필터, 원자 directory publish | 구현 통과, 실제 mix별 집계 확인 필요 |
| SFT 원천 identity | source SHA·ID·원행 SHA 우선순위, teacher 원행 결속, 최종 source overlap 0 | 구현·실제 pilot 통과 |
| SFT fresh run | 미존재 run 디렉터리 원자 선점, 기존 경로 보존, strict resume만 연속 기록 | 구현·회귀 통과 |
| SFT token cache | 전체 길이·값 2-pass 결속, 연속 int32/offset storage, 완화 불가 128 MiB 상한 | 구현·실제 pilot preflight 통과 |
| SFT checkpoint I/O | 같은 step의 best·주기·final 요청 단일 저장, 중단 final·zero-iteration fallback | 구현·회귀 통과 |
| SFT 보정 curriculum | v1~v4와 접미 counterexample v5, 모든 user turn suite 비누출, target-token 질량, 원자 publish | v5 train 7,200/heldout 720행 생성·재검증, 학습 대기 |
| 모듈별 교재 | 57개 Python 모듈 카드, 환경별 0~12단계 워크북, capstone rubric, 출처·주장 원장 | 구현·일대일 회귀 통과 |
| 장기 baseline | 전체 corpus/train/eval | 외부 대기 |
| 법적 판단 | 독립 법무 승인 | 외부 대기 |
| 공개 | 책임자·대상·채널 승인 | 외부 대기 |

자동 대화 품질의 `gate_passed=true`나 수동 gate 구현 완료는 실제 모델 사람 검토·법무·공개 승인을 대신하지 않는다. production trust policy에는 신규 quality 역할이 등록되지 않았으므로 root private key로 적법하게 정책을 갱신하고 승인 evidence를 발급하기 전에는 release가 의도적으로 실패-폐쇄된다.
