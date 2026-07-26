"""Qwen3 사주 tool-call 형식을 짧은 보정 학습 split으로 만든다."""

import copy
import json
from pathlib import Path

from llmex.chat.data import Message, Provenance
from llmex.fingerprint import fingerprint

SAJU = Path("data/chat/ko-saju-mcp-tool-v1/train.jsonl")
IDENTITY = Path("data/chat/identity-highmaru.jsonl")
OUT = Path("data/chat/ko-saju-tool-focus-v1")


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    saju, identity = read(SAJU), read(IDENTITY)
    train = [copy.deepcopy(row) for row in saju * 300 + identity * 50]
    for index, row in enumerate(train):
        row["id"] = f"saju-tool-focus-{index:05d}"
        row["messages"] = [Message.model_validate(item).model_dump() for item in row["messages"]]
        row["provenance"] = Provenance.model_validate(row["provenance"]).model_dump(exclude_none=True)
        row["sha256"] = fingerprint({"id": row["id"], "messages": row["messages"], "provenance": row["provenance"], "split": row["split"]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "train.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in train) + "\n", encoding="utf-8")
    heldout = read(Path("data/chat/ko-saju-mcp-tool-v1/heldout.jsonl"))
    (OUT / "heldout.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in heldout) + "\n", encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps({"saju_repeat": 300, "identity_repeat": 50, "train_rows": len(train), "heldout_rows": len(heldout)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"train_rows": len(train), "heldout_rows": len(heldout)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
