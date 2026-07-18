# 9장. 로컬 Teacher로 대화 데이터 증류하기

이 장에서는 이미 학습된 큰 언어 모델을 로컬 OpenAI 호환 서버에 띄우고, 그 응답을 작은 모델의 assistant-only SFT 데이터로 만드는 과정을 배운다. 여기서 “증류”는 teacher의 확률분포 전체를 맞추는 고전적 지식 증류가 아니라, teacher가 생성한 대화를 정제해 지도학습 표본으로 쓰는 응답 증류(response distillation)다.

## 학습 목표

- 논리 요청 inventory, spool, export를 분리하는 이유를 설명할 수 있다.
- train/heldout 누출 없이 prompt를 결정적으로 나눌 수 있다.
- 재시도 가능한 수집기와 실패-폐쇄 검증기를 작은 프로젝트에서 재구성할 수 있다.
- 휴리스틱 필터와 최종 안전성 판정의 차이를 구분할 수 있다.
- LLMEX의 실제 명령으로 수집 상태와 산출물을 검증할 수 있다.

## 선행지식

- JSON/JSONL과 SHA-256의 기본 개념
- HTTP 요청과 OpenAI 호환 `/v1/models`, `/v1/chat/completions`
- train/heldout split의 목적
- Python dataclass 또는 Pydantic 수준의 schema 검증

## 관련 실제 파일

- [정식 qwen36mtp 설정](../../configs/distill/qwen36mtp-10k.yaml)
- [증류 설정 schema](../../src/llmex/config.py)
- [logical request 생성](../../src/llmex/distill/prompts.py)
- [수집·재개·export·검증](../../src/llmex/distill/collector.py)
- [teacher HTTP client](../../src/llmex/distill/client.py)
- [휴리스틱 응답 필터](../../src/llmex/distill/filters.py)
- [증류 schema](../../src/llmex/distill/schema.py)
- [증류 회귀 테스트](../../tests/test_distill.py)
- [운영 실행 가이드](../teacher-distillation.md)

## 핵심 개념/수식

### 1. 전체 흐름

```text
공개 instruction + Wikipedia corpus
              │
              ▼
  결정적 logical request inventory
              │
              ▼
 local teacher ──> 요청별 spool JSON
              │       accepted/rejected/failed
              ▼
 train.jsonl + heldout.jsonl + manifest.json
              │
              ▼
 현재 inventory와 spool에서 전체 재유도 검증
```

inventory와 응답을 한 파일에 바로 쓰지 않는 것이 핵심이다. 요청 목록이 먼저 고정되어야 중단 후 어떤 요청이 끝났고 어떤 요청이 남았는지 알 수 있다. 요청별 spool은 한 파일이 손상되어도 나머지 완료 결과를 보존한다.

### 2. 결정적 요청 ID와 split

LLMEX는 Unicode와 공백을 정규화한 prompt의 SHA-256을 계산한다. 앞 24 hex를 ID에 사용하지만, 충돌과 split 판정에는 전체 hash를 쓴다.

\[
h = \operatorname{SHA256}(\operatorname{normalize}(prompt))
\]

heldout 비율을 basis point 단위 \(b\)로 두면 기본 split은 다음처럼 결정할 수 있다.

\[
split(h)=
\begin{cases}
heldout & \operatorname{int}(h_{0:16},16) \bmod 10000 < b\\
train & \text{otherwise}
\end{cases}
\]

단, upstream 데이터가 이미 heldout이면 반드시 heldout을 보존한다. LLMEX는 같은 upstream source SHA가 train과 heldout에 동시에 나타나도 중단한다.

작은 재구성 예시는 다음과 같다.

```python
import hashlib
import unicodedata

def logical_request(prompt: str, heldout_bp: int, upstream_split: str) -> dict:
    normalized = " ".join(unicodedata.normalize("NFC", prompt).split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    hashed = "heldout" if int(digest[:16], 16) % 10_000 < heldout_bp else "train"
    split = "heldout" if upstream_split == "heldout" else hashed
    return {"id": f"distill-{digest[:24]}", "prompt": normalized, "split": split}
```

