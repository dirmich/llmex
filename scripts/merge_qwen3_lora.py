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
    print({"output": str(args.output), "parameters": sum(p.numel() for p in merged.parameters())})


if __name__ == "__main__":
    main()
