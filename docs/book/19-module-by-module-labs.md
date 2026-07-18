# 19장. 57개 모듈을 하나씩 만드는 실습실

이 장은 [16장 코드 지도](16-code-module-atlas.md)의 한 줄 설명을 실제 제작 순서로 확장한다. `src/llmex`의 Python 모듈 57개마다 책임, 공개 계약, 구현 순서, 의도적으로 실패시킬 사례, 표적 테스트와 산출물을 [모듈별 제작 실습 자료](modules/README.md)에 제공한다.

## 학습 목표

- 57개 Python 파일을 하위 계약부터 순서대로 직접 만든다.
- 각 파일이 소유하는 불변식과 상위 조립 계층의 책임을 구분한다.
- 정상 예제보다 먼저 누락·변조·충돌 실패를 테스트로 고정한다.
- 모듈 하나를 끝낼 때마다 실행 명령, artifact SHA와 미구현 경계를 기록한다.

## 선행 환경

[00장](00-environment-repo-tour.md)의 `uv sync --frozen`과 CPU smoke를 먼저 통과해야 한다. 모델 수치 모듈까지는 CPU로 진행할 수 있다. CUDA, 실제 teacher, 장기 SFT는 같은 계약의 fixture를 CPU에서 검증한 뒤 추가하는 실행 환경이지 별도 구현이 아니다.
[환경 프로필 부록](environment-profiles.md)의 챕터별 준비표에서 이번 실습의 입력·장치·종료 증거를 먼저 기록한다.

```bash
uv sync --frozen
uv run python -VV
uv run llmex --version
uv run pytest -q tests/test_foundation.py tests/test_config.py
```

장치가 필요한 단계에서는 다음 진단 결과를 학습 기록에 붙인다. hostname이나 secret은 기록하지 않는다.

```bash
uv run python -c 'import torch; print({"cuda": torch.cuda.is_available(), "bf16": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False, "torch": torch.__version__})'
df -h . data artifacts runs
curl --fail --silent --show-error http://localhost:8081/v1/models  # teacher 장에서만
```

## 여섯 개 모듈 챕터

1. [기반과 데이터](modules/01-foundation-and-data.md): 패키지 입구, 오류, 경로, 설정, SHA, lock, 원자 I/O, MediaWiki 처리
2. [토크나이저와 모델](modules/02-tokenizer-and-model.md): BPE, pack, RMSNorm, RoPE, GQA, SwiGLU, CausalLM
3. [학습·추론·평가](modules/03-training-inference-evaluation.md): sampler, optimizer, checkpoint, engine, runtime, canary 평가
4. [대화와 증류](modules/04-chat-and-distillation.md): chat schema, template, mix, curriculum, SFT, quality, teacher 수집
5. [조정·신뢰·릴리스](modules/05-orchestration-trust-release.md): 장기 pipeline, Ed25519 context, 배포 bundle과 외부 gate
6. [CLI 조립](modules/06-cli-assembly.md): 모든 도메인 함수를 얇은 Typer 명령 표면으로 연결

각 챕터는 적힌 순서대로 진행한다. 1~5부의 도메인 테스트가 모두 통과한 뒤 6부 `cli.py`를 만든다. 완성 저장소를 참고할 때는 공개 심볼과 테스트 계약만 먼저 읽고, 자신의 구현을 통과시킨 다음 내부 구현을 비교한다.

## 한 모듈의 반복 학습법

1. 한 문장 책임과 입력·출력 schema를 적는다.
2. 정상 경로 하나와 반드시 실패해야 하는 사례 세 개를 테스트로 쓴다.
3. 테스트를 통과하는 최소 공개 함수나 class를 구현한다.
4. byte 원자성, tensor shape, hash 결속처럼 그 모듈이 소유한 불변식을 추가한다.
5. 연결된 표적 테스트와 실제 CLI smoke를 실행한다.
6. 입력 SHA, 설정 fingerprint, artifact SHA와 아직 증명하지 않은 경계를 기록한다.
7. 다음 상위 모듈에서만 방금 만든 API를 import한다.

## 제출 단위

| 항목 | 제출 내용 |
|---|---|
| 설계 | 책임, 공개 심볼, 입력·출력, 하위 의존성 |
| 테스트 | 정상 1개, 실패·변조 3개, 재실행 또는 결정성 1개 |
| 구현 | 해당 모듈과 직접 필요한 작은 fixture만 포함한 diff |
| 실행 | 표적 pytest, lint/typecheck, 실제 CLI smoke |
| 증거 | commit, config/input/artifact SHA, 관찰한 JSON field |
| 한계 | GPU/teacher/수동 승인 등 아직 실행하지 않은 범위 |

## 모듈 수 동기화

교재가 소스 추가를 놓치지 않도록 `tests/test_book.py`는 `find src/llmex -name '*.py'`에 해당하는 집합과 모듈별 `###` 카드의 경로 집합이 정확히 같은지 검사한다. 새 Python 파일을 추가하면 같은 변경에서 적절한 모듈 챕터에 카드를 추가해야 한다.

```bash
uv run pytest -q tests/test_book.py
```

## 완료 기준

- [ ] 57개 모듈 카드가 실제 Python 파일과 일대일이다.
- [ ] 각 모듈의 공개 계약, 구현 순서, 실패 사례, 검증, 산출물을 설명할 수 있다.
- [ ] 하위 모듈에서 상위 CLI나 pipeline을 역으로 import하지 않는다.
- [ ] fixture CPU 경로와 전체 정적 검증이 통과한다.
- [ ] 실제 GPU·teacher·수동 승인 미실행 범위를 로컬 성공으로 대체하지 않는다.

## 연습문제

1. 자신의 구현 순서에서 순환 import가 발생할 수 있는 세 경로를 그리고 경계를 재배치하라.
2. `data/io.py`, `train/checkpoint.py`, `chat/mixer.py`의 원자 게시 계약을 비교하라.
3. `chat/quality.py`, `chat/quality_review.py`, `release.py`가 각각 증명하는 것과 증명하지 못하는 것을 표로 나눠라.
4. 새 모듈 하나를 추가하고 `tests/test_book.py`가 교재 카드 누락을 먼저 검출하는지 확인하라.
