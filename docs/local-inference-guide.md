# 서명 없이 로컬 대화 테스트

수동 reviewer 서명은 release 승격에만 필요하다. 로컬 checkpoint 추론은 서명 없이
다음처럼 실행할 수 있다.

```bash
uv run llmex sft generate \
  --config configs/sft/qwen36mtp-v5-full.yaml \
  --checkpoint runs/sft-qwen36mtp-v5-full/checkpoints/latest.pt \
  --prompt '안녕하세요. 오늘 기분이 조금 우울한데 어떻게 하면 좋을까요?' \
  --temperature 0 --repetition-penalty 1.5 --max-new-tokens 96
```

2026-07-25 실제 실행 결과:

- 응답: `많이 힘들겠어요. 오늘은 부담을 줄이고, 믿을 수 있는 사람과 잠시 이야기해 보세요.`
- `eos_reached=true`
- checkpoint: `runs/sft-qwen36mtp-v5-full/checkpoints/latest.pt`
- release gate는 여전히 `blocked`지만 이는 로컬 실행을 막지 않는다.

다른 질문은 `--prompt`만 바꾸면 되며, 반복 비교에는 `--seed`와 decoding 옵션을
고정한다. 로컬 결과는 release 서명을 자동으로 만들지 않는다.

## GGUF Q4 로컬 실행

`latest.pt`를 HF export한 뒤 F16 GGUF와 `Q4_K_M` GGUF를 만들 수 있다.

```bash
llama-completion -m ~/work/models/llmex/llmex-100m-Q4_K_M.gguf \
  -no-cnv -p $'<bos><|user|>\n대한민국의 수도는 어디야?\n<|assistant|>\n' \
  -n 64 --temp 0 --repeat-penalty 1.5 --seed 0 --special
```

현재 Q4 파일은 생성·로드·생성 smoke까지 통과했지만, 수도 질문이 위키식 역사
문장으로 이어져 자연대화 품질 gate는 통과하지 못한다. 양자화 성공과 모델 품질
승인은 별개의 판정이다.
