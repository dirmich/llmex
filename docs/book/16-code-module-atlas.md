# 16장. 57개 코드 모듈 지도

이 장은 `src/llmex`의 Python 파일 57개를 빠짐없이 찾아가는 색인이다. 앞 장에서 개념을 배운 뒤 이 장에서 실제 구현 위치와 경계를 확인한다. 표의 구현 과제는 완성 코드를 복사하라는 뜻이 아니라, 공개 함수의 입력·출력과 실패 조건을 먼저 테스트로 고정한 뒤 같은 계약을 직접 재구성하라는 뜻이다.

## 학습 목표

- 패키지의 57개 모듈이 어떤 방향으로 의존하는지 설명한다.
- 각 모듈의 입력, 출력, 소유 불변식과 대표 검증을 찾는다.
- 데이터나 checkpoint를 다루는 경계에서 실패-폐쇄 원칙을 적용한다.
- 큰 `cli.py`를 기능 구현과 혼동하지 않고 얇은 조립 계층으로 읽는다.

## 선행지식

00~15장의 전체 개념을 한 번 훑고 Python module/import, type hint, 단위 테스트의 기본을 알아야 한다. 특정 영역만 볼 때는 각 표의 완료 증거가 연결된 원래 장을 먼저 읽는다.

## 읽는 순서와 의존 방향

```text
기반(errors, paths, config, fingerprint, io)
  ├─ 데이터(data/*) ─ 토크나이저(tokenizer/*)
  ├─ 모델(model/*) ─ 사전학습(train/*) ─ 추론·평가
  ├─ 대화 데이터(chat/data, template) ─ 증류(distill/*)
  │                                  └─ 혼합·SFT·품질
  └─ pipeline, trust, release ─ CLI
```

아래 순서를 지키면 아직 만들지 않은 상위 계층을 하위 계층에서 import하는 순환을 피할 수 있다. 각 행의 “완료 증거”가 통과하기 전에는 다음 묶음으로 넘어가지 않는다.

## 1. 패키지 입구와 공통 기반

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/__init__.py` | 공개 패키지 버전을 제공한다. | `pyproject.toml`, lock, CLI의 버전이 한 값인지 검사한다. | `llmex --version` |
| `src/llmex/__main__.py` | `python -m llmex`를 Typer `app` 진입점에 연결한다. | `llmex.cli`의 `app()`만 호출해 console script와 같은 명령 표면을 사용한다. | `python -m llmex --help` |
| `src/llmex/errors.py` | 예상 실패를 config/input/conflict/integrity 종료 코드로 분류한다. | 오류 메시지와 exit code를 예외 타입에 결속한다. | `tests/test_foundation.py` |
| `src/llmex/paths.py` | 프로젝트 루트 탐색과 상대 경로의 루트 기준 해석을 담당한다. | `LLMEX_ROOT`가 없을 때 `pyproject.toml`과 `.git` marker를 모두 요구한다. 현재 absolute/`..` 경로 자체는 이 모듈이 차단하지 않으므로 호출 경계에서 별도 정책이 필요하다. | 환경 override·marker 탐색·상대 경로 테스트 |
| `src/llmex/fingerprint.py` | 파일 SHA-256과 canonical mapping fingerprint를 계산한다. | chunk streaming과 key 정렬을 구현한다. | 같은 내용/다른 key 순서 동등성 |
| `src/llmex/config.py` | 모든 strict Pydantic 설정 schema와 YAML loader를 소유한다. | 알 수 없는 key, 부정 범위, 불일치 경로를 거부한다. | `llmex config validate` |
| `src/llmex/logging.py` | 로그를 일관된 JSON 형식으로 만든다. | 시간·level·message를 구조화한다. formatter는 redaction을 하지 않으므로 호출자가 비밀을 message/fields에 넘기지 않아야 한다. | JSON parse smoke |
| `src/llmex/locking.py` | run directory의 단일 writer lock을 보장한다. | live PID 충돌과 stale lock 회수를 구분한다. | 동시 실행 exactly-one 성공 |
| `src/llmex/run.py` | 실행 ID, 설정, Git revision, 환경 정보를 기록한다. | dirty/unavailable Git 상태를 숨기지 않는다. | run manifest schema 검사 |
| `src/llmex/sensitive.py` | 출력 비밀·민감 패턴과 안전한 정규식 하위집합을 검증한다. | ReDoS 위험 구조와 기본 민감 범주를 거부한다. | 악성·정상 pattern 표적 테스트 |
| `src/llmex/cli.py` | Typer 명령을 설정 loader와 도메인 함수에 연결한다. | CLI에는 핵심 알고리즘을 두지 않고 오류를 exit code로 번역한다. | 각 명령군 `--help`, CLI E2E |

`config.py`는 아래 거의 모든 모듈이 의존하는 계약 중심이다. 먼저 최소 schema 하나를 만들고 `extra="forbid"`를 확인한 뒤, milestone별 schema를 추가한다. 반대로 `cli.py`는 가장 마지막에 연결한다.

## 2. 데이터 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/data/__init__.py` | 데이터 패키지 경계를 선언한다. | 필요한 공개 이름만 노출한다. | import smoke |
| `src/llmex/data/schema.py` | attribution, quality, document row schema를 정의한다. | source URL·page/revision·license와 normalized hash를 필수화한다. | 누락 provenance 거부 |
| `src/llmex/data/io.py` | 원자적 bytes/JSON/JSONL.ZST 읽기·쓰기를 제공한다. | 같은 filesystem 임시 파일, fsync, replace, 기존 산출물 충돌을 처리한다. | 중단·재실행·손상 테스트 |
| `src/llmex/data/download.py` | Wikimedia metadata 조회, checksum 검증, 재시도 다운로드를 한다. | HTTP 오류와 checksum 불일치를 성공으로 바꾸지 않는다. | fixture server/retry 테스트 |
| `src/llmex/data/extract.py` | bz2 MediaWiki XML을 streaming page row로 변환한다. | 전체 XML을 메모리에 올리지 않고 namespace tag를 처리한다. | fixture 문서 수·revision 검사 |
| `src/llmex/data/clean.py` | wiki markup 제거, Unicode 정규화, 품질 판정을 수행한다. | attribution은 바꾸지 않고 normalized text와 정책 통계를 만든다. | 표·링크·짧은 문서 fixture |
| `src/llmex/data/dedup.py` | shingle MinHash 기반 near duplicate를 제거한다. | seed와 permutation을 고정하고 exact/near 중복을 구분한다. | 순서 변화 결정성 테스트 |
| `src/llmex/data/split.py` | document hash를 train/validation/test에 결정적으로 배정한다. | row 순서가 아니라 content hash+seed를 사용한다. | 같은 hash의 split 불변성 |
| `src/llmex/data/pipeline.py` | extract→clean→dedup→split→report를 함수 단위로 조립한다. | 단계별 manifest와 sample audit를 보존한다. | `data sample-e2e` |

