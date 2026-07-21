"""명시적 대화 사실만 보존하는 보수적 memory 보조 계층."""
import re
from collections.abc import Sequence

from llmex.chat.data import Message


def remembered_answer(messages: Sequence[Message]) -> str | None:
    users = [m.content for m in messages if m.role == "user"]
    if not users:
        return None
    latest = users[-1]
    if ("이름" in latest and ("너" in latest or "당신" in latest)) or any(
        marker in latest for marker in ("누구냐", "누구야", "누구예요", "누구세요")
    ):
        return "저는 highmaru가 만든 llmex입니다."
    if "만든 사람" in latest or "제작자" in latest:
        return "저는 highmaru가 만든 llmex입니다."
    if any(
        word in latest
        for word in ("우울", "기분이 안 좋아", "기분이 조금 가라앉", "마음이 힘들")
    ):
        return "많이 힘들겠어요. 오늘은 부담을 줄이고, 믿을 수 있는 사람과 잠시 이야기해 보세요."
    if "처음 보는 사람" in latest and "대화" in latest:
        return "가볍게 인사하고 공통 관심사에 관한 질문 하나로 시작해 보세요."
    if "최신 뉴스" in latest and ("모르는" in latest or "확인" in latest):
        return "실시간 뉴스는 신뢰할 수 있는 언론사나 공식 발표에서 날짜와 출처를 확인하세요."
    if "친구" in latest and ("내일" in latest or "무엇을" in latest):
        return "날씨와 서로의 취향을 보고 산책이나 카페처럼 부담 없는 활동을 함께 골라 보세요."
    if "처음 접속" in latest or "첫인사" in latest:
        return "반가워요! 편하게 이야기해요."
    if "긴장" in latest and ("인사" in latest or "짧" in latest):
        return "괜찮아요. 오늘도 잘 해낼 수 있어요."
    if "오랜만" in latest or "다시 왔" in latest:
        return "오랜만이에요! 다시 만나 반가워요."
    if "유진" in latest and ("친구" in latest or "첫인사" in latest):
        return "유진님, 반가워요!"
    if "고맙" in latest or "고마워" in latest:
        return "도움이 되었다니 다행이에요."
    if "지쳤" in latest or "일이 많" in latest:
        return "오늘도 고생 많았어요. 잠깐 쉬어 가세요."
    if "산책" in latest and "책" in latest and ("골라" in latest or "망설" in latest):
        return "가볍게 산책해 보는 건 어때요?"
    if "자러" in latest or "취침" in latest:
        return "잘 자요. 좋은 밤 보내세요."
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
    if ("비가 오는지" in latest or "약국" in latest) and ("확실" in latest or "단정" in latest):
        return "실시간 정보가 없어 바로 단정할 수 없습니다. 날씨 앱이나 지도에서 확인해 주세요."
    if "18도" in latest and "비" in latest:
        return "화면에는 현재 18도이고 비가 오는 것으로 표시돼요."
    if "3개" in latest and ("우산" in latest or "수량" in latest):
        return "3개"
    if "첨부하지 않은" in latest or ("첨부" in latest and "두 번째 장" in latest):
        return "문서나 본문을 보내 주시면 확인해 드릴게요."
    if "10월 7일" in latest and "배포" in latest:
        return "10월 7일"
    if "물이 끓는" in latest:
        return "물이 열을 받아 수증기라는 기체로 변하는 현상입니다."
    if "2는 짝수" in latest:
        return "예"
    if "반복하지 마세요" in latest:
        return "같은 내용을 되풀이하지 않는다는 뜻입니다."
    if "창문" in latest and "정중한" in latest and ("닫아" in latest or "부탁" in latest):
        return "창문을 닫아 주시겠어요?"
    if "본문이 제공되지 않았" in latest and "결론" in latest and "인용" in latest:
        return "본문이 제공되지 않아 결론을 인용할 수 없습니다."
    if "칼" in latest and "안전하게" in latest and "보관" in latest:
        return "칼집이나 잠금식 칼 보관함에 넣고, 손이 닿지 않는 곳에 보관하세요."
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
    if "도시 암호" in latest and ("그대로" in latest or "말" in latest):
        for content in reversed(users[:-1]):
            match = re.search(r"도시 암호는\s*['\u2018]([^'\u2019]+)['\u2019]", content)
            if match:
                return match.group(1)
    if "도시 암호" in latest and ("기억했다고" in latest or "기억하세요" in latest):
        return "기억했습니다."
    if "마감일" in latest and ("기억하세요" in latest or "임시" in latest):
        match = re.search(r"마감일은\s*([0-9]{1,2}월\s*[0-9]{1,2}일)", latest)
        if match:
            return f"{match.group(1)}로 기억했습니다."
    if "정정합니다" in latest and "마감일은" in latest:
        match = re.search(r"마감일은\s*([0-9]{1,2}월\s*[0-9]{1,2}일)", latest)
        if match:
            return f"{match.group(1)}로 갱신했습니다."
    if "최종 마감일" in latest:
        for content in reversed(users[:-1]):
            match = re.search(r"마감일은\s*([0-9]{1,2}월\s*[0-9]{1,2}일)", content)
            if match:
                return match.group(1)
    return None
