# 1.0 사용 예시

## 오프라인 설정·데이터 smoke

```bash
uv run llmex config validate configs/data/sample.yaml --kind data
uv run llmex data sample-e2e --config configs/data/sample.yaml \
  --input tests/fixtures/kowiki-sample.xml.bz2 --output-dir /tmp/llmex-example --max-documents 10
```

## 모델·학습 계획 확인

```bash
uv run llmex model inspect --config configs/model/smoke.yaml --dry-run
uv run llmex train smoke --config configs/training/smoke.yaml --dry-run
uv run llmex pipeline preflight --config configs/pipeline/m6-baseline.yaml
```

## 릴리스 후보 검증

```bash
uv run llmex release audit
uv run llmex release bundle --output dist/reproducibility
```

외부 네 gate가 미승인이면 종료 코드 5가 의도된 결과다. 실제 독립 승인 artifact 없이 공개 gate를
통과시키는 예시는 제공하지 않는다.