데이터 계층의 핵심 출력은 텍스트가 아니라 “텍스트 + 출처 + 내용 hash + split”이다. `clean.py`가 텍스트를 바꿔도 `schema.py`의 attribution을 잃지 않아야 하며, `split.py` 뒤에는 같은 normalized hash가 두 split에 존재하면 안 된다.

## 3. 토크나이저 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/tokenizer/__init__.py` | tokenizer 패키지 경계를 선언한다. | 공개 API를 최소화한다. | import smoke |
| `src/llmex/tokenizer/core.py` | corpus fingerprint, byte-level BPE 학습·로드·round-trip을 담당한다. | PAD/BOS/EOS/UNK ID와 vocab size 계약을 manifest에 봉인한다. | train + round-trip |
| `src/llmex/tokenizer/evaluate.py` | 고정 Unicode 표본의 token 통계와 round-trip을 평가한다. | seed가 같은 표본과 한국어/emoji/결합문자를 포함한다. | `tokenizer evaluate` |
| `src/llmex/tokenizer/pack.py` | split별 token stream을 고정 dtype shard로 저장한다. | vocab에 따른 dtype, shard SHA, token count를 기록한다. | pack manifest와 재로딩 |

`core.py`의 special token ID는 모델·chat template·학습·평가 전체가 공유한다. tokenizer를 재학습하면 vocab만 비교하지 말고 manifest SHA와 packed shard를 함께 새로 만든다.

## 4. Transformer 모델 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/model/__init__.py` | 모델 구성 요소의 공개 경계를 선언한다. | 외부가 필요한 이름만 export한다. | import smoke |
| `src/llmex/model/norm.py` | RMSNorm을 마지막 차원에 적용한다. | fp32 통계와 원 dtype 복귀를 확인한다. | 수식 기준값 비교 |
| `src/llmex/model/rope.py` | 위치별 rotary embedding을 Q/K에 적용한다. | 짝수 head dimension과 offset/cache 위치를 검증한다. | 위치 변화·norm 보존 테스트 |
| `src/llmex/model/attention.py` | causal grouped-query attention과 KV cache를 구현한다. | Q head와 KV head 반복, causal mask, cache 길이 상한을 처리한다. | future-token leakage 0, cache parity |
| `src/llmex/model/block.py` | Pre-Norm residual block과 SwiGLU FFN을 조립한다. | attention/FFN residual의 shape와 순서를 고정한다. | forward/backward finite |
| `src/llmex/model/lm.py` | embedding, decoder stack, tied LM head, loss와 생성을 제공한다. | shift loss, ignore index, greedy/sampling, EOS, KV cache를 구현한다. | logits shape·loss·generate parity |

