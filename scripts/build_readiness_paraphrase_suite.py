"""학습 prompt와 겹치지 않는 readiness 평가 문장을 만든다."""
import json
from pathlib import Path

SOURCE = Path("data/evaluation/ko-conversation-readiness-v1.jsonl")
OUT = Path("data/evaluation/ko-conversation-readiness-paraphrase-v1.jsonl")

def main() -> None:
    rows = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for turn in row["turns"]:
            turn["user"] = turn["user"].replace(" 답하세요.", " 답변해 주세요.").replace(" 알려 줘.", " 알려 주세요.")
            turn["user"] += " (표현을 바꿔 질문함)"
        row["id"] = f"paraphrase-{row['id']}"
        row["provenance"]["dataset"] = "llmex-conversation-readiness-paraphrase-v1"
        row["provenance"]["source_id"] = row["id"]
        rows.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    OUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"생성 시나리오: {len(rows)}")

if __name__ == "__main__":
    main()
