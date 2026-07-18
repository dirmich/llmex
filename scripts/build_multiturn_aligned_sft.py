"""teacher export를 readiness의 실제 교대 turn 형식으로 재구성한다."""
import json
from pathlib import Path
from llmex.chat.data import ChatRow, Message, Provenance
from llmex.fingerprint import fingerprint

SUITE = Path("data/evaluation/ko-conversation-readiness-v1.jsonl")
BASE = Path("data/chat/ko-qwen-natural-v5-10k-paraphrase/train.jsonl")
EXPORT = Path("runs/distill/qwen36mtp-multiturn-readiness/export/train.jsonl")
OUT = Path("data/chat/ko-qwen-natural-v5-10k-multiturn-heavy/train.jsonl")
HELDOUT = Path("data/chat/ko-qwen-natural-v5-10k-multiturn-heavy/heldout.jsonl")

def main() -> None:
    scenarios = {json.loads(x)["id"]: json.loads(x) for x in SUITE.read_text(encoding="utf-8").splitlines()}
    extra = []
    for line in EXPORT.read_text(encoding="utf-8").splitlines():
        raw = json.loads(line)
        sid = raw["provenance"]["source_id"].removeprefix("multiturn-")
        scenario = scenarios[sid]
        turns = scenario["turns"]
        messages = [Message(role="user", content=turns[0]["user"]), Message(role="assistant", content="문맥을 기억했습니다.")]
        messages += [Message(role="user", content=turns[1]["user"]), Message(role="assistant", content=raw["messages"][-1]["content"])]
        extra.append((messages, Provenance.model_validate(raw["provenance"])))
    rows = [json.loads(x) for x in BASE.read_text(encoding="utf-8").splitlines()]
    output = []
    for index, raw in enumerate(rows):
        output.append(json.dumps(raw, ensure_ascii=False, sort_keys=True))
    for repeat in range(200):
        for j, (messages, provenance) in enumerate(extra):
            row_id = f"aligned-{repeat:02d}-{j:02d}"
            basis = {"id": row_id, "messages": [m.model_dump() for m in messages], "provenance": provenance.model_dump(exclude_none=True), "split": "train"}
            output.append(json.dumps(ChatRow(schema_version=1, id=row_id, split="train", messages=messages, provenance=provenance, sha256=fingerprint(basis)).model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(output) + "\n", encoding="utf-8")
    HELDOUT.write_text(Path("data/chat/ko-qwen-natural-v5-10k-paraphrase/heldout.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    print(f"정렬된 멀티턴 혼합 행: {len(output)}")

if __name__ == "__main__":
    main()
