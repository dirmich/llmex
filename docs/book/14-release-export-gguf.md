# 14. 릴리스 증거, export, GGUF와 llama.cpp

> 현재 상태: release audit/bundle/gate는 구현돼 있다. GGUF converter와 llama.cpp parity CLI는 아직 구현되지 않은 후속 연구실 계약이다. 이 절을 실행 완료로 표시하려면 실제 converter 코드와 자동 parity test를 먼저 추가해야 한다.

## 학습 목표

- wheel/sdist, checksum, SBOM, provenance bundle의 신뢰 경계를 이해한다.
- 로컬 자동 통과와 법무·품질·공개 승인을 분리한다.
- 아직 저장소에 구현되지 않은 GGUF 변환과 llama.cpp parity의 안전한 후속 계약을 설계한다.

## 선행지식

패키징, 공개키 서명, artifact digest와 [13장](13-manual-blind-review.md)이 필요하다.

## 관련 실제 파일

- [release 구현](../../src/llmex/release.py), [trust 검증](../../src/llmex/trust.py), [release CLI](../../src/llmex/cli.py)
- [release 테스트](../../tests/test_m7_release.py), [릴리스 체크리스트](../release-checklist.md), [재현성](../reproducibility.md)
- [보안 경계](../security.md), [acceptance matrix](../acceptance-matrix.md), [모델 카드](../model-card.md)

## 핵심 개념

artifact digest는 파일 identity, SBOM은 dependency inventory, provenance는 “어떤 소스와 과정이 이 artifact를 만들었는가”를 진술한다. 서명된 승인도 subject의 version·canonical Git commit·config fingerprint·evidence SHA·role·발급/만료가 현재 대상과 일치할 때만 유효하다.

LLMEX의 현재 release bundle은 Python 도구 패키지용이다. GGUF converter와 llama.cpp parity runner는 아직 production CLI로 구현되지 않았다. 따라서 이 장의 GGUF 부분은 완료 기능 설명이 아니라 구현해야 할 acceptance contract다.

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

### GGUF/llama.cpp 후속 구현 계약

1. source checkpoint·tokenizer·model config SHA와 converter version을 pin한다.
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

GGUF 구현 후 목표 명령 예시는 다음과 같으며, 현재 CLI에 있다고 가정하면 안 된다.

```text
llmex export gguf --checkpoint ... --tokenizer ... --output model-f16.gguf
llmex export parity --gguf model-f16.gguf --prompts parity.jsonl
```

## 예상 산출물

현재는 wheel/sdist, `artifact-checksums.json`, SBOM, in-toto provenance와 승인 검증 결과가 생성된다. 후속 GGUF는 model file, conversion manifest, tensor inventory, PyTorch/llama.cpp parity JSON을 가져야 한다.

## 검증 테스트

- wheel SHA가 checksum·SBOM property·provenance subject에서 일치한다.
- 승인 role/서명/commit/config/evidence SHA/만료 변조를 거부한다.
- manual quality evidence가 없으면 외부 공개 gate가 실패한다.
- 네 gate 중 하나라도 없거나 서로 다른 trust snapshot/commit을 요구하면 실패한다.
- manual report의 schema·fingerprint·finite/range·교차 필드 의미가 모순이면 실패한다.
- GGUF 후속 테스트는 tensor 수·shape, tokenizer IDs, greedy parity와 양자화 회귀를 포함한다.

## 흔한 실패와 해결

- `release audit` 통과=모델 공개 가능: audit는 로컬 도구 경계다. 수동 품질·법무·책임자 승인이 별도다.
- GGUF 변환 성공=동일 모델: tokenizer/chat template와 logits parity가 없으면 증명되지 않는다.
- 양자화부터 시작: converter 오류와 양자화 오차를 분리할 수 없다. F16 parity를 먼저 통과한다.

## 체크리스트

- [ ] package artifact와 provenance subject digest가 같다.
- [ ] 승인 신뢰 체인과 만료를 검증한다.
- [ ] GGUF 기능의 현재 미구현 상태를 구분한다.
- [ ] F16 parity 뒤에만 양자화 품질을 판정한다.

## 연습문제

1. wheel dependency 하나를 누락한 SBOM을 테스트가 잡도록 하라.
2. GGUF metadata에 필요한 LLMEX model 필드를 표로 정리하라.
3. logits 절대 오차와 greedy token parity 중 어떤 기준을 우선할지 논증하라.
