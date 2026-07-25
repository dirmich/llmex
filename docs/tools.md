# LLMEX tool 사용 계약

LLMEX의 tool 사용은 모델이 임의의 셸 명령을 실행하는 방식이 아니다. 모델의
출력은 구조화된 tool 호출로 해석되고, `ToolRegistry`에 명시적으로 등록된
함수만 실행된다. 현재 기본 제공 tool은 다음 두 개다.

- `calculator`: `{"expression": "2 + 3 * 4"}` 형태의 제한된 산술식 계산
- `current_time`: 현재 UTC 시각 반환

```python
from llmex.tools import ToolRegistry

registry = ToolRegistry()
print(registry.schemas())       # OpenAI 호환 function schema
result = registry.execute("calculator", {"expression": "12 / 3"})
```

등록되지 않은 이름, JSON이 아닌 인자, 객체가 아닌 인자는 `InputError`로
거부된다. 계산기는 AST 허용 목록과 빈 builtins 환경을 사용하므로 파일·네트워크·
셸 접근을 제공하지 않는다. 실제 서비스에서는 tool별 인자 검증, 타임아웃,
호출 횟수 제한, 감사 로그, 사용자 권한을 추가해야 한다.

## 모델 학습과 런타임의 역할

현재 Qwen3 adapter는 일반 대화와 언어 일치에 맞춰 학습되어 있으며, tool 호출을
대량의 예제로 SFT/RL한 상태는 아니다. 따라서 `ToolRegistry`는 안전한 실행 기반을
제공하지만 모델이 항상 올바른 호출 JSON을 생성한다고 보장하지 않는다. 대화 중
자동 호출을 완성하려면 다음 순서를 지킨다.

1. tool schema를 system prompt에 제공한다.
2. 모델 출력에서 `name`과 JSON `arguments`를 엄격히 파싱한다.
3. registry로 실행하고 결과를 `tool` 메시지로 대화에 삽입한다.
4. 최대 반복 횟수와 전체 시간 제한 안에서만 후속 답변을 생성한다.
5. 파싱 실패·허용되지 않은 tool·위험 인자는 사용자에게 설명하고 실행하지 않는다.

실제 모델을 “매우 잘” 쓰게 하려면 위 계약을 따르는 한국어·영어·일본어
도구 사용 예제(선택, 인자 작성, 오류 복구, 결과 요약)를 별도 SFT 데이터로
추가한 뒤 held-out tool 평가를 통과시켜야 한다. 현재 테스트는 실행기 안전성과
allowlist 경계를 검증하며, 모델의 tool-call 학습 완료를 의미하지 않는다.