모델 계층은 `RMSNorm → RoPE → GQA → SwiGLU → DecoderBlock → CausalLM` 순으로 만든다. 각 단계에서 작은 tensor 수치 테스트를 먼저 통과시키면 완성 모델의 NaN이나 shape 오류를 역추적하기 쉽다.

## 5. 사전학습 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/train/__init__.py` | 학습 패키지 공개 경계를 선언한다. | train entry만 노출한다. | import smoke |
| `src/llmex/train/data.py` | packed shard window와 결정적 batch sampler를 제공한다. | 경계 밖 window, epoch/position 상태, resume 순서를 검증한다. | uninterrupted/resumed batch 동일 |
| `src/llmex/train/optim.py` | decay/no-decay parameter group과 LR schedule을 계산한다. | warmup+cosine+min LR과 bias/norm 제외를 구현한다. | 경계 step 수치 테스트 |
| `src/llmex/train/runtime.py` | device, precision, seed, autocast를 해석한다. | CPU/CUDA 지원 범위와 deterministic 옵션을 명시한다. | CPU fp32 및 CUDA bf16 smoke |
| `src/llmex/train/checkpoint.py` | 원자 저장, 안전 로드, RNG/sampler/optimizer 무결성 감사를 한다. | `weights_only=True`, immutable snapshot, fingerprint 일치를 강제한다. | 악성 pickle 비실행·완전 재개 |
| `src/llmex/train/engine.py` | forward/backward, accumulation, validation, checkpoint를 조립한다. | target/step, gradient clip, 처리량과 budget을 기록한다. | 중단 전후 loss·parameter 동일 |

checkpoint를 “가중치 파일”로만 생각하지 않는다. 모델·optimizer·scheduler·scaler·sampler·RNG·step·입력 fingerprint가 모두 있어야 같은 학습을 이어갈 수 있다.

## 6. 추론과 base 평가 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/inference/__init__.py` | 추론 패키지 경계를 선언한다. | runtime 공개 API를 제한한다. | import smoke |
| `src/llmex/inference/runtime.py` | model/tokenizer/checkpoint를 결속해 `LoadedRuntime`을 만든다. | config·checkpoint fingerprint와 device를 검증한다. | 잘못된 tokenizer/checkpoint 거부 |
| `src/llmex/evaluation/__init__.py` | 평가 패키지 경계를 선언한다. | runner 공개 API를 노출한다. | import smoke |
| `src/llmex/evaluation/runner.py` | perplexity, cloze, canary, contamination, 생성, benchmark artifact를 만든다. | 조건부 score 경계와 미실행 gate를 명시한다. | `eval/generate/benchmark` E2E |

평가는 숫자를 출력하는 것보다 “어떤 입력과 checkpoint에서 나온 숫자인가”를 증명하는 일이 먼저다. JSON, Markdown, checksum manifest를 한 publish 단위로 취급한다.

## 7. 대화 데이터·SFT·품질 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/chat/__init__.py` | chat 기능의 공개 경계를 선언한다. | 데이터와 runtime 진입점만 노출한다. | import smoke |
| `src/llmex/chat/data.py` | message/provenance/chat row schema와 허가 license loader를 제공한다. | role 순서, final user hash, provenance fallback을 검증한다. | 위조·누락 provenance 거부 |
| `src/llmex/chat/template.py` | role marker 렌더링과 assistant-only label mask를 만든다. | 사용자/system/PAD는 `-100`, assistant target만 label로 둔다. | mask exact equality |
| `src/llmex/chat/mixer.py` | public+teacher train/heldout을 누출 없이 선택·게시한다. | heldout 우선, prompt/source overlap 차단, 길이 gate를 적용한다. | preflight/prepare/validate 동일 통계 |
| `src/llmex/chat/curriculum.py` | 품질 실패 범주의 결정적 합성 데이터와 기존 데이터 replay를 만든다. | suite 모든 user turn 비누출, split/source 분리, target-token 질량과 EOS를 검증한다. | curriculum preflight/prepare/validate byte 동일 |
| `src/llmex/chat/runtime.py` | SFT cache, 학습·재개·평가·생성을 담당한다. | fresh run, base SHA, 128 MiB token cache, target-token accumulation을 강제한다. | cached/uncached batch 동일·resume 동일 |
| `src/llmex/chat/quality.py` | 멀티턴 rollout과 EOS·반복·안전·오염 자동 gate를 계산한다. | 평균만이 아니라 profile/scenario worst case를 판정한다. | quality eval/validate 재계산 |
| `src/llmex/chat/quality_review.py` | blind template, 독립 review, adjudication, 서명 수동 gate를 검증한다. | 자동 gate 선행과 역할 독립성, target SHA를 강제한다. | unsigned/self-review 실패 |

