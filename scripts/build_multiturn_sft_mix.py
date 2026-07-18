"""기존 paraphrase train과 멀티턴 teacher export를 결정적으로 혼합한다."""
import json
from pathlib import Path

from llmex.chat.data import ChatRow, Message, Provenance
from llmex.fingerprint import fingerprint

BASE = Path("data/chat/ko-qwen-natural-v5-10k-paraphrase/train.jsonl")
EXTRA = Path("runs/distill/qwen36mtp-multiturn-readiness/export/train.jsonl")
OUT = Path("data/chat/ko-qwen-natural-v5-10k-multiturn/train.jsonl")
HELDOUT = Path("data/chat/ko-qwen-natural-v5-10k-multiturn/heldout.jsonl")
BASE_HELDOUT = Path("data/chat/ko-qwen-natural-v5-10k-paraphrase/heldout.jsonl")


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> None:
    rows = read(BASE) + read(EXTRA) * 20
    output: list[str] = []
    for index, raw in enumerate(rows):
        messages = [Message.model_validate(item) for item in raw["messages"]]
        provenance = Provenance.model_validate(raw["provenance"])
        row_id = f"multiturn-mix-{index:06d}"
        split = "train"
        basis = {
            "id": row_id,
            "messages": [message.model_dump() for message in messages],
            "provenance": provenance.model_dump(exclude_none=True),
            "split": split,
        }
        row = ChatRow(
            schema_version=1,
            id=row_id,
            split=split,
            messages=messages,
            provenance=provenance,
            sha256=fingerprint(basis),
        )
        output.append(json.dumps(row.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(output) + "\n", encoding="utf-8")
    HELDOUT.write_text(BASE_HELDOUT.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"혼합 행: {len(output)} (멀티턴 가중치 20배) -> {OUT}")


if __name__ == "__main__":
    main()