### 3. 재개 가능한 spool

수집기는 각 요청을 독립된 spool 파일로 저장한다. 재실행할 때 다음 규칙을 적용한다.

```text
for request in inventory:
    if spool exists and schema/hash/config binding is valid:
        if status is accepted or rejected: skip
        if status is failed: retry
    else:
        call teacher with rate limit and bounded retry
        atomically publish one spool record
```

`accepted`뿐 아니라 `rejected`도 완료다. 같은 유해·반복 응답을 매번 다시 요청하면 비용과 결과가 흔들리기 때문이다. `failed`와 아직 파일이 없는 요청만 `resume` 대상이다.

진행률은 단순 spool 파일 수가 아니다.

\[
progress = \frac{accepted + rejected}{total}
\]

실패 항목은 완료로 세지 않으며 ETA는 관측 처리율이 0보다 클 때만 계산한다.

### 4. 필터는 최종 안전 gate가 아니다

현재 필터는 길이, 제어문자, 손상 Unicode, 설정된 위험 개념, 4-gram 반복률, prompt 복사율을 검사한다. 반복률은 다음과 같다.

\[
r_{repeat}=1-\frac{|\operatorname{unique}(G_4)|}{|G_4|}
\]

이는 빠른 pre-filter다. 우회 표현과 문맥상 위험성을 완전히 판정하지 못하므로 export manifest에도 `heuristic_pre_filter_not_final_safety_gate`라고 기록된다. 자동·수동 안전 gate를 생략할 근거가 아니다.

## 단계별 구현

1. 엄격한 `LogicalRequest`, `SpoolRecord`, `ChatRow` schema를 만든다.
2. 입력 prompt를 정규화하고 hash 기반 ID와 split을 만든다.
3. inventory 전체와 config fingerprint를 manifest에 봉인한다.
4. `/v1/models`에서 지정 모델이 존재하는지 preflight한다.
5. timeout, 최대 응답 bytes, 초당 요청 수, 최대 재시도를 제한한 client를 만든다.
6. 요청별 결과를 임시 파일에 쓰고 `fsync → replace`로 spool을 공개한다.
7. status는 모든 spool을 schema와 request/config hash에 다시 결속해 센다.
8. accepted 응답만 ChatRow로 바꾸고 canonical duplicate 응답을 제거한다.
9. train/heldout JSONL과 manifest에 provenance, 파일 SHA, release 정책을 기록한다.
10. validate에서 현재 inventory와 spool로 export를 다시 계산해 byte 단위로 비교한다.

## 실제 명령

HTTP teacher 없이 inventory·spool·mix·SFT 경계를 먼저 학습하려면 [20장 offline 대화 E2E](20-offline-chat-e2e.md)를 완료한다. 그 fixture는 teacher 응답을 새로 수집하지 않으며, 내부 전용 teacher manifest와 release block의 전달만 재현한다.

로컬 teacher가 `localhost:8081/v1`에서 `qwen36mtp`를 제공한다고 가정한다.

```bash
cp configs/distill/qwen36mtp-10k.yaml docs/book/examples/distillation-book.yaml
# distillation-book.yaml의 source_chat_files를 실제 저장소 상대 경로로 바꾼다.
uv run llmex config validate docs/book/examples/distillation-book.yaml --kind distillation
uv run llmex distill preflight --config docs/book/examples/distillation-book.yaml
uv run llmex distill prepare --config docs/book/examples/distillation-book.yaml
uv run llmex distill collect --config docs/book/examples/distillation-book.yaml
uv run llmex distill status --config docs/book/examples/distillation-book.yaml
```

중단 후에는 완료 spool을 보존하며 재개한다.

```bash
uv run llmex distill resume --config docs/book/examples/distillation-book.yaml
uv run llmex distill export --config docs/book/examples/distillation-book.yaml
uv run llmex distill validate --config docs/book/examples/distillation-book.yaml
```

stock 설정의 `/tmp/llmex-public-sft/...`는 과거 실행 snapshot이므로 그대로 실행하지 않는다. 예를 들어 준비한 공개 대화가 `data/chat/public/train.jsonl`, `data/chat/public/heldout.jsonl`에 있다면 복사본을 다음처럼 고친다.

