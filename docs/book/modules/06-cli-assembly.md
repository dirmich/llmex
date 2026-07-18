# 6부. CLI 조립 모듈

`src/llmex/cli.py`는 57개 모듈 중 가장 큰 파일이지만 도메인 알고리즘의 소유자가 아니다. 각 기능을 strict config loader와 연결하고, 정상 결과를 JSON으로 출력하며, 예상 오류를 안정된 종료 코드로 번역하는 마지막 조립 계층이다.

### `src/llmex/cli.py`

- 책임: Typer `app`과 `release`, `distill`, `sft`, `pipeline`, `train`, `tokenizer`, `data` 명령군을 구성한다.
- 공개 계약: console script와 `python -m llmex`가 같은 app을 사용하고, config 종류별 Pydantic schema와 도메인 함수가 일대일로 연결된다.
- 실패 계약: `LlmexError` 계층은 2~5의 정해진 exit code로, 예상하지 못한 오류는 숨기지 않고 내부 오류로 종료한다.
- 설계 제한: CLI 함수에는 tensor 계산, 데이터 선택, HTTP 재시도, checksum 정책을 구현하지 않는다.
- 완료 산출물: `--help`, `--version`, JSON stdout, 안전한 stderr/exit code를 가진 단일 명령 표면이다.

## 명령군별 단계 구현

### 1. 기반 명령

1. root `app`, `--version`, `config validate`, `fingerprint`, `run create`만 만든다.
2. `ConfigKind`에서 kind 문자열을 정확한 strict schema로 매핑한다.
3. 존재하지 않는 설정, unknown key와 fingerprint 대상 부재의 exit code를 테스트한다.

```bash
uv run llmex --help
uv run llmex --version
uv run llmex config validate configs/model/smoke.yaml --kind model
uv run pytest -q tests/test_foundation.py tests/test_config.py
```

### 2. 데이터·토크나이저 명령

1. `data download/extract/clean/dedup/split/report/sample-e2e`를 각 `data.*` 함수에 연결한다.
2. `tokenizer train/evaluate/pack`에서 dry-run과 force의 의미를 공통 helper로 고정한다.
3. 도메인 함수가 만든 manifest를 CLI가 다시 해석하거나 수정하지 않고 JSON으로 출력한다.

```bash
uv run llmex data --help
uv run llmex tokenizer --help
uv run pytest -q tests/test_m1_data.py tests/test_m2_tokenizer.py
```

### 3. 모델·학습·평가 명령

1. `model inspect`에서 파라미터 수와 shape를 읽기 전용으로 출력한다.
2. `train smoke/run/resume/audit`를 같은 training config loader에 연결한다.
3. `eval`, `generate`, `benchmark`가 같은 runtime/checkpoint 결속을 사용하게 한다.

```bash
uv run llmex model inspect --config configs/model/smoke.yaml
uv run llmex train --help
uv run pytest -q tests/test_m3_model.py tests/test_m4_training.py tests/test_m5_evaluation.py
```

### 4. 증류 명령

1. `_distill_call` 하나에서 설정을 load하고 action을 collector 함수에 dispatch한다.
2. `preflight/prepare/collect/resume/status/export/validate` 순서를 도움말과 교재에서 동일하게 유지한다.
3. collect는 endpoint 허용 범위를 넓히지 않으며 collector의 실패를 성공 JSON으로 포장하지 않는다.

```bash
uv run llmex distill --help
uv run pytest -q tests/test_distill.py
```

### 5. SFT 데이터·학습·품질 명령

1. mix와 curriculum은 각각 `preflight/prepare/status/validate` 공통 dispatch를 둔다.
2. SFT는 `preflight/train/resume/eval/generate`를 `SFTConfig`와 연결한다.
3. quality는 자동 `preflight/eval/status/validate`와 수동 template/gate/validate를 분리한다.
4. review 파일은 반복 option으로 받되 역할과 서명 검증은 `quality_review.py`에 맡긴다.

```bash
uv run llmex sft --help
uv run pytest -q tests/test_g003_chat.py tests/test_sft_mixer.py \
  tests/test_sft_curriculum.py tests/test_sft_quality.py
```

### 6. 파이프라인·릴리스 명령

1. pipeline action은 external stage 허용 여부를 명시적으로 전달한다.
2. release audit/bundle/gate는 `release.py` 결과와 exit code를 그대로 보존한다.
3. 외부 승인 누락은 대화형 질문으로 우회하지 않고 실패 상태로 출력한다.

```bash
uv run llmex pipeline --help
uv run llmex release --help
uv run pytest -q tests/test_m6_pipeline.py tests/test_m7_release.py
```

## 얇은 CLI 회귀 검사

- CLI 테스트는 명령명·option·exit code·JSON schema를 검증한다.
- 도메인 수치와 변조 검사는 각 소유 모듈의 단위 테스트에 둔다.
- `--help`는 네트워크·GPU·대용량 파일 없이 동작해야 한다.
- credential과 원문 민감 데이터는 command line, stdout, JSON log에 출력하지 않는다.
- 새 도메인 기능은 함수 테스트가 통과한 후 CLI에 연결한다.

## 챕터 종료 체크

- [ ] 모든 명령군의 `--help`가 종료 코드 0이다.
- [ ] config kind와 schema의 누락·잘못된 매핑 테스트가 있다.
- [ ] 예상 오류는 2~5, 예상 밖 오류는 내부 오류로 구분된다.
- [ ] CLI가 도메인 artifact를 임의로 다시 계산하거나 수정하지 않는다.
- [ ] console script와 `python -m llmex`의 동작이 같다.
