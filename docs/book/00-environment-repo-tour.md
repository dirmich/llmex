# 00. 환경 설정과 저장소 둘러보기

## 학습 목표

- Python 3.11+, `uv`, Git과 선택적 CUDA 환경을 재현한다.
- 소스·설정·테스트·영속 산출물의 경계를 설명한다.
- CPU smoke를 실행하고 오류 코드를 읽는다.

## 선행지식

터미널의 현재 디렉터리, 환경변수, Python 가상환경과 Git의 기본 개념이면 충분하다.

## 설치 전 진단

현재 검증된 운영 환경은 Linux와 aarch64 DGX Spark다. 다른 OS에서도 Python 단위 테스트는 동작할 수 있지만, CUDA·Docker·파일시스템 원자성은 같은 수준으로 검증됐다고 가정하지 않는다.

| 확인 | 명령 | 통과 기준 |
|---|---|---|
| Python | `python3 --version` | 3.11 이상 |
| uv | `uv --version` | lock 계약과 같은 0.10.2 권장 |
| Git | `git --version` | revision 기록 가능 |
| 디스크 | `df -h .` | CPU 학습 10 GiB+, 장기 실행은 preflight 기준 |
| 메모리 | `free -h` | CPU smoke 8 GiB+ 권장 |
| 의존성 | `uv sync --frozen` | lockfile 변경 없이 종료 코드 0 |
| CLI | `uv run llmex --version` | `pyproject.toml`과 같은 버전 |

`uv`가 없다면 공식 설치 방식으로 0.10.2를 준비한 뒤 버전을 확인한다. 시스템 Python에 dependency를 하나씩 임의 설치하지 않는다.

## 관련 실제 파일

- [패키지와 도구 설정](../../pyproject.toml), [환경 계약](../environment.md), [Compose](../../docker-compose.yml)
- [CLI 진입점](../../src/llmex/cli.py), [경로 해석](../../src/llmex/paths.py), [오류 코드](../../src/llmex/errors.py)
- [기초 테스트](../../tests/test_foundation.py), [smoke 설정](../../configs/training/smoke.yaml)

## 핵심 개념

재현 환경은 코드만이 아니라 `환경 = Python/의존성 lock + OS/장치 + 입력 SHA + 설정 + Git revision`이다. `uv.lock`은 의존성 해석을 고정하고, `data/artifacts/runs`는 코드 checkout과 독립된 host 저장소로 취급한다. DGX Spark는 ARM64·unified memory이므로 전용 VRAM 숫자만으로 여유를 판단하지 않는다.

## 단계별 구현

1. 빈 프로젝트에 `src/<package>`, `tests`, `configs`, `docs`, `data`, `artifacts`, `runs`를 만든다.
2. `pyproject.toml`에 Python 하한, runtime/dev dependency, CLI entry point를 선언한다.
3. 프로젝트 루트를 탐색하는 함수는 marker(`pyproject.toml`)를 만날 때까지 부모를 올라가고, 못 찾으면 명시적으로 실패하게 한다.
4. 예상 오류를 `Config/Input/Conflict/Integrity`로 구분하고 종료 코드 2/3/4/5로 고정한다. 알 수 없는 오류만 70이다.

### 환경별 시작점

1. CPU 학습 환경에서는 Python 3.11+, `uv 0.10.2`, 10 GiB 이상의 빈 공간을 먼저 확인한다.
2. CUDA pilot 환경에서는 `torch.cuda.is_available()`, 장치 이름, bf16 지원과 짧은 행렬곱의 유한값을 확인한다.
3. DGX Spark 장기 환경에서는 전용 VRAM 숫자 대신 system available memory, RSS, swap, PyTorch peak allocation과 host NVMe 여유를 함께 기록한다.
4. teacher 증류 환경은 학습 환경과 분리해 endpoint model identity, redirect 금지, timeout과 최대 응답 byte를 preflight한다.
5. 환경이 달라도 `data/`, `artifacts/`, `runs/`의 의미와 manifest SHA 계약은 바꾸지 않는다.

```python
class ExitCode(IntEnum):
    CONFIG = 2
    INPUT = 3
    CONFLICT = 4
    INTEGRITY = 5

def project_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / "pyproject.toml").is_file():
            return path
    raise RuntimeError("프로젝트 루트를 찾을 수 없습니다")
```

## 실제 명령

```bash
uv sync --frozen
uv run python -VV
uv run llmex --version
uv run llmex --help
uv run llmex config validate configs/model/smoke.yaml --kind model
uv run pytest -q tests/test_foundation.py
```

CUDA가 보이는 장비에서는 다음 최소 probe를 추가한다.

```bash
uv run python -c 'import torch; print({"cuda": torch.cuda.is_available(), "torch": torch.__version__, "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu", "bf16": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False})'
df -h . data artifacts runs
```

결과는 학습 기록에 남기되 hostname, credential, private endpoint token은 문서나 Git에 넣지 않는다.

localhost teacher를 사용하는 장에서는 다음을 먼저 확인한다.

```bash
curl --fail --silent --show-error http://localhost:8081/v1/models
uv run llmex distill preflight --config configs/distill/qwen36mtp-10k.yaml
```

endpoint는 기본 loopback 또는 명시적 `allowed_endpoint_hosts`로 제한하고, 응답 model identity가 설정과 같아야 한다. preflight 전에는 본 수집을 시작하지 않으며 API key나 원문 데이터 내용을 shell history에 직접 쓰지 않는다.

DGX Spark에서는 `.env.example`을 복사해 호환 NGC 이미지 digest를 넣고 `docker compose run --rm dev make check`를 먼저 수행한다. secret이 들어간 `.env`는 Git에 넣지 않는다.

## 예상 산출물

`.venv/`, 설치된 `llmex` CLI, 한국어 도움말과 strict config 검증 JSON이 생긴다. smoke 검증은 `runs/`를 만들 필요가 없다.

## 검증 테스트

- CLI `--version`과 도움말이 성공한다.
- fixture bzip2 MediaWiki XML을 네트워크 없이 읽는다.
- 프로젝트 밖의 상대 경로와 누락 marker를 명시적으로 거부한다.

## 흔한 실패와 해결

- `uv sync --frozen` 실패: `uv.lock`과 `pyproject.toml` 불일치다. 임의 설치하지 말고 lock 변경 원인을 검토한다.
- CUDA 미탐지: `nvidia-smi`, container runtime과 PyTorch CUDA build를 각각 확인하고 CPU smoke로 범위를 축소한다.
- host 파일 권한 오류: container UID/GID와 bind mount 소유권을 맞춘다.

## 체크리스트

- [ ] Python과 lock 버전이 고정됐다.
- [ ] 코드와 대용량 산출물 경계가 설명된다.
- [ ] CPU smoke와 strict config가 통과한다.
- [ ] secret·절대 개인 경로가 문서/로그에 없다.

## 연습문제

1. `project_root`의 marker가 둘이면 어떤 루트를 선택할지 테스트로 고정하라.
2. `IntegrityError`와 `InputError`의 차이를 파일 손상/파일 부재 사례로 설명하라.
3. CPU·CUDA 실행의 장치 정보를 같은 JSON schema로 출력하라.
