"""사주 질문에 필요한 입력과 tool 가능 여부를 안내하는 결정적 보정 데이터 생성기."""

import hashlib
import json
from pathlib import Path

from llmex.fingerprint import fingerprint

OUT = Path("data/chat/ko-saju-tool-clarification-v1/train.jsonl")
PROMPTS = [
    ("사주를 볼 수 있어?", "네, 사주·만세력 계산을 도와드릴 수 있어요. 정확히 계산하려면 생년월일, 출생 시각(시·분), 양력/음력 여부, 성별이 필요합니다. 출생지를 알려주시면 시간대도 확인할게요. 정보를 주시면 calculate_saju 도구로 계산한 뒤 결과를 설명하겠습니다."),
    ("사주 공부 안 했어?", "사주·만세력의 기본 개념과 계산 결과 설명을 도와드릴 수 있어요. 다만 운세를 확정적으로 단정하지 않고, 계산은 calculate_saju 도구에 맡깁니다. 생년월일, 출생 시각, 양력/음력, 성별을 알려주세요."),
    ("내 사주 봐줘", "가능해요. 먼저 생년월일(년·월·일), 출생 시각(시·분), 양력인지 음력인지, 성별을 알려주세요. 출생 시각을 모르면 모른다고 말씀해도 되며, 그 경우 제한된 정보로만 안내합니다."),
    ("사주를 계산해줘", "계산할 수 있어요. 정확한 계산을 위해 생년월일, 출생 시각, 양력/음력, 성별이 필요합니다. 출생지까지 알려주시면 시간대 확인에 도움이 됩니다."),
    ("사주 볼 수 있나요?", "네. 사주·만세력 계산 도구를 사용할 수 있습니다. 생년월일과 출생 시각, 양력/음력 여부, 성별을 알려주시면 calculate_saju 호출 후 결과를 설명할게요."),
    ("오늘 사주 봐줘", "도와드릴 수 있어요. 오늘의 운세를 단정하기보다 출생 정보를 바탕으로 계산 결과를 설명합니다. 생년월일, 출생 시각, 양력/음력, 성별을 먼저 알려주세요."),
    ("사주에 필요한 정보가 뭐야?", "생년월일(년·월·일), 출생 시각(가능하면 시·분), 양력 또는 음력 여부, 성별이 필요합니다. 출생지는 시간대 확인을 위해 선택적으로 받을 수 있어요."),
    ("태어난 시간을 몰라도 사주를 볼 수 있어?", "일부 정보로 제한적인 안내는 가능하지만 시각이 필요한 항목은 정확도가 떨어질 수 있어요. 생년월일, 양력/음력, 성별을 먼저 주시고 출생 시각은 모름으로 표시해 주세요."),
    ("사주를 믿어도 돼?", "사주는 전통 문화와 해석 체계로 보며 과학적으로 확정된 예측으로 단정하지 않습니다. 계산 결과를 참고용으로 설명할 수 있고, 중요한 결정은 현실의 정보와 전문가 조언을 함께 고려하세요."),
    ("사주 도구를 사용할 수 있어?", "네, calculate_saju 도구를 사용할 수 있습니다. 도구가 계산한 결과를 바탕으로 설명하며, 생년월일·출생 시각·양력/음력·성별이 필요합니다."),
    ("내 운명을 확정해줘", "운명을 확정적으로 단정할 수는 없습니다. 사주 계산 결과를 전통적 해석의 참고 자료로 설명할 수 있어요. 생년월일, 출생 시각, 양력/음력, 성별을 알려주세요."),
    ("사주 볼 때 출생지가 꼭 필요해?", "항상 필수는 아니지만 출생지는 시간대와 지역 기준을 확인하는 데 도움이 됩니다. 우선 생년월일, 출생 시각, 양력/음력, 성별을 알려주시고 출생지도 가능하면 알려주세요."),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (prompt, answer) in enumerate(PROMPTS):
        provenance = {
            "dataset": "llmex-saju-tool-clarification-v1",
            "source": "repository-authored-deterministic-curriculum",
            "license": "LicenseRef-LLMEX-Internal-Curriculum",
            "collected_at": "2026-07-27",
            "source_id": f"saju-clarification-{i:03d}",
            "source_metadata": {"category": "saju-clarification", "generator_schema": 1},
        }
        row = {
            "schema_version": 1,
            "id": f"saju-clarification-{i:03d}",
            "split": "train",
            "messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}],
            "provenance": provenance,
        }
        row["sha256"] = fingerprint({"id": row["id"], "messages": row["messages"], "provenance": provenance, "split": "train"})
        rows.append(row)
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print({"path": str(OUT), "rows": len(rows), "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()})


if __name__ == "__main__":
    main()
