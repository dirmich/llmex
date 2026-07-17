# 한국어 대화 SFT 실행 가이드

LLMEX 1.5.2는 Wikipedia 사전학습과 분리된 assistant-only 대화 학습 경로를 제공한다. 전체 Wikipedia corpus/tokenizer와 100k baseline 학습은 완료되었고 후속 전체 평가가 대기 중이다. SFT 실험 완료가 전체 평가, 대화 품질 또는 외부 공개 승인을 대신하지 않는다.

## JSONL 계약

입력은 UTF-8 JSONL이며 빈 행을 허용하지 않는다. 각 행은 `schema_version=1`, 고유 `id`, `train` 또는 `heldout` split, 번갈아 나오는 `user`/`assistant` messages, provenance와 `sha256`를 포함한다. 선택적인 `system`은 첫 turn에만 둔다. provenance에는 dataset, 원 출처, license, `YYYY-MM-DD` 수집일이 필수다.

행 hash는 `id`, `messages`, `provenance`, `split`의 canonical JSON fingerprint다. loader는 파일 SHA-256, 행 hash, 중복 ID, split, 허용 license를 실패-폐쇄로 검증한다. train/heldout에 같은 행 hash가 있으면 학습하지 않는다. 원문 라이선스를 직접 검토해 `allowed_licenses`에 명시해야 하며, 이 설정은 법률 자문이나 재배포 허가를 자동 생성하지 않는다.

## Template와 masking

고정 template는 `<|system|>`, `<|user|>`, `<|assistant|>` 역할 머리말과 줄바꿈을 사용한다. system/user/역할 머리말/padding은 label `-100`으로 마스킹하고 assistant 본문과 assistant EOS만 loss에 포함한다. 왼쪽 truncation 후 assistant target이 남지 않으면 거부한다.

## 실행과 재개

`configs/sft/smoke.yaml`의 경로, 모델 형상과 허용 라이선스를 실제 artifact에 맞춘다. 기존 사전학습 checkpoint는 `base_checkpoint`로 초기화한다. 형상이 정확히 일치하지 않거나 안전한 `weights_only` 역직렬화가 실패하면 중단한다.

```bash
uv run llmex config validate configs/sft/smoke.yaml --kind sft
uv run llmex sft train --config configs/sft/smoke.yaml
uv run llmex sft resume --config configs/sft/smoke.yaml
uv run llmex sft eval --config configs/sft/smoke.yaml --checkpoint runs/sft-smoke/checkpoints/latest.pt
uv run llmex sft generate --config configs/sft/smoke.yaml --checkpoint runs/sft-smoke/checkpoints/latest.pt --prompt "안녕하세요"
```

checkpoint는 모델, optimizer, scheduler step, RNG와 결정적 data cursor를 원자적으로 저장하고 config/model/tokenizer/train/heldout fingerprint가 모두 같을 때만 재개한다. `max_steps`만 늘려 같은 run을 이어갈 수 있다.

heldout 평가는 assistant-only NLL/perplexity와 생성별 반복률, 금지 문자열, EOS 도달을 기록한다. 기능 smoke는 독립적인 한국어 안전성 평가나 실제 사용자 배포 승인을 대신하지 않는다.
