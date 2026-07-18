# 모듈별 제작 실습 자료

이 디렉터리는 완성된 `src/llmex`를 읽는 색인이 아니라, 빈 패키지에서 같은 계약을 단계적으로 다시 만드는 실습 자료다. [16장 모듈 지도](../16-code-module-atlas.md)가 전체 책임을 한눈에 보여 준다면, 이 자료는 Python 파일 하나마다 무엇을 먼저 테스트하고 어떤 순서로 구현할지를 설명한다.

## 환경 설정

모든 명령은 저장소 루트에서 실행한다. 먼저 [00장 환경 설정](../00-environment-repo-tour.md)의 진단을 끝내고 다음 공통 환경을 고정한다.

```bash
uv sync --frozen
uv run python -VV
uv run llmex --version
uv run pytest -q tests/test_foundation.py
```

CPU 트랙은 데이터·토크나이저·작은 모델·fixture 테스트를 수행한다. CUDA 트랙은 CPU 계약을 통과한 뒤에만 `torch.cuda.is_available()`와 bf16 지원을 확인하고 학습 smoke를 추가한다. teacher 트랙은 학습 환경과 별도로 `localhost` model identity와 timeout·응답 크기 제한을 preflight한다. Git에 들어가는 것은 코드·설정·교재뿐이며 `data/`, `artifacts/`, `runs/`의 대용량 산출물은 manifest SHA로 참조한다.

## 챕터별 학습 순서

| 순서 | 모듈 실습 | 먼저 읽을 본문 | 종료 조건 |
|---:|---|---|---|
| 1 | [기반과 데이터](01-foundation-and-data.md) | 00~03장 | strict 설정, 원자 I/O, provenance 데이터 E2E |
| 2 | [토크나이저와 모델](02-tokenizer-and-model.md) | 04~06장 | round-trip, causal leakage 0, cache parity |
| 3 | [학습·추론·평가](03-training-inference-evaluation.md) | 07~08장 | 중단 재개 parity와 checkpoint 결속 평가 |
| 4 | [대화와 증류](04-chat-and-distillation.md) | 09~13장 | assistant-only mask, 누출 0, 품질 재계산 |
| 5 | [조정·신뢰·릴리스](05-orchestration-trust-release.md) | 14~15장 | 복구 drill, 서명 context, release audit |
| 6 | [CLI 조립](06-cli-assembly.md) | 16~17장 | 모든 도메인 기능을 얇은 명령 표면으로 연결 |

한 챕터에서는 각 `###` 모듈 절을 위에서 아래로 진행한다. 먼저 공개 계약을 테스트로 쓰고, 최소 정상 경로를 구현한 다음 실패 사례를 추가한다. 완료 증거가 통과하기 전에는 다음 모듈을 import하지 않는다.

## 모듈 학습 기록

```markdown
### src/llmex/...py

- 시작 commit:
- 먼저 작성한 실패 테스트:
- 구현한 공개 심볼:
- 정상/변조/재실행 결과:
- 생성 artifact와 SHA-256:
- 아직 구현하지 않은 경계:
```

`__init__.py`는 학습 단계에서 빈 패키지 경계로 시작한다. 공개 API가 안정된 후에만 필요한 이름을 노출한다. `cli.py`는 모든 도메인 모듈이 테스트된 마지막 단계에 조립한다.

## 전체 검증

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run llmex release audit
git diff --check
```

이 검증은 구현과 문서의 정적 완성도를 증명한다. 실제 대화 품질과 외부 공개 승인은 각각 자동 quality artifact와 독립 수동 서명으로 별도 증명한다.
