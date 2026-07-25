"""saju-mcp의 공개 MCP schema를 바탕으로 tool-use SFT/heldout 데이터를 만든다."""

import json
from datetime import date
from pathlib import Path

from llmex.chat.data import ChatRow, Message, Provenance
from llmex.fingerprint import fingerprint, sha256_file

OUT = Path("data/chat/ko-saju-mcp-tool-v1")
SOURCE = Path("../0.ref/saju-mcp")

CASES = [
    (
        "사주를 보고 싶어요. 2001년 11월 3일 오후 2시 20분, 남자입니다.",
        "calculate_saju",
        {
            "year": 2001,
            "month": 11,
            "day": 3,
            "hour": 14,
            "minute": 20,
            "gender": "남",
            "calendar": "solar",
        },
    ),
    (
        "1990년 1월 1일 오전 9시 양력 사주를 계산해줘.",
        "calculate_saju",
        {"year": 1990, "month": 1, "day": 1, "hour": 9, "calendar": "solar"},
    ),
    (
        "음력 1988년 5월 5일 윤달 여부를 포함해 계산해줘.",
        "calculate_saju",
        {"year": 1988, "month": 5, "day": 5, "calendar": "lunar", "leap": False},
    ),
    ("2020년 3월 4일을 음력으로 변환해줘.", "solar_to_lunar", {"year": 2020, "month": 3, "day": 4}),
    (
        "음력 2024년 1월 1일을 양력으로 바꿔줘.",
        "lunar_to_solar",
        {"year": 2024, "month": 1, "day": 1, "isLeapMonth": False},
    ),
    ("출생시각을 모르면 사주를 계산할 수 있나요?", "none", None),
    ("사주 결과를 근거 없이 단정하지 말고 설명해줘.", "none", None),
    (
        "양력 2000년 1월 1일 여자, 0시 0분의 만세력을 계산해줘.",
        "calculate_saju",
        {
            "year": 2000,
            "month": 1,
            "day": 1,
            "hour": 0,
            "minute": 0,
            "gender": "여",
            "calendar": "solar",
        },
    ),
]


def make_row(index: int, prompt: str, tool: str, arguments: dict | None, split: str) -> str:
    if tool == "none":
        answer = (
            "사주·만세력은 출생 정보와 계산 결과가 필요합니다. 생년월일과 양력·음력 여부를 "
            "알려주시면 먼저 계산 tool을 사용하겠습니다. 해석은 전통 명리 관점의 참고용으로만 "
            "설명하겠습니다."
        )
    else:
        answer = json.dumps(
            {"tool": tool, "arguments": arguments}, ensure_ascii=False, sort_keys=True
        )
    messages = [
        Message(
            role="system",
            content=(
                "사주·만세력 계산은 반드시 ssaju MCP tool에 맡기고 계산 결과를 근거로 설명한다. "
                "운세를 확정적으로 단정하지 않는다."
            ),
        ),
        Message(role="user", content=prompt),
        Message(role="assistant", content=answer),
    ]
    provenance = Provenance(
        dataset="ko-saju-mcp-tool-v1",
        source=str(SOURCE / "README.md"),
        license="MIT",
        collected_at=date.today().isoformat(),
        source_id="saju-mcp-mcp-schema-and-readme",
        source_metadata={"tool": tool},
    )
    payload = {
        "id": f"saju-tool-{index:04d}",
        "messages": [m.model_dump() for m in messages],
        "provenance": provenance.model_dump(exclude_none=True),
        "split": split,
    }
    row = ChatRow(
        schema_version=1,
        id=payload["id"],
        split=split,
        messages=messages,
        provenance=provenance,
        sha256=fingerprint(payload),
    )
    return json.dumps(row.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    variants = ["", " 자세한 계산을 부탁해요.", " 결과를 tool로 먼저 확인해줘."]
    rows = [
        (f"{prompt}{variants[round]}", tool, arguments)
        for round in range(3)
        for prompt, tool, arguments in CASES
    ]
    for split, selected in (("train", rows[:20]), ("heldout", rows[20:])):
        path = OUT / f"{split}.jsonl"
        path.write_text(
            "\n".join(make_row(i, *case, split) for i, case in enumerate(selected)) + "\n",
            encoding="utf-8",
        )
    manifest = {
        "dataset": OUT.name,
        "source": str(SOURCE),
        "license": "MIT",
        "train": 20,
        "heldout": 4,
        "files": {name: sha256_file(OUT / name) for name in ("train.jsonl", "heldout.jsonl")},
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
