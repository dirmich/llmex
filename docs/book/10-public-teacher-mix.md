# 10장. 공개 데이터와 Teacher 데이터를 누출 없이 혼합하기

teacher export를 얻었다고 바로 공개 instruction과 이어 붙이면 안 된다. 같은 prompt나 같은 upstream source가 train과 heldout에 동시에 들어갈 수 있고, 내부 전용 teacher 응답의 배포 제한이 사라질 수 있다. 이 장에서는 heldout 우선 격리와 provenance 결속을 가진 결정적 mix를 만든다.

## 학습 목표

- prompt overlap과 provenance source overlap의 차이를 설명할 수 있다.
- heldout 우선 선택, 중복 제거, 길이 gate를 재구성할 수 있다.
- teacher manifest SHA pin이 왜 필요한지 설명할 수 있다.
- 혼합 데이터의 라이선스가 checkpoint까지 전파되는 경로를 추적할 수 있다.
- LLMEX mix 명령과 산출물을 검증할 수 있다.

## 선행지식

- 9장의 teacher export 구조
- chat template과 tokenizer의 기본 원리
- SHA-256, manifest, provenance
- train/heldout 평가 누출의 의미

## 관련 실제 파일

- [mix 설정 schema](../../src/llmex/config.py)
- [결정적 mixer](../../src/llmex/chat/mixer.py)
- [ChatRow와 canonical prompt](../../src/llmex/chat/data.py)
- [chat 렌더링과 tokenization](../../src/llmex/chat/template.py)
- [mixer 회귀 테스트](../../tests/test_sft_mixer.py)
- [SFT 실행 가이드](../chat-sft.md)
- [teacher export 가이드](../teacher-distillation.md)

현재 저장소에는 정식 10k export가 완료된 뒤 SHA를 채울 canonical mix YAML이 아직 고정되어 있지 않다. 실제 실행 전 `SFTMixConfig` 필드를 사용해 별도 YAML을 만들고 teacher manifest의 현재 SHA-256을 넣어야 한다.

## 핵심 개념/수식

### 1. 네 입력과 하나의 신뢰점

mix는 네 JSONL을 입력으로 받는다.

```text
public train ─┐
public heldout ├─> selection ─> train.jsonl
teacher train ┤              └> heldout.jsonl
teacher heldout┘
        ▲
        └── SHA-256으로 고정된 teacher export manifest
```

teacher JSONL의 SHA만 직접 적는 대신 manifest를 pin하면 inventory, accepted spool set, 라이선스, release 정책까지 함께 결속할 수 있다. mixer는 manifest 안의 train/heldout SHA와 실제 파일 SHA가 같은지도 확인한다.

간단한 YAML 뼈대는 다음과 같다.

```yaml
schema_version: 1
name: ko-public-teacher-mix
seed: 42
tokenizer_dir: artifacts/tokenizers/bpe-16k
public_train_data: data/chat/public/train.jsonl
public_heldout_data: data/chat/public/heldout.jsonl
teacher_train_data: runs/distill/qwen36mtp-10k-v5/export/train.jsonl
teacher_heldout_data: runs/distill/qwen36mtp-10k-v5/export/heldout.jsonl
teacher_manifest: runs/distill/qwen36mtp-10k-v5/export/manifest.json
expected_teacher_manifest_sha256: "현재 manifest의 64자리 SHA-256으로 교체"
output_dir: data/chat/ko-public-teacher-v1
allowed_licenses: [CC-BY-4.0, LicenseRef-LLMEX-Internal-Distillation]
max_seq_len: 1024
generation_reserve_tokens: 128
```

### 2. 두 종류의 누출

마지막 user prompt는 Unicode와 공백을 정규화한 뒤 hash한다.

\[
p = \operatorname{SHA256}(\operatorname{canonicalFinalUser}(messages))
\]

source identity는 명시 정보가 있으면 그것을 우선한다. 공개 변환 행처럼 `source_id`와
`source_sha256`이 모두 없으면 schema 검증을 통과한 입력 행 자체의 canonical SHA-256을
fallback으로 사용한다. 그렇지 않고 dataset/source URL만 공유하는 행을 하나의 원천으로
묶으면 heldout 한 행 때문에 공개 train 전체가 제외될 수 있다.

