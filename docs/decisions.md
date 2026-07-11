# LLMEX 결정 기록

## ADR-001: 처음부터 학습하는 base LM

- 상태: 승인
- 결정: 기존 모델 RAG/파인튜닝이 아니라 한국어 Wikipedia로 decoder-only LM을 처음부터 학습한다.
- 이유: 기반 교재의 토크나이저, Attention, 사전학습을 end-to-end로 검증하는 것이 핵심이다.
- 결과: 상용 챗봇 품질은 비목표이며 모델 한계를 명확히 공개한다.

## ADR-002: 날짜 고정 Wikimedia dump

- 상태: 승인
- 결정: 탐색은 `latest`, 실험은 날짜 URL과 checksum을 사용한다.
- 이유: `latest`는 시간이 지나면 다른 데이터가 되어 재현성을 깨뜨린다.

## ADR-003: 문서 단위 split

- 상태: 승인
- 결정: 정규화된 page ID/title hash로 train/validation/test를 나눈다.
- 이유: 같은 문서의 chunk가 여러 split에 들어가는 누출을 방지한다.

## ADR-004: byte-level BPE

- 상태: 승인
- 결정: Hugging Face tokenizers 기반 byte-level BPE와 byte fallback을 쓴다.
- 이유: 임의 Unicode를 표현하고 한국어 corpus에 맞는 어휘를 학습한다.

## ADR-005: 소형 modern decoder

- 상태: 승인
- 결정: Pre-Norm RMSNorm, RoPE, GQA, SwiGLU, tied embeddings, causal LM을 기본으로 한다.
- 이유: 교재의 nano-GPT를 유지하면서 현대적 구조를 실험 가능한 최소 단위로 구현한다.

## ADR-006: 전체 표본보다 검증 게이트 우선

- 상태: 승인
- 결정: sample/smoke/baseline 프로파일을 분리하고 sample E2E 통과 전 전체 dump와 GPU 학습을 금지한다.
- 이유: 데이터·shape·resume 오류를 비싼 학습 전에 발견한다.

## ADR-007: DGX Spark ARM64 컨테이너 실행

- 상태: 승인
- 결정: 본학습과 재현 환경은 DGX Spark의 NVIDIA Container Runtime과 버전 고정 NGC PyTorch ARM64 호환 이미지를 사용한다.
- 이유: Grace Blackwell, CUDA, PyTorch 조합을 host Python에 임의 설치하는 것보다 재현성과 호환성이 높다.
- 결과: source, data, artifacts, runs는 host NVMe volume에 두고 container 삭제와 무관하게 보존한다.

## ADR-008: unified memory headroom

- 상태: 승인
- 결정: 128GB unified memory의 최대 80%를 정상 운용 상한의 출발점으로 삼고 pilot 실측 후 조정한다.
- 이유: GPU와 CPU, OS, dataloader, page cache가 같은 메모리를 공유하며 과도한 swap은 학습을 사실상 정지시킬 수 있다.
- 결과: RSS, available memory, swap, PyTorch peak memory를 동시에 관측한다.

## ADR 템플릿

```text
## ADR-NNN: 제목
- 상태: 제안/승인/폐기
- 배경:
- 결정:
- 대안:
- 결과:
- 검증:
```
