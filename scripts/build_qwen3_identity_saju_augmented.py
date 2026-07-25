"""Qwen3 사주 tool과 llmex identity를 반복 보강한 학습 split을 만든다."""

import json
from pathlib import Path

BASE = Path("data/chat/ko-public-teacher-v5/train.jsonl")
SAJU = Path("data/chat/ko-saju-mcp-tool-v1/train.jsonl")
IDENTITY = Path("data/chat/identity-highmaru.jsonl")
OUT = Path("data/chat/ko-public-teacher-v5-identity-saju-v2")


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    base = rows(BASE)
    saju = rows(SAJU)
    identity = rows(IDENTITY)
    # Special behavior is intentionally oversampled: it is otherwise below 0.3% of the corpus.
    train = base + saju * 100 + identity * 100
    for index, row in enumerate(train):
        row["id"] = f"identity-saju-v2-{index:06d}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "train.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in train) + "\n", encoding="utf-8"
    )
    heldout = rows(SAJU)
    (OUT / "heldout.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in heldout) + "\n", encoding="utf-8"
    )
    (OUT / "manifest.json").write_text(
        json.dumps(
            {"dataset": OUT.name, "base_rows": len(base), "saju_rows": len(saju),
             "identity_rows": len(identity), "saju_repeat": 100, "identity_repeat": 100,
             "train_rows": len(train), "heldout_rows": len(heldout)},
            ensure_ascii=False, indent=2,
        ) + "\n", encoding="utf-8"
    )
    print(json.dumps({"train_rows": len(train), "heldout_rows": len(heldout)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
