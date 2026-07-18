# 14. 릴리스 증거, export, GGUF와 llama.cpp

> 현재 상태: release audit/bundle/gate와 private HF Llama·GGUF 변환 CLI가 구현돼 있다. 기존 SFT checkpoint에서 Transformers logits와 llama.cpp F16 greedy/EOS parity를 확인했다. 선택된 최종 checkpoint도 같은 검증을 다시 통과해야 하며 외부 공개 승인은 별도다.

## 학습 목표

- wheel/sdist, checksum, SBOM, provenance bundle의 신뢰 경계를 이해한다.
- 로컬 자동 통과와 법무·품질·공개 승인을 분리한다.
- HF Llama와 GGUF 변환의 tensor·tokenizer·private release 경계를 이해한다.

## 선행지식

패키징, 공개키 서명, artifact digest와 [13장](13-manual-blind-review.md)이 필요하다.

## 관련 실제 파일

- [release 구현](../../src/llmex/release.py), [모델 export](../../src/llmex/model/export.py), [GGUF wrapper](../../scripts/convert_llmex_hf_to_gguf.py), [release CLI](../../src/llmex/cli.py)
- [release 테스트](../../tests/test_m7_release.py), [릴리스 체크리스트](../release-checklist.md), [재현성](../reproducibility.md)
- [보안 경계](../security.md), [acceptance matrix](../acceptance-matrix.md), [모델 카드](../model-card.md)

## 핵심 개념

artifact digest는 파일 identity, SBOM은 dependency inventory, provenance는 “어떤 소스와 과정이 이 artifact를 만들었는가”를 진술한다. 서명된 승인도 subject의 version·canonical Git commit·config fingerprint·evidence SHA·role·발급/만료가 현재 대상과 일치할 때만 유효하다.

LLMEX의 release bundle은 Python 도구 패키지용이고 모델 export는 별도다. `export-hf`는 checkpoint를 immutable snapshot으로 한 번 읽어 SHA·fingerprint·finite tensor·shape·release 차단을 검증한다. 인접쌍 RoPE Q/K를 HF Llama half-split 배열로 바꾸고 학습과 같은 BOS·assistant EOS·줄바꿈 정규화 chat template를 기록한다. `export-gguf`는 예상 HF manifest SHA와 고정 artifact 집합을 재검증한 뒤 llama.cpp 공식 converter를 격리 실행한다.

## 단계별 구현

### 현재 구현 재구성

1. Git tracked 파일을 열거하되 secret·개인 절대 경로·`0.ref` import를 감사한다.
2. wheel/sdist를 isolated build하고 artifact SHA manifest를 만든다.
3. wheel METADATA의 runtime dependency로 CycloneDX SBOM을 만든다.
4. artifact를 in-toto provenance subject로 결속한다.
5. manual quality evidence와 legal/baseline/quality-release/release 네 승인을 현재 release target에 검증한다.

```python
target = {"version": version, "git_commit": head, "config_fingerprint": cfg_fp}
for approval, role in required:
    verify_signature(approval)
    require_exact_subject(approval, target, role)
    require_sha(approval["evidence"])
```

`release gate`는 invocation 시작에 canonical Git commit과 root-signed policy·issuer map을 `TrustContext` 하나로 snapshot한다. 법무, 장기 baseline, 수동 품질, 공개 배포 네 서명은 모두 그 context와 동일 target commit에서 검증된다.

수동 품질 evidence는 `gate-manifest.json`이다. verifier는 manifest/report의 exact key schema, canonical fingerprint, report SHA, finite metric과 허용 범위, 최소 100 sample, worst 값, mean-core/dimension 평균, `rate × sample` 정수 count, `safety_responses ≤ sample_responses`, disagreement 상한, reviewer/submission 3개 또는 adjudicator 포함 4개 관계를 확인한다. 그 뒤 별도의 `quality-release/manual-quality-gate-approval` 서명이 이 evidence SHA를 승인해야 한다. release는 원래 raw review를 다시 채점하지 않는다.

### GGUF/llama.cpp 구현 계약

1. source checkpoint·HF manifest·tokenizer SHA와 llama.cpp checkout을 기록한다.
2. tied embedding, RMSNorm epsilon, RoPE theta, GQA head 수, special token/EOS와 chat template를 GGUF metadata에 보존한다.
3. 우선 F16/BF16 무양자 변환을 만들고 tensor name/shape/count/hash inventory를 검증한다.
4. PyTorch와 llama.cpp에 같은 token IDs를 입력해 첫 N개 step logits top-k, greedy token IDs, EOS와 stop 이유를 비교한다.
5. 그 뒤 Q8/Q4 등 양자화를 별도 artifact로 만들고 허용 품질 회귀 임계값을 정한다.

## 실제 명령

현재 구현:

```bash
uv run llmex release audit
uv run llmex release bundle --output dist/reproducibility
uv run llmex release gate --help
uv run llmex release gate --approvals approvals/release-approvals.json --repository-root .
uv run pytest -q tests/test_m7_release.py
```

`approvals/release-approvals.json`은 target과 정확히 네 gate를 가진다. 아래는 구조를 보여 주는 축약 예시이며 실제 issuer·시간·evidence SHA·Ed25519 signature는 보호 CI/KMS/HSM이 발급해야 한다.