```yaml
source_chat_files:
  - data/chat/public/train.jsonl
  - data/chat/public/heldout.jsonl
corpus: data/processed/corpus-v1.jsonl.zst
```

## 예상 산출물

정식 설정의 run 디렉터리는 `runs/distill/qwen36mtp-10k-v5`다.

```text
runs/distill/qwen36mtp-10k-v5/
├── inventory.jsonl
├── run-manifest.json
├── state.json
├── spool/
│   └── distill-<24hex>.json
└── export/
    ├── train.jsonl
    ├── heldout.jsonl
    └── manifest.json
```

`status`에는 `total`, `completed`, `progress`, 상태별 `counts`, 사유별 `reasons`, 경과 시간, 유효 RPS와 ETA가 나온다. export manifest에는 train/heldout 개수와 SHA-256, accepted spool set fingerprint, upstream 라이선스, `redistribution_allowed=false`, `release_gate=blocked`가 포함된다.

## 검증 테스트

```bash
uv run pytest -q tests/test_distill.py
uv run ruff check src/llmex/distill tests/test_distill.py
uv run pyright
```

작은 프로젝트라면 최소한 다음 부정 테스트를 만든다.

- upstream heldout이 train으로 이동하면 실패
- 같은 upstream source가 두 split에 있으면 실패
- inventory에 없는 spool이 있으면 실패
- spool의 request/config/response hash를 바꾸면 실패
- incomplete 또는 failed 요청이 남은 상태에서 validate하면 실패
- export JSONL 한 글자를 바꾸면 재유도 결과와 불일치
- teacher output license나 release gate를 완화하면 실패

## 흔한 실패와 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| preflight에서 모델을 찾지 못함 | endpoint 또는 model 이름 불일치 | `/v1/models` 응답과 YAML의 `model`을 대조한다. |
| prepare에서 입력 파일 없음 | 공개 instruction 경로 또는 corpus 미준비 | 절대/상대 경로와 파일 권한을 확인한다. |
| collect가 느림 | RPS 제한, timeout, teacher 처리량 | 먼저 소규모 pilot으로 측정하고 무작정 concurrency를 높이지 않는다. |
| rejected가 많음 | 길이·반복·복사·위험 패턴 임계 초과 | `reasons`를 확인한다. 필터를 느슨하게 하기 전에 teacher prompt와 응답 품질을 고친다. |
| export 불가 | pending/failed 요청 존재 | `status`에서 남은 요청을 확인하고 `resume`한다. |
| validate checksum 실패 | spool 또는 export를 수동 편집 | 원본을 복구하거나 별도 새 run에서 다시 생성한다. |

## 체크리스트

- [ ] teacher endpoint는 loopback HTTP `/v1`인가?
- [ ] model 이름을 `/v1/models`로 확인했는가?
- [ ] source provenance와 upstream split을 보존하는가?
- [ ] inventory가 config fingerprint와 hash로 고정되는가?
- [ ] 요청별 spool이 원자적으로 저장되는가?
- [ ] rejected와 failed를 구분하는가?
- [ ] export 전에 completed가 total과 같은가?
- [ ] train/heldout prompt와 source overlap이 0인가?
- [ ] 내부 teacher 라이선스와 release 차단을 계승하는가?
- [ ] 휴리스틱 필터를 최종 안전 판정으로 오해하지 않았는가?

## 연습문제

1. hash split 대신 난수 셔플을 매 실행마다 다시 하면 재개와 검증에 어떤 문제가 생기는가?
2. `rejected`를 미완료로 취급할 때 발생하는 비용·재현성 문제를 설명하라.
3. 동일 prompt가 공개 instruction heldout과 Wikipedia train에 모두 있으면 어떤 우선순위가 안전한가?
4. canonical response 중복 제거를 spool 단계가 아니라 export 단계에서 하는 이유를 생각해 보라.
5. `max_response_chars`를 크게 늘렸을 때 데이터 품질과 운영 비용의 trade-off를 서술하라.