```python
if provenance.source_sha256 is not None:
    source_key = provenance.source_sha256
elif provenance.source_id is not None:
    source_key = fingerprint({
        "dataset": provenance.dataset,
        "source": provenance.source,
        "source_id": provenance.source_id,
    })
else:
    source_key = row.sha256
```

출력에는 기존 identity를 덮어쓰지 않는다. 두 identity가 모두 없던 행에만 원행 ID와
원행 SHA를 provenance로 승격한다. 그러면 mixer가 만든 split과 이후 SFT runtime이 같은
원천 키를 사용해 누출을 이중 검사할 수 있다.

prompt가 달라도 같은 원문에서 파생된 두 질문은 정보를 공유할 수 있다. 그래서 최종 조건은 둘 다 0이어야 한다.

\[
P_{train}\cap P_{heldout}=\varnothing,
\qquad
S_{train}\cap S_{heldout}=\varnothing
\]

### 3. heldout 우선 선택

선택 순서는 다음과 같다.

```text
1. 네 입력의 모든 heldout prompt와 source를 먼저 집합으로 만든다.
2. heldout에서 같은 prompt가 여러 개면 정렬 기준으로 하나만 남긴다.
3. train 후보가 heldout prompt와 겹치면 제외한다.
4. train 후보가 heldout source와 겹치면 제외한다.
5. train 내부에서는 (source, prompt) 중복을 하나만 남긴다.
6. 최종 prompt/source 교집합이 비었는지 다시 검사한다.
```

heldout이 우선이어야 평가 표본이 학습으로 역류하지 않는다. 중복 선택은 입력 순서에 기대지 않고 source key, row hash, origin을 정렬해 결정한다.

### 4. truncation 대신 길이 gate

mix 단계는 학습 중 무음 truncation을 피한다. 두 길이를 따로 검사한다.

\[
L_{prompt}+L_{reserve}\le L_{max}
\]

\[
L_{full\ chat}\le L_{max}
\]

첫 식은 추론 시 최소 생성 공간을 남긴다. 둘째 식은 assistant 정답이 학습 중 잘리지 않게 한다.

```python
if prompt_tokens + generation_reserve > max_seq_len:
    exclude("prompt_too_long")
elif full_chat_tokens > max_seq_len:
    exclude("sequence_too_long")
else:
    keep(row)
```

## 단계별 구현

1. 네 입력의 각 행을 엄격한 ChatRow schema로 검증한다.
2. split 값과 허용 라이선스를 확인한다.
3. 각 행에 origin, canonical prompt hash, source key를 붙인다.
4. teacher manifest 자체 SHA와 내부 파일 SHA/count/release 정책을 검증한다.
5. 현재 tokenizer manifest를 고정하고 두 길이 gate를 적용한다.
6. heldout 우선 규칙으로 train/heldout을 선택한다.
7. 최종 overlap을 다시 검사한다.
8. 선택 행을 안정된 순서와 canonical JSONL로 직렬화한다.
9. 입력·제외 사유·분포·출력 SHA·release 정책을 manifest에 기록한다.
10. lock과 staging에서 train, heldout, manifest 순으로 원자 publish한다.
11. validate는 현재 네 입력에서 전체 결과를 재유도해 byte 단위로 비교한다.

## 실제 명령

먼저 teacher export manifest SHA를 계산해 YAML에 고정한다.

```bash
sha256sum runs/distill/qwen36mtp-10k-v5/export/manifest.json
mkdir -p docs/book/examples
# 위 YAML을 docs/book/examples/sft-mix-book.yaml로 저장하고 SHA 문자열을 실제 값으로 교체한다.
uv run llmex config validate docs/book/examples/sft-mix-book.yaml --kind sft-mix
uv run llmex sft preflight-mix --config docs/book/examples/sft-mix-book.yaml
uv run llmex sft prepare-mix --config docs/book/examples/sft-mix-book.yaml
uv run llmex sft status-mix --config docs/book/examples/sft-mix-book.yaml
uv run llmex sft validate-mix --config docs/book/examples/sft-mix-book.yaml
```

따옴표 안 설명 문자열은 placeholder이므로 그대로 validate하지 않는다. 현재 SHA를 넣고 공개 JSONL·teacher export·04장 tokenizer가 모두 존재하는지 확인한 뒤 검증한다.

