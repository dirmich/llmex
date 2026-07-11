# M6 장기 실행·복구 runbook

## 상태와 사전 검사

```bash
uv run llmex pipeline preflight --config configs/pipeline/m6-baseline.yaml
uv run llmex pipeline status --config configs/pipeline/m6-baseline.yaml
```

외부 증거는 `runs/m6-baseline/evidence/`에 둔다. 빈 파일이나 자기 승인 파일을 만들지 말고 감사자·장비·입력 checksum·명령·시각·판정을 JSON에 기록한다.

## 실행과 재개

```bash
uv run llmex pipeline run --config configs/pipeline/m6-baseline.yaml
uv run llmex pipeline run --config configs/pipeline/m6-baseline.yaml --allow-external
uv run llmex train resume --config configs/training/baseline-100m.yaml \
  --checkpoint runs/baseline-100m/checkpoints/latest.pt
```

완료 단계와 출력이 모두 남아 있으면 재개 시 건너뛴다. 설정 fingerprint가 바뀌면 기존 상태 재사용을 거부한다. `scripts/llmex-baseline.service`를 `/etc/systemd/system/`에 배치해 container 실패 시 재시작할 수 있다. tmux는 관찰용이며 내구성 경계는 systemd, Docker bind mount, 원자적 checkpoint다.

## 실패·복구 drill

```bash
uv run llmex pipeline drill --config configs/pipeline/m6-baseline.yaml
kill -TERM $(cat runs/baseline-100m/trainer.pid)  # 실제 drill에서만
uv run llmex train resume --config configs/training/baseline-100m.yaml
```

SIGTERM 뒤 `latest.pt`, `중단` metric, sampler/RNG/fingerprint 복구를 확인한다. checksum, attribution, split 누출, NaN/Inf, checkpoint 복구 실패, 예산 120% 초과는 즉시 중단 조건이다.

## 보고서 내보내기

```bash
uv run llmex pipeline export --config configs/pipeline/m6-baseline.yaml
cat runs/m6-baseline/dashboard.md
```

전체 dump와 장기 학습이 미완료인 동안 정상 상태는 `외부 게이트 대기`다.

## 1.2.0 외부 evidence와 telemetry

외부 단계 evidence는 `baseline-evidence` kind와 `baseline` role, issuer, UTC RFC3339 발급/만료,
subject Git commit/config fingerprint, artifact path/SHA-256 및 보호 CI 서명을 포함한다. 같은 대상에
결속된 `resource-usage.json`은 `resource-usage` kind, `final=true`, 누적 tokens/energy_kwh와 서명을
가져야 한다. 하나라도 없거나 만료·변조되면 `--allow-external`이어도 단계는 실행되지 않고 대기한다.

## 1.3.0 external stage 최종 telemetry 순서

실행 전 존재하는 `resource-usage.json`은 최종 승인으로 재사용하지 않는다. live polling은 조기 중단을 위한 보조 장치다. external command 종료 뒤 새로 생성된 final 진술이 실행 전 digest와 달라야 하며, Ed25519 issuer 서명과 commit/config/stage/run-id, 승인 token·energy 예산 및 실제 최종 사용량 상한을 모두 통과해야 단계가 완료된다. unsigned, `final=false`, stale replay, 변조, NaN/음수, 예산 초과는 전체 pipeline을 실패로 기록한다.
