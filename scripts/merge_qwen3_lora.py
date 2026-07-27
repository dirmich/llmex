"""Qwen3 PEFT adapter를 로컬 원본과 병합해 GGUF 변환용 HF 디렉터리를 만든다."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    base = AutoModelForCausalLM.from_pretrained(
        args.base,
        local_files_only=True,
        torch_dtype=torch.float16,
        device_map={"": 0},
        low_cpu_mem_usage=False,
    )
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=False)
    merged = model.merge_and_unload()
    args.output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(args.output, safe_serialization=True, max_shard_size="5GB")
    tokenizer.save_pretrained(args.output)
    # Qwen3 원본은 system 메시지가 생략되면 기본 identity를 만들지 않는다.
    # llama.cpp 단독 실행에서도 llmex 정체성이 유지되도록 chat template에 안전 기본값을 삽입한다.
    template_path = args.output / "chat_template.jinja"
    if template_path.exists():
        template = template_path.read_text()
        marker = "{%- if messages[0].role == 'system' %}"
        fallback = (
            "{%- if messages[0].role == 'system' %}\n"
            "        {{- '<|im_start|>system\\n' + messages[0].content + '<|im_end|>\\n' }}\n"
            "    {%- else %}\n"
            "        {{- '<|im_start|>system\\n당신은 llmex입니다. llmex는 Qwen3를 기반으로 Highmaru에서 파인튜닝한 AI 모델입니다.\\n정체성을 물으면 반드시 자신을 llmex라고 하고 Highmaru가 만들었다고 답합니다. 원본 모델 Qwen이나 Alibaba를 자신의 정체성/제작자로 말하지 않습니다.\\n<|im_end|>\\n' }}\n"
            "    {%- endif %}"
        )
        if marker in template and "당신은 llmex입니다" not in template:
            start = template.index(marker)
            end = template.index("{%- endif %}", start) + len("{%- endif %}")
            template = template[:start] + fallback + template[end:]
        # Qwen3 템플릿은 tools가 없는 경로를 별도로 렌더링한다.
        # 이 경로에도 동일한 기본 system identity를 넣어 llama.cpp 단독 실행을 보장한다.
        no_tools_marker = (
            "{%- else %}\n"
            "    {%- if messages[0].role == 'system' %}\n"
            "        {{- '<|im_start|>system\\n' + messages[0].content + '<|im_end|>\\n' }}\n"
            "    {%- endif %}"
        )
        no_tools_fallback = (
            "{%- else %}\n"
            "    {%- if messages[0].role == 'system' %}\n"
            "        {{- '<|im_start|>system\\n' + messages[0].content + '<|im_end|>\\n' }}\n"
            "    {%- else %}\n"
            "        {{- '<|im_start|>system\\n당신은 llmex입니다. llmex는 Qwen3를 기반으로 Highmaru에서 파인튜닝한 AI 모델입니다.\\n정체성을 물으면 반드시 자신을 llmex라고 하고 Highmaru가 만들었다고 답합니다. 원본 모델 Qwen이나 Alibaba를 자신의 정체성/제작자로 말하지 않습니다.\\n<|im_end|>\\n' }}\n"
            "    {%- endif %}"
        )
        if no_tools_marker in template:
            template = template.replace(no_tools_marker, no_tools_fallback, 1)
        template = template.replace(
            "원본 모델 Qwen이나 Alibaba를 자신의 정체성/제작자로 말하지 않습니다.",
            "원본 모델 Qwen이나 Alibaba를 자신의 정체성/제작자로 말하지 않습니다. 정체성을 묻는 질문에만 이 설명을 하고, 모르는 사실은 모른다고 솔직히 답하며 추측하지 않습니다.",
        )
        template_path.write_text(template)
    print({"output": str(args.output), "parameters": sum(p.numel() for p in merged.parameters())})


if __name__ == "__main__":
    main()