`preflight-mix`는 파일을 쓰지 않고 선택 수와 release 상태를 계산한다. `prepare-mix`는 이미 완전한 동일 출력을 발견하면 검증 후 재사용하며, 부분 출력은 덮어쓰지 않는다.

## 예상 산출물

```text
data/chat/ko-public-teacher-v1/
├── train.jsonl
├── heldout.jsonl
└── manifest.json
```

manifest의 중요한 항목은 다음과 같다.

- 네 input의 path, SHA-256, row 수, split, origin
- teacher manifest SHA와 핵심 fingerprint
- tokenizer manifest SHA
- `max_seq_len`, generation reserve, truncation 금지 정책
- 선택 train/heldout 수와 제외 사유
- origin/license/dataset 분포
- output SHA와 fingerprint
- prompt/source overlap 0
- `redistribution_allowed`와 `release_gate`

teacher 내부 전용 라이선스가 한 건이라도 입력에 있으면 최종 mix는 `redistribution_allowed=false`, `release_gate=blocked`다.

## 검증 테스트

```bash
uv run pytest -q tests/test_sft_mixer.py
uv run ruff check src/llmex/chat/mixer.py tests/test_sft_mixer.py
uv run pyright
```

필수 부정 테스트는 다음과 같다.

- teacher manifest SHA가 다르면 실패
- manifest의 JSONL SHA/count를 바꾸면 실패
- 허용되지 않은 라이선스가 있으면 실패
- heldout prompt/source와 겹치는 train 행은 제외
- 너무 긴 prompt와 전체 chat은 사유별로 제외
- 최종 train 또는 heldout이 비면 실패
- train/heldout/manifest 중 일부만 존재하면 실패
- 두 writer가 동시에 prepare하면 한쪽은 lock 충돌
- output 한 바이트 변조 후 validate하면 실패

## 흔한 실패와 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| teacher manifest checksum 오류 | export 후 파일 변경 또는 잘못된 SHA | `distill validate`를 다시 통과시키고 현재 manifest SHA를 pin한다. |
| 허용되지 않은 라이선스 | `allowed_licenses` 누락 | 사용 권리를 확인한 뒤 정확한 SPDX/LicenseRef만 추가한다. |
| 제외 행이 너무 많음 | sequence/generation reserve가 데이터와 불일치 | tokenizer 길이 분포를 보고 모델 context와 reserve를 함께 조정한다. |
| train이 비어 있음 | heldout 우선 격리로 모든 train 제거 | 입력 split과 source provenance를 점검한다. heldout을 억지로 train으로 이동하지 않는다. |
| 부분 출력 충돌 | 이전 실행이 중간에 중단 | 파일을 임의 병합하지 말고 원인과 staging을 감사한 뒤 별도 output_dir로 재실행한다. |
| release가 blocked | 내부 teacher 라이선스 포함 | 정상 동작이다. 수동으로 manifest를 완화하지 않는다. |

## 체크리스트

- [ ] teacher export가 먼저 validate를 통과했는가?
- [ ] teacher manifest 현재 SHA를 YAML에 고정했는가?
- [ ] 네 입력 split과 라이선스가 정확한가?
- [ ] 동일 tokenizer manifest를 사용하는가?
- [ ] prompt와 source overlap을 모두 검사하는가?
- [ ] heldout을 train보다 우선 격리하는가?
- [ ] prompt+reserve와 full chat 길이를 모두 검사하는가?
- [ ] 제외 사유와 데이터 분포를 manifest에 남기는가?
- [ ] 내부 전용 라이선스의 release 차단을 계승하는가?
- [ ] validate가 현재 입력에서 전체 출력을 재유도하는가?

## 연습문제

1. prompt hash만 검사하고 source identity를 검사하지 않을 때 가능한 누출 사례를 하나 작성하라.
2. 같은 heldout prompt에 공개 응답과 teacher 응답이 모두 있을 때 결정적 하나를 선택해야 하는 이유는 무엇인가?
3. `generation_reserve_tokens`가 너무 작거나 너무 클 때 각각 어떤 문제가 생기는가?
4. 내부 teacher 데이터가 1행뿐이어도 전체 release를 차단해야 하는 이유를 설명하라.
5. mix manifest를 SFT 설정의 `source_manifest`에 연결하면 어떤 무결성 속성이 추가되는가?
