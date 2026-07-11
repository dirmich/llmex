# API와 CLI 문서

공개 Python API는 `llmex.__version__`과 안정된 CLI 계약이다. 내부 모듈은 호환성을 보장하지 않는다.

| 명령군 | 목적 |
|---|---|
| `config`, `fingerprint`, `run` | 설정·입력·실행 identity |
| `data`, `tokenizer` | corpus와 token shard 생성 |
| `model`, `train` | inspect, 학습, 재개, smoke |
| `eval`, `generate`, `benchmark` | 품질·안전 평가와 추론 |
| `pipeline` | preflight/run/status/drill/export |
| `release` | audit/bundle/gate |

사용자 출력과 오류는 한국어다. JSON 결과는 stdout, 로그는 stderr이며 종료 코드는 0 성공, 2 설정,
3 입력, 4 충돌, 5 무결성, 70 내부 오류다. option은 `llmex <명령> --help`로 확인한다.
