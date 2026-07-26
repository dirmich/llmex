# Qwen3-14B identity·사주 v3 실행 검증

## 산출물

- GGUF: `~/work/models/llmex/qwen3-14b-identity-saju-v3-Q4_K_M.gguf`
- 파라미터: 14,768,307,200
- 양자화: Q4_K_M, 파일 크기 약 8.4 GiB
- SHA-256: `3ec88e06bc2e8c9695bddac834148fc39f375675c0149e12bd27e4251b7aa5ab`

## llama.cpp 무시스템 테스트

다음처럼 `-sys` 없이 실행했다. GGUF chat template가 system 메시지가 없을 때에도 identity 기본값을 삽입한다.

```bash
llama-completion -m ~/work/models/llmex/qwen3-14b-identity-saju-v3-Q4_K_M.gguf \
  -ngl 99 --jinja --single-turn -p '너는 누구냐? 누가 만들었어? 무엇을 할 수 있어?'
```

결과: `저는 llmex입니다. Highmaru에서 ...`로 응답. 영어는 `I am llmex, created by Highmaru.`, 일본어는 `私はllmexです。Highmaruが作りました。`로 응답했다. 세 언어 모두 Qwen 또는 Alibaba를 자기 정체성/제작자로 출력하지 않았다.

## 사주 도구 호출 테스트

```text
사주를 계산해줘. 1990년 1월 1일 12시 출생, 양력, 남자이다.
```

무시스템 실행 결과:

```json
{"tool":"calculate_saju","arguments":{"birth_date":"1990-01-01","birth_time":"12:00","calendar":"solar","gender":"male"}}
```

따라서 모델에 학습된 사주 도구 계약이 JSON으로 재현된다. 실제 계산은 실행 호스트의 `calculate_saju` tool dispatcher가 수행한다.

## 학습 기록

- 설정: `configs/qwen3-14b/qlora-identity-saju-v3.yaml`
- 데이터: identity 308개, 사주/tool 시스템·무시스템 균형 보강, 일반 대화 replay
- 학습: 100 step, train loss 0.9583859795, eval loss 2.4410552979
