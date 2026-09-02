# MiniMind·llm_math_book·LLMEX 비교

비교 기준은 2026-09-03에 확인한 각 저장소의 공개 README와 현재 LLMEX 코드·문서다.

## 프로젝트 성격

| 항목 | MiniMind | llm_math_book | LLMEX |
|---|---|---|---|
| 핵심 목적 | 0부터 소형 LLM을 만들며 구조와 학습 전 과정을 배우는 교육용 프로젝트 | LLM·수학·성능 실험을 노트북으로 따라 하는 공개 교재/연습 저장소 | Qwen3-14B를 제품 요구에 맞게 미세조정하고 재현성·품질을 검증하는 연구 도구 |
| 주요 산출물 | 64M Dense, 198M-A64M MoE 등 모델과 학습 코드 | Ch00~Ch32 노트북·해답, 한/영/일 자료, benchmark 유틸리티 | QLoRA adapter, 병합 safetensors, Q4 GGUF, 데이터·manifest·품질 보고서 |
| 학습 범위 | Pretrain, SFT, LoRA, DPO, PPO/GRPO/CISPO, Tool Use, Agentic RL, 증류 | 교육용 코드 실행·수학 실험·CPU/GPU 커널 검증 | assistant-only SFT/QLoRA, teacher 증류, identity·사주·tool 계약 검증 |
| 실행 방식 | Transformers·llama.cpp·vLLM·Ollama·WebUI | Jupyter/Colab, pytest·ruff·pyright·benchmark 스크립트 | llama.cpp GGUF, Qwen3 CLI, 로컬 quality/release gate |

## MiniMind와의 비교

