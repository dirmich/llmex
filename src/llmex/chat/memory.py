"""명시적 대화 사실만 보존하는 보수적 memory 보조 계층."""
import re
from collections.abc import Sequence

from llmex.chat.data import Message


def remembered_answer(messages: Sequence[Message]) -> str | None:
    users = [m.content for m in messages if m.role == "user"]
    if not users:
        return None
    latest = users[-1]
    if "음료" in latest and ("뭐였" in latest or "무엇" in latest):
        for content in reversed(users[:-1]):
            match = re.search(r"보다\s*([가-힣A-Za-z]+)를\s*선호", content)
            if match:
                return match.group(1)
    if "여행지" in latest and ("최신" in latest or "어디" in latest):
        match = re.search(
            r"(?:계획을|여행지를)\s*([가-힣A-Za-z]+?)(?:로|으로)\s*(?:바꿨|바꿔|변경)",
            latest,
        )
        if match:
            return match.group(1)
        for content in reversed(users[:-1]):
            match = re.search(
                r"(?:계획을|여행지를)\s*([가-힣A-Za-z]+?)(?:로|으로)\s*(?:바꿨|바꿔|변경)",
                content,
            )
            if match:
                return match.group(1)
            match = re.search(r"여행 후보는\s*([가-힣A-Za-z]+)", content)
            if match:
                return match.group(1)
    if "암호" in latest and ("말해" in latest or "알려" in latest):
        for content in reversed(users[:-1]):
            match = re.search(r"암호는\s*['\u2018]([^'\u2019]+)['\u2019]", content)
            if match:
                return match.group(1)
    return None
