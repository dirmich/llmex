# 02. 엄격한 설정, fingerprint와 provenance

## 학습 목표

- YAML을 strict typed model로 읽고 알 수 없는 키를 거부한다.
- 파일 SHA-256과 구조 fingerprint의 역할을 나눈다.
- 데이터·checkpoint·평가 artifact에 provenance를 전파한다.

## 선행지식

Pydantic model과 JSON 직렬화의 기본을 안다고 가정한다.

## 관련 실제 파일

- [설정 모델](../../src/llmex/config.py), [fingerprint](../../src/llmex/fingerprint.py), [run 생성](../../src/llmex/run.py)
- [설정 테스트](../../tests/test_config.py), [sample data 설정](../../configs/data/sample.yaml), [baseline 모델 설정](../../configs/model/baseline-100m.yaml)
- [데이터 schema](../../src/llmex/data/schema.py), [chat schema](../../src/llmex/chat/data.py)

## 핵심 개념과 수식

파일 SHA는 raw bytes를 봉인한다.

\[
sha256(file)=H(b_0,b_1,\ldots,b_n)
\]

구조 fingerprint는 키를 정렬한 canonical JSON을 hash해 YAML 공백과 키 순서 차이를 제거한다. 둘은 대체 관계가 아니다. provenance는 최소한 dataset/source/date/license/source-id와 원본 hash를 포함한다.

## 단계별 구현

1. `extra="forbid", strict=True`인 기반 model을 만든다.
2. 모든 비율·길이·head shape에 범위/교차 필드 validator를 둔다.
3. YAML decode·schema 오류를 한 종류의 설정 오류로 변환한다.
4. canonical JSON은 UTF-8, 정렬 키, 고정 separator로 직렬화한다.
5. manifest에는 config fingerprint와 각 입력 file SHA를 모두 기록한다.

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

def fingerprint(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
```

## 실제 명령

```bash
uv run llmex config validate configs/data/sample.yaml --kind data
uv run llmex fingerprint file configs/model/smoke.yaml
sha256sum configs/model/smoke.yaml
uv run pytest -q tests/test_config.py
```

## 예상 산출물

검증된 설정 JSON, 64자리 config fingerprint와 file SHA가 나온다. 두 값은 용도가 다르므로 manifest에서 별도 필드로 유지한다.

## 검증 테스트

- 오타 키, 문자열로 쓴 정수, 범위 밖 비율을 거부한다.
- `latest` dump URL과 날짜 불일치를 거부한다.
- `d_model % n_heads`, `n_heads % n_kv_heads`, 짝수 head dimension을 검사한다.
- dict 키 순서가 달라도 fingerprint는 같다.

## 흔한 실패와 해결

- YAML의 `1e-4`가 문자열로 해석: 명시적 숫자 표기와 strict validation을 사용한다.
- 경로만 manifest에 저장: 경로가 같은 다른 파일을 막을 수 없으므로 SHA를 추가한다.
- license 누락: ingestion 단계에서 거부하고 나중에 추측해 채우지 않는다.

## 체크리스트

- [ ] 모든 외부 입력은 strict schema를 통과한다.
- [ ] raw bytes SHA와 canonical fingerprint가 구분된다.
- [ ] provenance와 release 속성이 downstream에 전파된다.
- [ ] 오류 메시지는 잘못된 필드와 이유를 가리킨다.

## 연습문제

1. `ModelConfig`에 `n_kv_heads=0`과 불균등 GQA를 거부하는 테스트를 작성하라.
2. 같은 의미의 YAML 두 개가 같은 fingerprint인지 확인하라.
3. provenance schema를 version 2로 올릴 때 호환 정책을 설계하라.
