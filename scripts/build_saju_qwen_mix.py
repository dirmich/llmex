"""기존 Qwen3 대화 학습 split에 사주 MCP tool 예제를 결합한다."""

import json
from pathlib import Path

BASE = Path("data/chat/ko-public-teacher-v5")
SAJU = Path("data/chat/ko-saju-mcp-tool-v1")
OUT = Path("data/chat/ko-public-teacher-v5-saju-tool-v1")


def merge(split: str) -> None:
    rows: list[str] = []
    for source in (BASE / f"{split}.jsonl", SAJU / f"{split}.jsonl"):
        rows.extend(
            line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{split}.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    merge("train")
    merge("heldout")
    manifest = {
        "dataset": OUT.name,
        "base": BASE.name,
        "extra": SAJU.name,
        "train_rows": sum(1 for _ in (OUT / "train.jsonl").open(encoding="utf-8")),
        "heldout_rows": sum(1 for _ in (OUT / "heldout.jsonl").open(encoding="utf-8")),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
