# 5부. 파이프라인·신뢰·릴리스 모듈

이 챕터는 이미 검증된 도메인 명령을 장기 실행 파이프라인으로 묶고, 외부 승인과 배포 artifact를 암호학적으로 결속한다. 도메인 알고리즘을 이 계층에서 다시 구현하지 않는다.

### `src/llmex/pipeline.py`

- 책임: stage 명령, 예산, 증거, timeout과 복구 상태를 조정한다.
- 주요 계약: `preflight`, `run`, `recovery_drill`, `export`는 shell 문자열이 아닌 argv를 실행하고 stage artifact를 재검증한다.
- 구현 순서: strict stage schema → 설정/입력 snapshot → dry preflight → 단일 stage 실행 → timeout·예산 검사 → 상태·증거 publish → 재개 순서다.
- 실패 사례: 허용되지 않은 외부 stage, 시간/메모리/출력 byte 초과, 예상 artifact 부재와 config fingerprint 변화는 즉시 실패해야 한다.
- 검증: `uv run pytest -q tests/test_m6_pipeline.py`와 `llmex pipeline preflight/run/status/drill/export`를 fixture 설정으로 실행한다.
- 완료 산출물: stage별 상태, stdout/stderr digest, evidence SHA와 재개 지점이 있는 pipeline bundle이다.

### `src/llmex/trust.py`

- 책임: root → policy → issuer Ed25519 신뢰 사슬과 statement context를 검증한다.
- 주요 계약: `load_trust_context`, `verify_statement_context`, `repository_commit`은 서명뿐 아니라 role, repository commit, config/artifact SHA와 만료 시각을 함께 확인한다.
- 구현 순서: canonical JSON → 공개키 decode → root policy 서명 → issuer 권한/기간 → statement payload/context → 역할별 fingerprint 순서다.
- 실패 사례: 만료, 다른 commit, 잘못된 역할, issuer 교체, payload 한 byte 변조와 dirty repository 오인은 거부한다.
- 검증: `uv run pytest -q tests/test_m7_release.py`의 만료·역할·변조·context 테스트를 실행한다.
- 완료 산출물: 검증된 `TrustContext`와 특정 역할·대상에 결속된 issuer authority fingerprint다.

### `src/llmex/release.py`

- 책임: source audit, wheel/sdist checksum, SBOM, provenance와 외부 gate를 만든다.
- 주요 계약: `audit`, `bundle`, `external_gate`는 실제 추적 파일과 배포 bytes를 사용하며 로컬 성공을 외부 승인으로 바꾸지 않는다.
- 구현 순서: tracked file 감사 → build artifact 선택 → checksum manifest → dependency SBOM → provenance statement → 독립 승인 statement 검증 → 원자 bundle 순서다.
- 실패 사례: Git 미추적 필수 파일, checksum 불일치, 누락 license, 같은 역할의 자기 승인과 잘못된 target SHA는 실패한다.
- 검증: `uv run pytest -q tests/test_m7_release.py`, `uv run llmex release audit`, 필요 시 `uv build`와 `release bundle`을 실행한다.
- 완료 산출물: 재현성 bundle과, 실제 외부 증거가 모두 있을 때만 통과하는 release gate artifact다.

## 구현 실습 순서

1. fixture stage 하나로 pipeline preflight와 상태 파일을 만든다.
2. stage가 중간에 실패하도록 해 마지막 검증 지점에서 재개되는지 확인한다.
3. 임시 키로 신뢰 사슬 fixture를 만들고 payload·역할·만료를 각각 변조한다.
4. 작은 wheel/sdist를 빌드하고 실제 bytes에서 checksum과 SBOM을 만든다.
5. 외부 승인 파일이 없을 때 release gate가 실패-폐쇄인지 확인한다.

## 챕터 종료 체크

- [ ] pipeline은 shell injection 없이 argv만 실행한다.
- [ ] 재개는 디렉터리 존재가 아니라 검증된 stage evidence를 기준으로 한다.
- [ ] 서명 검증은 key만이 아니라 역할·대상·commit·만료를 포함한다.
- [ ] release checksum은 build 이전 예상값이 아니라 실제 배포 bytes에서 계산한다.
- [ ] 외부 승인 부재는 `미실행/차단`으로 남는다.
