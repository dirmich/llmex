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