```json
{
  "schema_version": 1,
  "target": {"version": "1.8.1", "git_commit": "<canonical commit>", "config_fingerprint": "<64hex>"},
  "gates": {
    "법무 검토": {"approved": true, "issuer": "<legal issuer>", "role": "legal", "kind": "legal-approval", "approver": "<identity>", "issued_at": "<UTC RFC3339>", "expires_at": "<UTC RFC3339>", "evidence": {"path": "legal-evidence.json", "sha256": "<64hex>"}, "signature": "<base64>"},
    "장기 baseline": {"approved": true, "issuer": "<baseline issuer>", "role": "baseline", "kind": "baseline-evidence", "approver": "<identity>", "issued_at": "<UTC RFC3339>", "expires_at": "<UTC RFC3339>", "evidence": {"path": "baseline-evidence.json", "sha256": "<64hex>"}, "signature": "<base64>"},
    "수동 품질 평가": {"approved": true, "issuer": "<quality issuer>", "role": "quality-release", "kind": "manual-quality-gate-approval", "approver": "<identity>", "issued_at": "<UTC RFC3339>", "expires_at": "<UTC RFC3339>", "evidence": {"path": "gate-manifest.json", "sha256": "<64hex>"}, "signature": "<base64>"},
    "공개 배포 결정": {"approved": true, "issuer": "<release issuer>", "role": "release", "kind": "release-approval", "approver": "<identity>", "issued_at": "<UTC RFC3339>", "expires_at": "<UTC RFC3339>", "evidence": {"path": "release-evidence.json", "sha256": "<64hex>"}, "signature": "<base64>"}
  }
}
```

placeholder를 그대로 실행하지 않는다. 네 approver는 서로 달라야 하고 evidence path는 approvals 파일 기준 상대 경로다. production policy에 신규 quality 역할이 없다면 실패가 정상이며 root private key 없이 policy를 고치지 않는다.

SHA는 실행 시 실제 파일에서 계산한 64자리 값을 사용한다.

```bash
CHECKPOINT=runs/<선택-run>/checkpoints/step-XXXXXXXX.pt
CHECKPOINT_SHA=$(sha256sum "$CHECKPOINT" | cut -d' ' -f1)

uv run llmex model export-hf \
  --config configs/sft/<선택-config>.yaml \
  --checkpoint "$CHECKPOINT" \
  --expected-checkpoint-sha256 "$CHECKPOINT_SHA" \
  --output-dir dist/<모델>-hf-private

HF_MANIFEST_SHA=$(sha256sum dist/<모델>-hf-private/export-manifest.json | cut -d' ' -f1)
uv run llmex model export-gguf \
  --hf-dir dist/<모델>-hf-private \
  --expected-hf-manifest-sha256 "$HF_MANIFEST_SHA" \
  --llama-cpp-dir ../llama.cpp \
  --output dist/<모델>-f16.gguf --outtype f16

../llama.cpp/build/bin/llama-completion \
  -m dist/<모델>-f16.gguf -no-cnv -ngl 99 \
  -p $'<bos><|user|>\n안녕하세요\n<|assistant|>\n' \
  -n 128 --temp 0 --repeat-penalty 1.2 --special
```

## 예상 산출물

wheel/sdist, `artifact-checksums.json`, SBOM, in-toto provenance와 승인 검증 결과 외에 HF 디렉터리의 `export-manifest.json`과 GGUF가 생성된다. manifest는 checkpoint·config·model·tokenizer fingerprint, artifact SHA/bytes, `redistribution_allowed=false`, `release_gate=blocked`, `hub_visibility=private`를 가진다.

## 검증 테스트

- wheel SHA가 checksum·SBOM property·provenance subject에서 일치한다.
- 승인 role/서명/commit/config/evidence SHA/만료 변조를 거부한다.
- manual quality evidence가 없으면 외부 공개 gate가 실패한다.
- 네 gate 중 하나라도 없거나 서로 다른 trust snapshot/commit을 요구하면 실패한다.
- manual report의 schema·fingerprint·finite/range·교차 필드 의미가 모순이면 실패한다.
- export 테스트는 Q/K 순열, chat template, manifest/artifact 변조, private mode와 충돌 없는 게시를 포함한다.
- 실제 검증은 Transformers logits argmax와 llama.cpp greedy token/EOS를 원본 LLMEX와 비교한다.

## 흔한 실패와 해결

- `release audit` 통과=모델 공개 가능: audit는 로컬 도구 경계다. 수동 품질·법무·책임자 승인이 별도다.
- GGUF 변환 성공=동일 모델: tokenizer/chat template와 logits parity가 없으면 증명되지 않는다.
- 양자화부터 시작: converter 오류와 양자화 오차를 분리할 수 없다. F16 parity를 먼저 통과한다.

## 체크리스트

- [ ] package artifact와 provenance subject digest가 같다.
- [ ] 승인 신뢰 체인과 만료를 검증한다.
- [ ] 선택 checkpoint의 HF/GGUF SHA와 parity 결과를 기록한다.
- [ ] F16 parity 뒤에만 양자화 품질을 판정한다.

## 연습문제

1. wheel dependency 하나를 누락한 SBOM을 테스트가 잡도록 하라.
2. GGUF metadata에 필요한 LLMEX model 필드를 표로 정리하라.
3. logits 절대 오차와 greedy token parity 중 어떤 기준을 우선할지 논증하라.
