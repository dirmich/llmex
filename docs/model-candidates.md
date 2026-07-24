# 10B급 기반 모델 후보 선정

작성일: 2026-07-25

## 결론

llmex의 다음 기반 모델은 `Qwen/Qwen3-14B`로 선정한다. 정확한 10B 모델보다 8~14B pretrained 모델군을 비교했으며, 한국어·영어·일본어·번역·tool-use·Apache 2.0·safetensors 학습 가능성을 함께 고려했다.

## 후보 비교

| 후보 | 파라미터 | 강점 | 위험·제약 | 판정 |
|---|---:|---|---|---|
| `Qwen/Qwen3-14B` | 14.8B | 100개 이상 언어, 번역·agent, Apache 2.0, 원본 safetensors | 14B라 QLoRA 필요, Qwen chat template 고정 필요 | **채택** |
| `google/gemma-4-12b-it` | 12B | 일반 대화·tool-use, 로컬 생태계 | Gemma 라이선스 확인, GGUF만으로는 SFT 불가 | 보조 후보 |
| `mistralai/Mistral-Nemo-Instruct-2407` | 12B | 128k context, 9개 언어, Apache 2.0 | 한국어 특화가 아니며 moderation mechanism 없음 | 비교 후보 |
| `EleutherAI/polyglot-ko-12.8b` | 12.8B | 대규모 한국어 사전학습, Apache 2.0 | instruct·영어·일본어·tool-use 부족 | 한국어 전용 비교 |
| `OpenLLM-Korea/EXAONE-3.5-7.8B-Instruct` | 7.8B | 한국어·영어 이중언어 | 비상업 라이선스 | 연구용 비교 |
| `meta-llama/Llama-3.1-8B-Instruct` | 8B | 생태계·추론 도구 풍부 | 공식 지원 언어에 한국어 없음, 커스텀 라이선스 | 제외 |

## 채택 이유

1. Qwen3-14B는 한국어만이 아니라 영어·일본어·번역까지 하나의 tokenizer/chat template로 평가할 수 있다.
2. Apache 2.0으로 공개·수정·재배포 정책을 검토하기 쉽다.
3. GGUF 변환 전 safetensors 원본에서 LoRA/QLoRA와 full SFT를 선택할 수 있다.
4. 기존 Qwen teacher 데이터와 prompt·role 계약을 재사용하기 쉽다.

## 실행 계획

1. `Qwen/Qwen3-14B` safetensors 원본을 `~/work/models/Qwen3-14B`에 저장한다.
2. 기존 100M 전용 trainer와 분리된 Transformers + PEFT QLoRA 경로를 추가한다.
3. 기존 public+teacher train/heldout을 그대로 사용하되, Qwen3 chat template와 assistant-only label mask를 새로 검증한다.
4. 한국어 quality/readiness, 신규 blind smoke, EOS·반복·안전·tool-call 평가를 모두 실행한다.
5. 통과한 safetensors만 GGUF로 변환하고 llama.cpp parity를 확인한다.

## 보류 정책

- 현재 0.1B checkpoint와 runtime fallback은 baseline으로 보존한다.
- 새 14B 모델이 자동 gate만 통과해도 raw generation과 수동 blind review를 통과하기 전에는 release candidate로 승격하지 않는다.
- GGUF만 있는 agentic 변형은 추론 비교용이며 학습 기반으로 채택하지 않는다.

참고: [Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B), [Mistral Nemo](https://huggingface.co/mistralai/Mistral-Nemo-Instruct-2407), [Polyglot-Ko](https://huggingface.co/EleutherAI/polyglot-ko-12.8b), [EXAONE 3.5](https://huggingface.co/OpenLLM-Korea/EXAONE-3.5-7.8B-Instruct)
