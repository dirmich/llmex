# 출처와 권위 순서

## 프로젝트 내부 권위

1. 현재 `src/llmex` 구현과 `tests`
2. 현재 `configs`, CLI `--help`, 실제 run artifact
3. 현재 `docs`와 `docs/book`
4. `../knowledge_base/Codex/LLMEX/프로젝트 계획.md`의 외부 운영 snapshot
5. `0.ref`의 읽기 전용 교육 참조

상위 자료와 충돌하면 상위 자료를 따른다. wiki의 macOS 경로, 과거 checkpoint와 1-batch 수치는 현재 상태로 복제하지 않는다.

## 외부 자료 범주

- Wikimedia: dump URL, checksum, format, license와 attribution
- NVIDIA: DGX Spark hardware, container runtime, 고정 NGC image digest
- PyTorch·tokenizers·Pydantic·Typer: 선택한 버전의 공식 API 계약
- teacher output: source provenance, endpoint model identity, 생성 시각·설정·request ID

외부 문장을 길게 복제하지 않고 필요한 사실을 요약하며 URL, 접근일, 적용 버전과 license를 기록한다.
