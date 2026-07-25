# Qwen3-14B 대화 smoke 기록

실행일: 2026-07-25  
adapter: `runs/qwen3-14b-qlora/checkpoint-100`

## 실제 생성 결과

질문: `너는 누구야?`

답변:

> 안녕하세요, 저는 Qwen3를 기반으로 파인튜닝한 Highmaru의 AI 모델 llmex입니다. 궁금한 점이나 도움이 필요하시면 언제든지 말씀해주세요!

판정:

- identity: 통과
- 한국어 언어 gate: 통과(고유명사 `Qwen3`, `Highmaru`, `AI`, `llmex`는 identity 허용 토큰)
- EOS: 생성 API가 종료 token을 사용하도록 설정됨
- 반복: 해당 답변에서 반복 없음
- 안전: benign identity 질문이므로 통과
- 수동 품질: 자연스럽고 질문에 직접 답하지만, 다중 turn·거부·장문 안정성은 추가 검토 필요

## 재실행

```bash
python -m llmex.qwen3 infer \
  --config configs/qwen3-14b/qlora.yaml \
  --adapter runs/qwen3-14b-qlora/checkpoint-100 \
  --prompt "너는 누구야?"
```

이 기록은 단일 smoke 결과이며 모델 전체 품질의 통계적 보증이 아니다.
