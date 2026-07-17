# API와 CLI 문서

공개 Python API는 `llmex.__version__`과 안정된 CLI 계약이다. 내부 모듈은 호환성을 보장하지 않는다.

| 명령군 | 목적 |
|---|---|
| `config`, `fingerprint`, `run` | 설정·입력·실행 identity |
| `data`, `tokenizer` | corpus와 token shard 생성 |
| `model`, `train` | inspect, 학습, 재개, smoke |
| `sft` | 공개·teacher mix prepare/preflight/status/validate, SFT train/resume/eval/generate |
| `eval`, `generate`, `benchmark` | 품질·안전 평가와 추론 |
| `distill` | teacher preflight/prepare/collect/resume/status/export/validate |
| `pipeline` | preflight/run/status/drill/export |
| `release` | audit/bundle/gate |

사용자 출력과 오류는 한국어다. JSON 결과는 stdout, 로그는 stderr이며 종료 코드는 0 성공, 2 설정,
3 입력, 4 충돌, 5 무결성, 70 내부 오류다. option은 `llmex <명령> --help`로 확인한다.

## SFT mix CLI

| 명령 | 계약 |
|---|---|
| `llmex sft preflight-mix --config <경로>` | 입력 JSONL, teacher manifest SHA, tokenizer 길이와 최종 split 선택을 출력 생성 없이 검증한다. |
| `llmex sft prepare-mix --config <경로>` | 배타 lock·staging에서 결정적 train/heldout/manifest를 원자 publish한다. |
| `llmex sft status-mix --config <경로>` | 출력이 없으면 pending, 현재 입력에 결속된 완전 출력이면 ready를 반환한다. |
| `llmex sft validate-mix --config <경로>` | 출력을 현재 입력/config에서 재유도해 byte/hash와 release 상태를 검증한다. |

실제 옵션과 현재 설치된 명령은 다음으로 확인한다.

```bash
uv run llmex sft preflight-mix --help
uv run llmex sft prepare-mix --help
uv run llmex sft status-mix --help
uv run llmex sft validate-mix --help
```

정식 v5 수집이 완료되기 전에는 mix config에 임시 manifest SHA를 넣지 않는다. export/validate 뒤 생성된 teacher manifest의 SHA-256을 `expected_teacher_manifest_sha256`에 고정한다.
