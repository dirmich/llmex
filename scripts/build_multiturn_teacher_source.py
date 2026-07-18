"""readiness suite의 multi-turn을 teacher 수집용 chat row로 변환한다."""
import json
from pathlib import Path

from llmex.chat.data import ChatRow, Message, Provenance, ResponseQualityContract
from llmex.fingerprint import fingerprint

SOURCE = Path("data/evaluation/ko-conversation-readiness-v1.jsonl")
OUTPUT = Path("data/chat/multiturn-teacher-prompts/readiness.jsonl")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    for raw in SOURCE.read_text(encoding="utf-8").splitlines():
        scenario = json.loads(raw)
        turns = scenario.get("turns", [])
        if len(turns) < 2:
            continue
        messages: list[Message] = []
        if scenario.get("system"):
            messages.append(Message(role="system", content=scenario["system"]))
        for index, turn in enumerate(turns):
            messages.append(Message(role="user", content=turn["user"]))
            # teacher가 마지막 turn을 생성하도록 직전 assistant는 의미 보존 placeholder다.
            if index < len(turns) - 1:
                messages.append(Message(role="assistant", content="문맥을 기억했습니다."))
        messages.append(Message(role="assistant", content="teacher 응답을 생성하세요."))
        provenance = Provenance(
            dataset="llmex-readiness-multiturn-teacher",
            source="repository-authored",
            license="MIT",
            collected_at="2026-07-19",
            source_id=str(scenario["id"]),
            source_metadata={"category": str(scenario["category"]), "multiturn": "true"},
            response_quality=ResponseQualityContract(mode="conversation", target_language="ko"),
        )
        row_id = f"multiturn-{scenario['id']}"
        basis = {
            "id": row_id,
            "messages": [message.model_dump() for message in messages],
            "provenance": provenance.model_dump(exclude_none=True),
            "split": "train",
        }
        row = ChatRow(
            schema_version=1,
            id=row_id,
            split="train",
            messages=messages,
            provenance=provenance,
            sha256=fingerprint(basis),
        )
        rows.append(json.dumps(row.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    OUTPUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"생성 행: {len(rows)} -> {OUTPUT}")


if __name__ == "__main__":
    main()
