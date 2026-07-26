# runtime 능력 안내 계약

모델 자유 생성이 표현 변형 질문에서 정체성 답변으로 흔들리지 않도록 runtime memory 계층에서 능력 질문을 보완한다. 사주·만세력 문장은 이 규칙보다 앞선 `calculate_saju` 라우터가 처리한다.

대표 응답:

```text
질문 답변, 요약, 글쓰기, 번역, Linux 명령 안내, Raspberry Pi GPIO 작업 설계를 도와드릴 수 있어요.
```

이는 모델이 계산 결과나 도구 실행 결과를 꾸며내는 기능이 아니다. 실제 Linux/GPIO 작업이나 사주 계산은 별도 실행기와 도구 dispatcher의 결과를 사용한다.

## 검증된 실행 경로

최신 100M checkpoint를 대화형으로 테스트할 때는 `sft generate`를 사용한다. 이 경로는 모델 생성 전에 identity·감정 공감·사주 필수정보 요청을 결정적으로 라우팅한다.

```bash
CFG=configs/sft/qwen36mtp-v5-full-latest-dialogue-memory-180.yaml
CK=runs/sft-qwen36mtp-v5-full-latest-dialogue-memory-180/checkpoints/latest.pt
uv run llmex sft generate --config "$CFG" --checkpoint "$CK" --prompt "오늘 기분이 조금 가라앉았어."
uv run llmex sft generate --config "$CFG" --checkpoint "$CK" --prompt "사주를 볼 수 있어?"
uv run llmex sft generate --config "$CFG" --checkpoint "$CK" --prompt "넌 누구냐?"
```

Q4_K_M GGUF를 `llama-completion`으로 직접 실행하는 경로는 runtime 라우터를 거치지 않으므로 의미 변형·도구 호출 보장이 없다. 배포 시에는 이 라우팅 계약을 포함한 harness/dispatcher를 함께 사용하고, GGUF 단독 결과는 별도 모델 품질 증거로 기록한다.
