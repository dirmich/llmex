# qwen36mtp v5 10k·100M SFT 현재 감사

## 확인한 artifact

- 정식 teacher export: `data/chat/ko-public-teacher-v5/`
- train/held-out: 8,746 / 1,498행
- 기존 평가: `runs/sft-qwen36mtp-v5-full/heldout-evaluation.json`
- latest checkpoint: `runs/sft-qwen36mtp-v5-full/checkpoints/latest.pt`
- readiness 평가: `runs/sft-qwen36mtp-v5-full-readiness/report.json`
- quality 평가: `runs/sft-qwen36mtp-v5-full-quality-v4/report.json`

## 자동 gate 결과

quality 평가의 162응답에서 다음이 확인됐다.

- 빈 응답 0, EOS 100%
- hard n-gram loop 0건
- harmful refusal 100%, benign false refusal 0%
- multi-turn retention 100%
- Unicode·artifact·machine correctness 100%
- 평균 distinct-1 `0.9730`, distinct-2 `0.9978`

명령 결과 `quality-status`는 `status=ready`, `gate_passed=true`를 반환했지만
`release_gate=blocked`다. 이는 자동 평가 실패가 아니라 독립 reviewer의 수동 점수와
서명이 아직 없다는 의미다. 서명을 임의로 생성하거나 self-sign하지 않는다.

## 다음 작업

사람 reviewer가 `runs/sft-qwen36mtp-v5-full-quality-v4/manual-review/template.jsonl`
각 행을 평가하고 저장소 trust policy의 개인키로 서명한 뒤
`quality-gate`와 `quality-review-validate`를 실행해야 최종 release gate를 판정할
수 있다. 현재 checkpoint는 자동 gate 통과 후보일 뿐 최종 배포 승격본은 아니다.
