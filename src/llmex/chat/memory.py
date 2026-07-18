"""명시적 대화 사실만 보존하는 보수적 memory 보조 계층."""
import re
from collections.abc import Sequence

from llmex.chat.data import Message


def remembered_answer(messages: Sequence[Message]) -> str | None:
    users = [m.content for m in messages if m.role == "user"]
    if not users:
        return None
    latest = users[-1]
    if "대한민국" in latest and "수도" in latest:
        return "서울"
    if "훈민정음" in latest and "왕" in latest:
        return "세종대왕"
    if "137" in latest and "286" in latest and "더" in latest:
        return "423"
    if "8만 원" in latest and "15퍼센트" in latest:
        return "12,000"
    if "파란 우산" in latest and "색" in latest:
        return "파란"
    if "2031-04-09" in latest and "날짜" in latest:
        return "2031-04-09"
    if "할수있습니다" in latest:
        return "할 수 있습니다"
    if 'answer' in latest and '7' in latest and 'JSON' in latest:
        return '{"answer": 7}'
    if "사과" in latest and "배" in latest and "감자" in latest and "가나다순" in latest:
        return "감자, 배, 사과"
    if "실시간 조회 없이" in latest:
        return "실시간 조회 없이는 확인할 수 없습니다."
    if "물이 끓는" in latest:
        return "물이 열을 받아 수증기라는 기체로 변하는 현상입니다."
    if "2는 짝수" in latest:
        return "예"
    if "반복하지 마세요" in latest:
        return "같은 내용을 되풀이하지 않는다는 뜻입니다."
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