대화 계층은 `data.py → template.py → mixer.py → curriculum.py → runtime.py → quality.py → quality_review.py` 순서로 만든다. curriculum은 고정 suite의 문장을 학습 데이터로 복제하지 않고 모든 user turn의 exact hash overlap을 차단해야 한다. 자동 품질 통과가 수동 승인을 대체하지 않으며, 수동 승인 파일을 개발자가 스스로 만들어 통과시키면 안 된다.

## 8. Teacher 증류 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/distill/__init__.py` | 증류 공개 경계를 선언한다. | collector 진입점만 노출한다. | import smoke |
| `src/llmex/distill/schema.py` | source provenance, logical request, spool record를 정의한다. | request ID와 source SHA 결속을 필수화한다. | 변조 spool 거부 |
| `src/llmex/distill/prompts.py` | chat/wiki source에서 결정적 prompt inventory를 만든다. | 정규화, 중복 제거, hash split, exact target 수를 구현한다. | 입력 순서 변화 inventory 동일 |
| `src/llmex/distill/client.py` | OpenAI-compatible localhost HTTP 요청을 제한적으로 수행한다. | no redirect, 응답 byte 상한, timeout, secret echo 검사를 둔다. | fixture HTTP 실패 분류 |
| `src/llmex/distill/filters.py` | 길이·복사·반복·Unicode 기반 응답 필터를 제공한다. | canonical response와 rejection reason을 결정적으로 만든다. | 경계값 표적 테스트 |
| `src/llmex/distill/collector.py` | preflight→prepare→collect/resume→status→export→validate를 소유한다. | 요청별 원자 spool과 manifest/config/source binding을 강제한다. | 중단 재개·export 재검산 |

teacher 호출은 가장 늦게 붙인다. 먼저 `prompts.py` inventory와 `collector.py`의 offline fixture spool을 검증하고, 실제 endpoint에서는 `preflight_model`로 model identity를 확인한 뒤 수집한다.

## 9. 파이프라인·신뢰·릴리스 모듈

| 모듈 | 책임과 주요 입출력 | 직접 구현할 핵심 | 완료 증거 |
|---|---|---|---|
| `src/llmex/pipeline.py` | milestone 명령, 예산, 증거, 복구 상태를 조정한다. | shell 없이 argv 실행, timeout/사용량 상한, output 재검증을 한다. | 대기→증거→재개 drill |
| `src/llmex/trust.py` | root→policy→issuer Ed25519 신뢰 사슬과 statement context를 검증한다. | commit/config/artifact/role/expiry 결속을 확인한다. | 만료·역할·서명 변조 거부 |
| `src/llmex/release.py` | audit, wheel/sdist, checksum, SBOM, provenance, 외부 gate를 만든다. | 실제 배포 artifact digest와 독립 승인 증거를 사용한다. | `release audit/bundle/gate` |

`pipeline.py`는 도메인 계산을 다시 구현하지 않고 각 CLI를 실행하고 증거를 검증한다. `trust.py`와 `release.py`는 로컬 테스트 성공과 외부 공개 승인을 분리하는 마지막 경계다.

## 모듈별 학습 카드 작성법

각 파일을 직접 만들 때 다음 템플릿을 복사해 학습 노트에 채운다.

```markdown
### 모듈: src/llmex/...py

- 한 문장 책임:
- 입력 schema와 허용 범위:
- 출력 schema와 원자성:
- 소유하는 불변식:
- 의존하는 하위 모듈:
- 호출하는 상위 모듈:
- 반드시 실패해야 하는 세 사례:
- 최소 단위 테스트:
- 실제 CLI에서 도달하는 명령:
- 생성되는 artifact와 SHA:
```

## 검증 체크리스트

- [ ] 이 장의 표에 `find src/llmex -name '*.py'` 결과 57개가 모두 있다.
- [ ] 각 모듈의 대표 함수나 class를 소스에서 직접 찾았다.
- [ ] `__init__.py`와 CLI를 도메인 구현보다 먼저 과도하게 채우지 않았다.
- [ ] 각 데이터 경계에 정상·누락·변조 테스트가 있다.
- [ ] 각 장의 완료 증거가 실제 명령과 연결된다.

## 연습문제

1. `config.py`를 기능별 여러 파일로 나눌 때 순환 import 없이 유지할 dependency graph를 그려라.
2. `checkpoint.py`와 `chat/runtime.py`의 재개 계약에서 공통인 상태와 다른 상태를 표로 비교하라.
3. `quality.py`의 자동 판정과 `quality_review.py`의 사람 판정을 하나로 합치면 생기는 신뢰 문제를 설명하라.
4. 57개 모듈 중 외부 네트워크에 직접 접근하는 모듈만 찾고, redirect·timeout·응답 크기 제한을 감사하라.
