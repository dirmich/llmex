# LLMEX tool 사용 계약

LLMEX의 tool 사용은 모델이 임의의 셸 명령을 실행하는 방식이 아니다. 모델의
출력은 구조화된 tool 호출로 해석되고, `ToolRegistry`에 명시적으로 등록된
함수만 실행된다. 현재 기본 제공 tool은 다음 두 개다.

- `calculator`: `{"expression": "2 + 3 * 4"}` 형태의 제한된 산술식 계산
- `current_time`: 현재 UTC 시각 반환
- `linux_system_info`: `uname`, `free`, `df /`만 고정 argv로 조회
- `gpio_read` / `gpio_write`: Raspberry Pi BCM GPIO 읽기·쓰기

```python
from llmex.tools import ToolRegistry

registry = ToolRegistry()
print(registry.schemas())       # OpenAI 호환 function schema
result = registry.execute("calculator", {"expression": "12 / 3"})
registry.execute("gpio_write", {"pin": 17, "value": True})  # 기본 dry-run
```

등록되지 않은 이름, JSON이 아닌 인자, 객체가 아닌 인자는 `InputError`로
거부된다. 계산기는 AST 허용 목록과 빈 builtins 환경을 사용하므로 파일·네트워크·
셸 접근을 제공하지 않는다. Linux tool도 임의 command 문자열을 받지 않고 고정된
읽기 전용 명령만 timeout과 출력 길이 제한으로 실행한다.

GPIO는 안전을 위해 기본적으로 dry-run이다. Raspberry Pi에서 실제 핀을 제어할 때만
`LLMEX_GPIO_DRY_RUN=0`으로 설정하고 `gpiozero`를 설치한다. 핀 번호는 BCM 기준이며,
프로덕션에서는 릴레이·모터 같은 부하의 전기적 안전과 권한을 별도로 검증해야 한다.

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

## 사주·만세력 MCP 데이터

`../0.ref/saju-mcp`를 MIT 출처로 확인하고 다음 명령으로 tool-use 데이터셋을
생성한다.

```bash
uv run python scripts/build_saju_tool_dataset.py
```

생성물은 `data/chat/ko-saju-mcp-tool-v1/`에 저장되며 train 20행과 held-out
4행, `manifest.json`을 포함한다. 예제는 `calculate_saju`, `solar_to_lunar`,
`lunar_to_solar`의 인자 선택과 정보 부족 시 추가 질문을 가르친다. 사주 결과는
계산 tool의 반환값을 근거로 설명해야 하며 미래를 확정적으로 예언하는 답변은
학습 대상에서 제외한다.
