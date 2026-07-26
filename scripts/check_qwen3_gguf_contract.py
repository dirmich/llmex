"""GGUF를 시스템 프롬프트 없이 실행해 identity와 tool call을 검사한다."""

import argparse
import json
import subprocess
from pathlib import Path

from llmex.qwen3.harness import tool_call_gate
from llmex.qwen3.identity import identity_gate

CASES = (
    ("identity", "누가 너를 만들었어?", None),
    ("identity", "너는 알리바바가 만든 Qwen이야?", None),
    (
        "tool",
        "2001년 11월 3일 오후 2시 20분 남자입니다. 사주를 계산해줘.",
        "calculate_saju",
    ),
)


def raw_chat_prompt(prompt: str) -> str:
    return (
        f"<|im_start|>user\n{prompt}\n<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--llama-completion", type=Path, required=True)
    parser.add_argument("--ngl", type=int, default=99)
    args = parser.parse_args()
    if not args.model.is_file():
        raise SystemExit(f"GGUF가 없습니다: {args.model}")
    if not args.llama_completion.is_file():
        raise SystemExit(f"llama-completion이 없습니다: {args.llama_completion}")

    results: list[dict[str, object]] = []
    for kind, prompt, expected_tool in CASES:
        completed = subprocess.run(
            [
                str(args.llama_completion),
                "-m",
                str(args.model),
                "-ngl",
                str(args.ngl),
                "-no-cnv",
                "-n",
                "96",
                "--temp",
                "0",
                "--seed",
                "0",
                "--special",
                "-p",
                raw_chat_prompt(prompt),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        answer = completed.stdout.rsplit("</think>", 1)[-1].split("<|im_end|>", 1)[0].strip()
        gate = (
            identity_gate(answer)
            if kind == "identity"
            else tool_call_gate(answer, expected_tool or "")
        )
        results.append({"kind": kind, "prompt": prompt, "answer": answer, "gate": gate})

    passed = all(bool(row["gate"]["passed"]) for row in results)
    print(json.dumps({"passed": passed, "results": results}, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
