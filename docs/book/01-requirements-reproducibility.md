# 01. 요구사항, 재현성과 실패-폐쇄

## 학습 목표

- 목표·비목표·품질 gate를 실행 가능한 불변식으로 바꾼다.
- 결정성, 재현성, 무결성의 차이를 구분한다.
- 실패-개방 대신 실패-폐쇄 상태 기계를 설계한다.

## 선행지식

[00장](00-environment-repo-tour.md)과 hash·난수 seed의 기초가 필요하다.

## 관련 실제 파일

- 역사 snapshot인 [프로젝트 계획](../../../knowledge_base/Codex/LLMEX/프로젝트%20계획.md), 현재 권위인 [PRD](../prd.md), [결정 기록](../decisions.md)
- [pipeline 상태 기계](../../src/llmex/pipeline.py), [run identity](../../src/llmex/run.py), [재현성 문서](../reproducibility.md)
- [pipeline 테스트](../../tests/test_m6_pipeline.py), [실패 모드](../failure-modes.md)

프로젝트 계획의 절대 macOS 경로와 M0 순서는 과거 실행 맥락이다. 현재 작업에서는 저장소 상대 경로, 현재 코드/config/docs와 `uv run llmex ... --help`를 우선하며 낡은 지시를 복사하지 않는다.

## 핵심 개념과 수식

결정성은 동일 환경에서 `F(input, config, seed) = 동일 bytes`가 되는 성질이다. 재현성은 환경·입력·코드까지 기록해 다른 실행자가 같은 결과를 확인할 수 있는 성질이며, 무결성은 결과가 지정된 입력과 중간에 바뀌지 않았음을 증명한다.

단계 상태는 `pending → running → succeeded|failed`만 허용하고, 실패한 증거를 자동으로 성공으로 되돌리지 않는다. 다음 단계의 허용 조건은 모든 선행 증거의 논리곱이다.

\[
allow(stage_k)=\bigwedge_{i<k}(status_i=success \land binding_i=current)
\]

## 단계별 구현

1. 요구사항을 “무엇을 한다”가 아니라 입력, 출력, 불변식, 중단 조건으로 쓴다.
2. run-id를 config fingerprint와 Git revision으로부터 결정적으로 만든다.
3. 시작 전에 disk/memory/device/input을 검사하고 상태를 원자 저장한다.
4. 외부 단계는 실행 뒤 새 evidence를 요구한다. 과거 final evidence 재사용을 금지한다.
5. 최종 성공 직전에 모든 권위 evidence를 다시 읽어 TOCTOU를 차단한다.

```python
def may_run(stage, state):
    for dependency in stage.needs:
        row = state[dependency]
        if row["status"] != "succeeded":
            return False
        verify_digest_and_subject(row["evidence"])
    return True
```

## 실제 명령

```bash
uv run llmex run create --config configs/model/smoke.yaml --kind model --dry-run
uv run llmex pipeline preflight --config configs/pipeline/m6-baseline.yaml
uv run llmex pipeline status --help
uv run pytest -q tests/test_m6_pipeline.py
```

## 예상 산출물

resolved config, Git revision, config fingerprint와 단계별 상태/evidence가 생성된다. preflight 실패 시 학습 artifact는 없어야 한다.

## 검증 테스트

- 같은 입력은 같은 run-id를 만든다.
- dependency 실패·누락·변조 시 후속 단계가 실행되지 않는다.
- process 중단 뒤 `running`을 성공으로 해석하지 않는다.
- 외부 evidence의 commit/config/run-id/발급시각이 다르면 거부한다.

## 흔한 실패와 해결

- “파일이 있으니 성공”: 내용 SHA와 subject를 재검증한다.
- nondeterministic timestamp를 fingerprint에 포함: identity와 관측 metadata를 분리한다.
- 실패 후 `--force` 덮어쓰기: 다른 fingerprint 출력은 새 run으로 만든다.

## 체크리스트

- [ ] 각 단계의 불변식·중단 조건이 문서화됐다.
- [ ] success는 재검증 가능한 evidence를 가진다.
- [ ] 실패·부분 출력은 성공으로 승격되지 않는다.
- [ ] 외부 승인과 로컬 기능 완료가 분리됐다.

## 연습문제

1. tokenizer fingerprint가 달라진 checkpoint를 왜 거부해야 하는지 설명하라.
2. 원자 write 없이 상태 JSON을 쓰는 장애 시나리오를 테스트하라.
3. `warn`이 허용되는 조건과 즉시 실패해야 할 조건을 표로 만들라.
