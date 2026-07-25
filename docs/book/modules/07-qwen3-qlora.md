# 7부. Qwen3-14B QLoRA 모듈

기존 100M 학습 경로를 그대로 보존하면서 로컬 Transformers safetensors와
PEFT adapter만 다루는 독립 실습이다. GPU 학습 전에 CPU preflight와
assistant-only mask를 먼저 고정한다.

### `src/llmex/qwen3/__init__.py`

- 책임: Qwen3 설정 모델과 loader만 공개하는 부작용 없는 패키지 경계다.
- 검증: `python -c 'import llmex.qwen3'`가 선택 의존성 없이 성공해야 한다.

### `src/llmex/qwen3/config.py`

- 책임: QLoRA 양자화·LoRA·학습 설정을 strict Pydantic schema로 검증한다.
- 실패 계약: unknown key, 중복 target module, 원본과 같은 output 경로를 거부한다.
- 검증: `pytest -q tests/test_qwen3.py -k config`를 실행한다.

### `src/llmex/qwen3/data.py`

- 책임: Qwen chat template를 thinking 비활성으로 적용하고 assistant 본문과
  종료 token만 label에 남기며 batch padding을 조립한다.
- 실패 계약: template prefix가 변하거나 truncation 뒤 학습 token이 없으면
  조용히 빈 loss를 만들지 않고 실패한다.
- 검증: 단일·멀티턴 assistant label과 종료 token 포함 여부를 검사한다.

### `src/llmex/qwen3/runtime.py`

- 책임: 로컬 Qwen3 safetensors preflight, 4-bit base load, PEFT adapter 학습과
  heldout loss 평가를 조립한다.
- 실패 계약: GGUF, 다른 model type, tokenizer 누락, split prompt 중복과 선택
  의존성 누락을 GPU load 전에 거부한다.
- 검증: fixture model directory와 실제 `check` 실패 메시지를 검사한다.

### `src/llmex/qwen3/cli.py`

- 책임: `check`, `fit`, `eval` 명령을 설정·runtime 함수와 연결하고 안정된
  LLMEX 종료 코드를 반환한다.
- 설계 제한: 모델·데이터 알고리즘을 CLI에 다시 구현하지 않는다.
- 검증: `python -m llmex.qwen3 --help`와 missing-model exit code를 검사한다.

### `src/llmex/qwen3/__main__.py`

- 책임: 기존 `llmex` console script와 분리된 `python -m llmex.qwen3` 진입점이다.
- 검증: 선택 Transformers 의존성이 없어도 도움말이 출력되어야 한다.

### `src/llmex/qwen3/harness.py`

- 책임: llmex identity system prompt와 입력 언어·EOS·반복·안전 gate를 제공한다.
- 실패 계약: 일반 외국어 혼입과 반복 응답은 통과시키지 않으며 identity 고유명사만 허용한다.
- 검증: 한국어 정상·반복·위험 요청 fixture의 gate 결과를 확인한다.

### `src/llmex/tools.py`

- 책임: 모델이 요청한 구조화 tool 중 허용 목록에 등록된 함수만 실행한다.
- 기본 실습: `calculator`와 `current_time`의 schema를 확인하고 `execute`로 호출한다.
- 실패 계약: 미등록 tool, 잘못된 JSON, 셸·파일 접근 산술식은 `InputError`로 거부한다.
- 중요한 한계: 실행기는 tool 호출을 안전하게 처리하지만, 모델 자체가 올바른
  호출을 생성하려면 별도의 tool-use SFT 데이터와 held-out 평가가 필요하다.

### `scripts/build_saju_tool_dataset.py`

- 책임: `../0.ref/saju-mcp`의 MIT 라이선스 README/MCP schema를 출처로 삼아
  사주·만세력 tool 호출 예제와 held-out 예제를 JSONL로 생성한다.
- 실행: `uv run python scripts/build_saju_tool_dataset.py` 후
  `data/chat/ko-saju-mcp-tool-v1/{train,heldout}.jsonl`을 확인한다.
- 원칙: 사주 계산은 모델이 암기하거나 산술로 추측하지 않고 `calculate_saju`,
  `solar_to_lunar`, `lunar_to_solar` tool에 위임한다. 결과 해석은 참고용으로만 말한다.

## 챕터 종료 체크

- [ ] 원본 Qwen3 safetensors와 tokenizer가 로컬에서 검증된다.
- [ ] user/system/role prefix/PAD label은 `-100`이다.
- [ ] assistant 본문과 종료 token만 loss 대상이다.
- [ ] adapter는 별도 output directory에 저장되고 원본은 변경되지 않는다.
