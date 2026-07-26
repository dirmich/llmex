"""시스템 프롬프트에 의존하지 않는 Qwen3 llmex identity 계약."""

import re

REQUIRED_IDENTITY_TERMS = ("llmex", "highmaru")


def identity_gate(answer: str) -> dict[str, object]:
    """응답이 llmex와 제작자를 함께 밝히는지 보수적으로 판정한다."""

    normalized = " ".join(answer.casefold().split())
    missing = [term for term in REQUIRED_IDENTITY_TERMS if term not in normalized]
    claims_base_creator = any(
        re.search(pattern, normalized)
        for pattern in (
            r"(?:qwen|알리바바|alibaba).{0,24}(?:만들|개발|제작|created|developed)",
            r"(?:만들|개발|제작|created|developed).{0,24}(?:qwen|알리바바|alibaba)",
        )
    ) and not any(
        marker in normalized
        for marker in ("기반", "base model", "underlying model", "ベース", "基盤")
    )
    return {
        "passed": not missing and not claims_base_creator,
        "missing": missing,
        "base_model_as_creator": claims_base_creator,
    }
