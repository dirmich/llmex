# MiniMind와 LLMEX 비교

이 문서는 [jingyaogong/minimind](https://github.com/jingyaogong/minimind)와 현재 LLMEX 저장소의 목표와 구현 차이를 정리한 것이다. 비교 기준은 2026-09-03에 확인한 MiniMind 저장소와 이 저장소의 코드·문서다.

## 한눈에 보는 차이

| 항목 | MiniMind | LLMEX |
|---|---|---|
| 주된 목표 | 0부터 소형 언어 모델을 만들며 LLM 내부를 학습하는 교육·재현 프로젝트 | Qwen3-14B를 기반으로 실제 대화 품질과 Highmaru identity, 사주·도구 사용을 검증하는 제품형 연구 도구 |
| 모델 규모 | 주력 MiniMind-3 Dense 약 64M, MoE 약 198M-A64M | 현재 주력 Qwen3-14B(약 14.8B), QLoRA adapter 및 Q4 GGUF 산출물 |
| 학습 방식 | 사전학습 → SFT → LoRA/RLHF/RLAIF/Agentic RL 등 전 과정을 직접 구현 | 허가된 JSONL, assistant-only SFT/QLoRA, teacher 증류와 데이터·무결성·품질 gate 중심 |
| 핵심 강점 | 짧은 시간·적은 비용으로 구조와 학습 원리를 직접 이해 가능 | 강한 원본 모델의 언어·추론 능력을 유지하면서 도메인/identity/tool 계약을 빠르게 보강 |
| 실행 생태계 | Transformers, llama.cpp, vLLM, Ollama, OpenAI API, Streamlit WebUI 지원 | llama.cpp GGUF, Qwen3 runtime/CLI, 재현 가능한 로컬 검증과 release audit 중심 |
| 도구 사용 | Tool Use, Agentic RL, 다중 tool-call 예제를 기본 학습 흐름에 포함 | 사주 `calculate_saju`, Linux/GPIO 호출 형식과 계약 테스트를 집중 검증; 실제 실행은 dispatcher 필요 |
| 다중 모달 | MiniMind-V, MiniMind-O 등 별도 확장 프로젝트 | 현재 주력 14B GGUF는 텍스트 모델이며 이미지 입력은 지원하지 않음 |
| 품질/거버넌스 | 교육용 평가와 학습 재현성이 중심 | license provenance, contamination, heldout, SHA-256, reviewer 서명/release gate까지 관리 |

## MiniMind의 장단점

MiniMind는 핵심 알고리즘을 PyTorch 원시 코드로 구현하고, 사전학습·SFT·LoRA·DPO·PPO/GRPO/CISPO·Tool Use·Agentic RL·증류까지 하나의 교육 흐름으로 제공한다. README는 Qwen3/Qwen3-MoE 구조 정렬, `<tool_call>`·`<think>` 토큰, OpenAI 호환 API, WebUI, 단일/다중 GPU 학습을 명시한다. 또한 64M 모델을 단일 3090에서 약 2시간에 SFT할 수 있다는 목표를 제시한다. [MiniMind README](https://github.com/jingyaogong/minimind#readme)

장점은 구조가 작아 실험 주기가 짧고, 모델·토크나이저·학습 루프를 직접 읽으며 교육하기 좋다는 점이다. 반면 64M~198M 규모는 Qwen3-14B보다 지식·추론·자연스러운 장문 대화에서 불리하며, 처음부터 사전학습해야 하므로 충분한 일반 코퍼스와 계산량을 별도로 확보해야 한다. MiniMind의 Tool Use 학습은 호출 패턴을 제공하지만 특정 외부 도구의 정확한 계산 결과나 실행 권한까지 자동으로 보장하지 않는다.

## LLMEX의 장단점

LLMEX는 Qwen3-14B 원본을 바꾸지 않고 QLoRA로 assistant-only loss를 학습한다. 현재 검증된 GGUF는 identity(“Highmaru가 만든 llmex”), `calculate_saju` JSON 호출, 일반 대화용 chat template를 분리한다. 데이터셋은 라이선스·출처·SHA-256·train/heldout 비누출을 검사하고, GGUF 변환 후 llama.cpp 계약 테스트를 실행한다.

장점은 14B의 사전학습 지식과 한국어 대화 능력을 그대로 활용하면서 적은 adapter 학습으로 도메인 기능을 추가하는 것이다. 또한 운영 전제(재현 명령, checkpoint, quality gate, release 서명)를 문서화하기 쉽다. 단점은 원본 Qwen3에 크게 의존하고, 처음부터 모델 구조를 이해하거나 독립적인 사전학습을 재현하는 교육 목적에는 MiniMind보다 부적합하다는 점이다. QLoRA와 GGUF는 모델이 tool JSON을 생성하게 할 뿐, llama.cpp 단독 프로세스가 MCP·Linux·GPIO·사주 계산기를 실행하지는 않는다. 별도의 dispatcher 또는 내장 실행기가 필요하다.

## 어떤 경우에 무엇을 선택할까?

- **LLM 구조·학습 원리를 배우고 작은 모델을 직접 만들기:** MiniMind가 적합하다.
- **자연스러운 대화와 기존 Qwen3 지식이 우선:** LLMEX의 14B 기반 접근이 유리하다.
- **사주처럼 정확한 외부 계산이 필요한 기능:** 두 프로젝트 모두 모델 학습만으로 계산을 맡기지 말고, 검증된 계산 tool/dispatcher를 사용해야 한다.
- **저사양 GPU에서 반복 실험:** MiniMind가 훨씬 빠르고 저렴하다.
- **운영 전 품질·라이선스·재현성 감사:** LLMEX의 gate와 manifest 체계가 더 강하다.

## 결론

두 프로젝트는 경쟁 관계라기보다 층위가 다르다. MiniMind는 “작은 LLM을 처음부터 이해하고 만드는 교육용 전체 스택”이고, LLMEX는 “강한 14B 기반 모델을 특정 제품 요구(identity·한국어 대화·사주·tool 계약)에 맞추고 검증하는 운영형 스택”이다. LLMEX에 MiniMind의 장점을 흡수하려면 향후 소형 scratch 모델을 교육용 baseline으로 추가하고, Tool Use/Agentic RL 실험을 별도 adapter로 재현하는 것이 가장 현실적이다.