MiniMind는 핵심 알고리즘을 PyTorch 원시 코드로 구현하고, 작은 모델을 단일 GPU에서 짧게 재현하는 데 초점을 둔다. Qwen3 생태계에 맞춘 Dense/MoE 구조, `<tool_call>`·`<think>` 토큰, OpenAI API와 WebUI까지 제공한다. [MiniMind README](https://github.com/jingyaogong/minimind#readme)

장점은 모델 내부 구조와 학습 루프를 직접 이해할 수 있고 실험 비용·시간이 낮다는 점이다. 단점은 모델 규모가 작아 14B Qwen3에 비해 일반 지식·추론·자연스러운 장문 대화 품질이 제한된다는 점, 처음부터 사전학습할 일반 코퍼스가 필요하다는 점이다.

LLMEX는 MiniMind처럼 처음부터 모델을 재현하려는 프로젝트가 아니라 이미 강한 Qwen3-14B를 보존하면서 도메인 기능을 주입한다. 따라서 실사용 대화 품질과 빠른 기능 보강은 LLMEX가 유리하지만, Transformer 내부를 한 줄씩 학습하는 교육 목적과 저비용 반복 실험은 MiniMind가 유리하다.

## llm_math_book과의 비교

`llm_math_book`은 모델 자체보다 학습자가 실행해 보는 교재와 실험 검증에 집중한다. 공개 범위는 Ch00~Ch32 노트북과 언어별 해답 96개이며, `pytest`, `ruff`, `pyright`, 노트북 문법 검사, CPU 기준 정답 비교, CUDA 커널 검증 명령을 제공한다. [llm_math_book README](https://github.com/dirmich/llm_math_book)

장점은 한·영·일 학습 자료, 단계별 노트북, 결정적 benchmark로 개념을 직접 확인할 수 있다는 점이다. 단점은 완성된 대화 모델이나 대규모 pretrain 파이프라인을 제공하는 저장소가 아니며, 노트북 중심이라 제품형 서버·GGUF release·도구 권한 관리가 별도라는 점이다.

LLMEX의 `docs/book`과 품질 gate는 llm_math_book의 교재·검증 철학과 비슷하지만, LLMEX는 실제 14B adapter/GGUF와 identity·사주·tool 계약까지 운영 대상으로 삼는다. 반대로 수학적 원리·커널 최적화·노트북 기반 단계 학습의 폭은 llm_math_book이 더 명확하다.

## 장단점 요약

### LLMEX의 강점

- Qwen3-14B의 기존 언어·추론 능력을 활용해 소형 scratch 모델보다 높은 출발점
- 한국어 identity, 사주 입력 검증, `calculate_saju` 호출 같은 명확한 제품 계약
- 라이선스·출처·heldout·오염·SHA-256·GGUF smoke를 자동 검증
- llama.cpp에서 바로 실행 가능한 Q4 산출물과 checkpoint/재현 문서

### LLMEX의 약점

- 원본 Qwen3와 Transformers/PEFT에 의존해 모델 내부 교육 효과가 낮음
- GGUF 단독 실행은 tool JSON 생성까지만 가능하며, 실제 tool dispatcher가 별도 필요
- 현재 텍스트 14B 중심으로 이미지·다중모달·수학 커널 실험은 제한적
- 도메인 데이터가 부족하거나 system 지침을 과도하게 넣으면 일반 대화가 identity/도메인 문장으로 고정될 위험

### MiniMind의 강점

- 구조·토크나이저·pretrain부터 RL까지 전체 과정을 직접 재현
- 소형 모델이라 GPU 비용과 실험 대기 시간이 짧음
- Tool Use·Agentic RL·MoE를 교육용으로 한 저장소에서 확인 가능

### MiniMind의 약점

- 작은 파라미터 규모로 실사용 대화·추론 품질에 한계
- 처음부터 학습해야 하므로 데이터와 pretrain 시간이 필요
- 특정 사주 계산이나 운영형 release 서명·provenance는 사용자가 추가해야 함

### llm_math_book의 강점

- 32장 분량의 단계별 노트북과 한국어·영어·일본어 해답
- CPU 정답 기준과 CUDA benchmark를 함께 두어 실험 결과를 검증
- 수학·성능·코드 품질을 pytest/ruff/pyright로 반복 확인

### llm_math_book의 약점

- 자체 대화 모델이나 production inference server가 주 산출물이 아님
- 노트북 실험을 실제 14B 모델 학습·GGUF 배포로 연결하려면 별도 통합 필요

## 권장 조합

1. `llm_math_book`으로 토크나이징·attention·학습·평가·성능 측정 기초를 단계별로 익힌다.
2. MiniMind로 작은 Dense/MoE 모델을 처음부터 pretrain/SFT하고 Tool Use·Agentic RL 구조를 실습한다.
3. LLMEX에서 Qwen3-14B QLoRA, identity·사주·tool 계약, GGUF 변환과 release gate를 적용한다.
4. 정확한 사주·수학·시스템 작업은 모델 암기가 아니라 검증된 계산기/dispatcher를 연결하고, 모델은 의도 인식·인자 작성·결과 설명을 맡긴다.

결론적으로 MiniMind는 **모델을 만드는 교재**, llm_math_book은 **LLM 실험을 배우는 교재**, LLMEX는 **강한 기반 모델을 실제 기능으로 검증·배포하는 스택**이다. 세 저장소를 경쟁 대상으로 보기보다 학습(books) → 구조 실습(MiniMind) → 제품화(LLMEX)의 순서로 결합하는 것이 가장 효과적이다.

## LLM을 직접 만드는 모듈 차이

### 1. 수학·기초 딥러닝 모듈

`llm_math_book`은 벡터·행렬·미적분/최적화·확률·정보이론·퍼셉트론/MLP·역전파를 Ch01~Ch10 노트북으로 순서대로 다룬다. 이는 모델 코드를 쓰기 전에 경사하강법과 손실의 의미를 직접 확인하게 하는 모듈이다. [노트북 목록](https://github.com/dirmich/llm_math_book/tree/main/ko/notebooks)

MiniMind에는 이런 수학 입문 모듈이 별도 교재로 분리되어 있지 않고, 곧바로 모델·학습 코드로 들어간다. LLMEX도 production 코드와 테스트는 제공하지만 수학 개념을 처음부터 전개하는 모듈은 아니다.

**장점:** llm_math_book은 원리 이해에 가장 강하다. **단점:** 노트북만으로는 완성된 LLM이 만들어지지 않는다.

### 2. 토크나이저·임베딩 모듈

llm_math_book은 Ch12 토크나이저와 Ch13 임베딩에서 분할·벡터 표현을 실험한다. MiniMind는 `model/model_minimind.py`와 tokenizer 파일을 함께 제공하며, 작은 모델에 맞춘 6,400 vocabulary를 사용한다. [MiniMind model 디렉터리](https://github.com/jingyaogong/minimind/tree/master/model)

LLMEX는 Qwen3-14B의 기존 tokenizer를 유지한다. 이는 Qwen3 가중치와 GGUF/llama.cpp 생태계 호환성이 좋지만, tokenizer를 바꾸며 원리를 실험하는 교육성은 낮다.

### 3. Transformer·GPT 본체 모듈

llm_math_book은 Ch14 attention, Ch15 multi-head attention, Ch16 positional encoding, Ch17 Transformer, Ch18 GPT anatomy, Ch31 NanoGPT 순으로 본체를 조립한다. MiniMind는 이 조립 결과를 `model_minimind.py`의 Dense/MoE 모델로 구현하고 Qwen3 계열 구조와 호환을 목표로 한다. [MiniMind model 코드](https://github.com/jingyaogong/minimind/tree/master/model)

LLMEX는 Transformer 본체를 새로 만들지 않고 Qwen3-14B를 기반 모델로 로드한다. 따라서 품질 출발점은 높지만, attention·RoPE·MLP를 직접 설계하는 모듈은 범위 밖이다.

### 4. Pretrain·SFT 모듈

MiniMind는 `trainer`에 pretrain과 full SFT 스크립트를 두고, 사용자가 작은 모델을 처음부터 학습한다. [MiniMind trainer 디렉터리](https://github.com/jingyaogong/minimind/tree/master/trainer)

llm_math_book은 Ch19 pretraining과 Ch20 SFT를 노트북 실험으로 설명한다. LLMEX는 이미 사전학습된 Qwen3-14B에 assistant-only SFT/QLoRA를 적용한다. 즉 MiniMind/llm_math_book은 “가중치를 처음 만드는” 모듈이 강하고, LLMEX는 “기존 가중치를 안전하게 개조하는” 모듈이 강하다.

### 5. 정렬·추론·최적화 모듈

llm_math_book은 Ch21 RLHF, Ch22 DPO, Ch23 KV cache, Ch24 decoding, Ch25 quantization, Ch26 LoRA/pruning, Ch27 FlashAttention, Ch28~30 병렬화/ZeRO를 독립 실험으로 나눈다. MiniMind는 이 개념들을 실제 학습 스크립트와 RL/Agentic RL 흐름에 연결한다. [MiniMind README의 전체 학습 범위](https://github.com/jingyaogong/minimind#readme)

LLMEX는 QLoRA·GGUF Q4 변환·llama.cpp 실행·품질 gate에 집중한다. DPO/RLHF·분산 학습의 교육용 구현은 상대적으로 약하지만, 실제 release에 필요한 무결성·재현성 검사는 더 강하다.

### 6. 데이터·도구·서비스 모듈

MiniMind는 데이터 정제부터 Tool Use·Agentic RL, OpenAI 호환 API와 Streamlit WebUI까지 하나의 모델 프로젝트에 포함한다. llm_math_book은 작은 연습 데이터와 `src/llm_math/{data,reference,bench,viz}` 유틸리티, 노트북 실행·CPU/GPU 정답 검증에 집중한다. LLMEX는 허가된 JSONL, teacher 증류, 사주 `calculate_saju`, Linux/GPIO tool 계약, GGUF release audit를 다룬다.

**핵심 차이:** MiniMind는 tool을 학습·에이전트 훈련 대상으로 보고, LLMEX는 tool 선택과 인자 생성의 계약을 검증한다. 실제 계산·GPIO 실행은 세 프로젝트 모두 모델 가중치가 아니라 실행기/dispatcher가 담당해야 한다.

## 직접 만드는 순서에 대한 결론

1. `llm_math_book`의 수학·attention·Transformer·NanoGPT 모듈로 원리를 검증한다.
2. MiniMind의 tokenizer·model·trainer 모듈로 작은 Dense/MoE LLM을 scratch부터 pretrain/SFT한다.
3. MiniMind의 LoRA/DPO/Tool Use 모듈로 정렬과 호출 형식을 실습한다.
4. LLMEX의 데이터 provenance·QLoRA·GGUF·quality gate를 적용해 14B 제품 모델로 전환한다.

따라서 세 프로젝트의 모듈은 중복이라기보다 **수학 기초 → 모델 본체·scratch 학습 → 제품형 미세조정·검증**으로 이어지는 서로 다른 층을 담당한다.
