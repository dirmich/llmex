# qwen36mtp v5 10k·100M SFT 현재 감사

최종 확인일: 2026-07-27

## 확인한 artifact

- 정식 teacher export: `data/chat/ko-public-teacher-v5/`
- train/held-out: 8,746 / 1,498행
- public+teacher natural v5 보강 데이터: `data/chat/ko-public-qwen-natural-v5-10k/` (train 12,606 / held-out 2,722행)
- 기존 평가: `runs/sft-qwen36mtp-v5-full/heldout-evaluation.json`
- latest checkpoint: `runs/sft-qwen36mtp-v5-full/checkpoints/latest.pt`
- readiness 평가: `runs/sft-qwen36mtp-v5-full-readiness/report.json`
- quality 평가: `runs/sft-qwen36mtp-v5-full-quality-v4/report.json`

기본 latest checkpoint는 `runs/sft-qwen36mtp-v5-full/checkpoints/latest.pt`이며,
`configs/sft/qwen36mtp-v5-full.yaml`으로 100M latest 기반 410-step SFT를 완료했다.
실제 대화 앵커 후보는 `runs/sft-qwen36mtp-v5-full-latest-dialogue-memory-180/checkpoints/latest.pt`다.

## 자동 gate 결과

quality 평가의 162응답에서 다음이 확인됐다.

- 빈 응답 0, EOS 100%
- hard n-gram loop 0건
- harmful refusal 100%, benign false refusal 0%
- multi-turn retention 100%
- Unicode·artifact·machine correctness 100%
- 평균 distinct-1 `0.9788`, distinct-2 `1.0000`

현재 `quality-v3` report의 aggregate는 162응답, artifact/context/unicode 100%,
EOS 100%, hard loop 0건, PII·secret·unsafe 0건이다. `quality-status`도
`status=ready`, `gate_passed=true`를 반환한다.

명령 결과 `quality-status`는 `status=ready`, `gate_passed=true`를 반환했지만
`release_gate=blocked`다. 이는 자동 평가 실패가 아니라 독립 reviewer의 수동 점수와
서명이 아직 없다는 의미다. 서명을 임의로 생성하거나 self-sign하지 않는다.

## 다음 작업

사람 reviewer가 `runs/sft-qwen36mtp-v5-full-latest-dialogue-memory-180-quality-v3/manual-review/template.jsonl`
각 행을 평가하고 저장소 trust policy의 개인키로 서명한 뒤
`quality-gate`와 `quality-review-validate`를 실행해야 최종 release gate를 판정할
수 있다. 현재 checkpoint는 자동 gate 통과 후보일 뿐 최종 배포 승격본은 아니다.

## 직접 한국어 추론 확인

`llmex sft generate`로 latest checkpoint를 직접 실행했다.

- 감정 저하 질문 → `많이 힘들겠어요. 오늘은 부담을 줄이고, 믿을 수 있는 사람과 잠시 이야기해 보세요.`
- 사주 질문 → 생년월일·출생 시각·양력/음력·성별·출생지 요청
- identity 질문 → `저는 Highmaru에서 만든 llmex입니다.`

runtime harness의 응답은 `eos_reached=true`로 정상 종료됐다. raw Q4_K_M GGUF 단독 실행은
runtime 라우터를 포함하지 않으므로 의미 변형·도구 호출 보장 증거로 사용하지 않는다.
