#!/usr/bin/env python3
"""LLMEX ByteLevel BPE를 gpt-2 pre-tokenizer로 명시해 llama.cpp converter를 실행한다."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llama-cpp-dir", type=Path, required=True)
    parser.add_argument("--hf-dir", type=Path, required=True)
    parser.add_argument("--expected-tokenizer-sha256", required=True)
    parser.add_argument("--outfile", type=Path, required=True)
    parser.add_argument("--outtype", choices=["f32", "f16", "bf16", "q8_0"], default="f16")
    args = parser.parse_args()

    tokenizer_path = args.hf_dir / "tokenizer.json"
    tokenizer_bytes = tokenizer_path.read_bytes()
    if hashlib.sha256(tokenizer_bytes).hexdigest() != args.expected_tokenizer_sha256:
        raise SystemExit("LLMEX tokenizer SHA-256이 예상값과 다릅니다")
    tokenizer = json.loads(tokenizer_bytes)
    expected_byte_level = {
        "type": "ByteLevel",
        "add_prefix_space": False,
        "trim_offsets": True,
        "use_regex": True,
    }
    if tokenizer.get("pre_tokenizer") != expected_byte_level:
        raise SystemExit("LLMEX GGUF wrapper는 고정 ByteLevel pre-tokenizer만 지원합니다")
    expected_decoder = {
        "type": "ByteLevel",
        "add_prefix_space": True,
        "trim_offsets": True,
        "use_regex": True,
    }
    model = tokenizer.get("model")
    special = tokenizer.get("added_tokens")
    expected_special = [
        (0, "<pad>"),
        (1, "<bos>"),
        (2, "<eos>"),
        (3, "<unk>"),
    ]
    if (
        tokenizer.get("normalizer") is not None
        or tokenizer.get("post_processor") is not None
        or tokenizer.get("decoder") != expected_decoder
        or not isinstance(model, dict)
        or model.get("type") != "BPE"
        or model.get("unk_token") != "<unk>"
        or model.get("dropout") is not None
        or model.get("byte_fallback") is not True
        or not isinstance(special, list)
        or [(item.get("id"), item.get("content")) for item in special] != expected_special
        or any(item.get("special") is not True for item in special)
    ):
        raise SystemExit("LLMEX tokenizer의 ByteLevel BPE 계약이 올바르지 않습니다")

    sys.path.insert(0, str(args.llama_cpp_dir))
    from conversion.base import TextModel

    original = TextModel.get_vocab_base_pre

    def llmex_vocab_pre(self, hf_tokenizer):
        try:
            return original(self, hf_tokenizer)
        except NotImplementedError:
            return "gpt-2"

    TextModel.get_vocab_base_pre = llmex_vocab_pre
    import convert_hf_to_gguf

    sys.argv = [
        "convert_hf_to_gguf.py",
        str(args.hf_dir),
        "--outfile",
        str(args.outfile),
        "--outtype",
        args.outtype,
    ]
    convert_hf_to_gguf.main()


if __name__ == "__main__":
    main()
