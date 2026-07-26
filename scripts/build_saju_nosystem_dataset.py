"""system turn 없이 사주 calculate_saju JSON을 출력하는 보정 데이터 생성기."""

import json
from pathlib import Path

from llmex.chat.data import ChatRow
from llmex.fingerprint import fingerprint

SRC = Path("data/chat/ko-saju-mcp-tool-v1/train.jsonl")
OUT = Path("data/chat/ko-saju-tool-nosystem-v1/train.jsonl")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, line in enumerate(SRC.read_text(encoding="utf-8").splitlines()):
        original = ChatRow.model_validate(json.loads(line))
        messages = [message.model_dump() for message in original.messages if message.role != "system"]
        provenance = original.provenance.model_dump(exclude_none=True)
        provenance["dataset"] = "llmex-saju-tool-nosystem-v1"
        provenance["source_id"] = f"saju-nosystem-{index:03d}"
        provenance["source_metadata"] = {"category": "saju-tool-nosystem", "generator_schema": 1}
        row = {
            "schema_version": 1,
            "id": f"saju-nosystem-{index:03d}",
            "split": "train",
            "messages": messages,
            "provenance": provenance,
        }
        row["sha256"] = fingerprint({"id": row["id"], "messages": messages, "provenance": provenance, "split": "train"})
        rows.append(row)
    explicit = [
        ("사주를 계산해줘. 1990년 1월 1일 오전 9시, 양력, 남자입니다.", {"calendar": "solar", "day": 1, "gender": "남", "hour": 9, "month": 1, "year": 1990}),
        ("1990년 1월 1일 오전 9시 양력 남자 사주를 봐줘.", {"calendar": "solar", "day": 1, "gender": "남", "hour": 9, "month": 1, "year": 1990}),
        ("2001년 11월 3일 오후 2시 20분 양력 남자입니다. 사주 계산해줘.", {"calendar": "solar", "day": 3, "gender": "남", "hour": 14, "minute": 20, "month": 11, "year": 2001}),
        ("음력 1988년 5월 5일 윤달 아님, 사주를 계산해줘.", {"calendar": "lunar", "day": 5, "leap": False, "month": 5, "year": 1988}),
    ]
    for offset, (prompt, arguments) in enumerate(explicit, start=len(rows)):
        provenance = {
            "dataset": "llmex-saju-tool-nosystem-v1",
            "source": "repository-authored-deterministic-curriculum",
            "license": "LicenseRef-LLMEX-Internal-Curriculum",
            "collected_at": "2026-07-27",
            "source_id": f"saju-nosystem-explicit-{offset:03d}",
            "source_metadata": {"category": "saju-tool-nosystem-explicit", "generator_schema": 1},
        }
        messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": json.dumps({"arguments": arguments, "tool": "calculate_saju"}, ensure_ascii=False, sort_keys=True)}]
        row = {"schema_version": 1, "id": f"saju-nosystem-explicit-{offset:03d}", "split": "train", "messages": messages, "provenance": provenance}
        row["sha256"] = fingerprint({"id": row["id"], "messages": messages, "provenance": provenance, "split": "train"})
        rows.append(row)
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print({"path": str(OUT), "rows": len(rows)})


if __name__ == "__main__":
    main()
