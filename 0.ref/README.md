# LLMEX 참조 코드

이 디렉터리는 기반 교재 저장소 `llm_math_book_org`에서 선별한 교육용 원본 코드다. LLMEX 구현 시 수식 대응, tensor shape, 최소 학습 루프와 benchmark를 확인하는 읽기 전용 참조로 사용한다.

## 원본

- 저장소: `/Users/dirmich/work/0.ai/0.books/llm_math_book_org`
- 복사 기준일: 2026-07-11
- 무결성: `SHA256SUMS` 참조
- 저작권과 라이선스: 원본 저장소의 조건을 따른다. 외부 공개 전에 원본 LICENSE를 확인하고 필요한 고지를 함께 제공한다.

## 파일별 사용처

| 참조 | LLMEX 구현에서 확인할 내용 |
|---|---|
| `notebooks/ch12_tokenizers.ipynb` | BPE와 byte-level 토큰화 개념, encode/decode |
| `notebooks/ch14_attention_mechanism.ipynb` | scaled dot-product attention과 causal mask |
| `notebooks/ch15_multi_head_attention.ipynb` | head split/merge와 MHA shape |
| `notebooks/ch16_positional_encoding.ipynb` | 위치 인코딩 기준 구현; LLMEX의 RoPE와 비교 |
| `notebooks/ch17_transformer_architecture.ipynb` | Pre-LN block과 residual |
| `notebooks/ch18_gpt_anatomy.ipynb` | decoder-only GPT 구성과 parameter count |
| `notebooks/ch19_pretraining.ipynb` | shifted next-token loss와 학습 루프 |
| `notebooks/ch27_flash_attention.ipynb` | memory-efficient attention 원리와 benchmark |
| `notebooks/ch31_nano_gpt.ipynb` | RMSNorm, RoPE, GQA, SwiGLU를 포함한 통합 기준 |
| `notebooks/ch32_mini_llm_project.ipynb` | 후속 LoRA/SFT/양자화 참고; MVP 사전학습 범위 밖 |
| `benchmarks/*.py` | 성능 측정 형식과 regression 비교 |
| `src/llm_math/bench.py` | warmup/repeat/timing helper 참고 |
| `src/llm_math/data.py` | 교육용 데이터 helper 참고 |

## 사용 규칙

1. `0.ref` 코드를 `src/llmex`에서 import하지 않는다.
2. 참조 코드를 직접 수정하지 않는다. 개선은 production 코드와 테스트에 새로 구현한다.
3. notebook의 출력값을 정답으로 맹신하지 않고 수식, PyTorch 공식 동작과 독립 테스트로 검증한다.
4. 교재 코드는 작은 입력을 설명하기 위한 구현이다. Wikipedia streaming, distributed-safe checkpoint, DGX Spark unified memory 요구를 충족한다고 가정하지 않는다.
5. LLMEX에서 차용한 알고리즘이나 코드가 있으면 새 파일의 주석 또는 문서에 참조 파일을 기록한다.
6. `SHA256SUMS`가 달라지면 원본 갱신인지 로컬 변경인지 확인하고 결정 기록을 남긴다.

## 빠른 탐색

```bash
rg -n "class .*Attention|class .*GPT|RMSNorm|RoPE|SwiGLU|get_batch|CrossEntropy" 0.ref/llm_math_book
(cd 0.ref && shasum -a 256 -c SHA256SUMS)
```
