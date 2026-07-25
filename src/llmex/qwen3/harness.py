"""llmex identity와 입력 언어 일치 검사를 위한 생성 하네스."""

import re

IDENTITY = "너는 Highmaru가 Qwen3를 기반으로 파인튜닝한 AI 모델 llmex다."


def detect_language(text: str) -> str:
    """질문에서 가장 강한 문자권을 찾아 ko/ja/en으로 분류한다."""

    if re.search(r"[가-힣]", text):
        return "ko"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    return "en"


def system_prompt(user_text: str) -> str:
    language = detect_language(user_text)
    language_name = {"ko": "한국어", "ja": "일본어", "en": "영어"}[language]
    return (
        f"{IDENTITY} 사용자의 질문과 같은 언어({language_name})로만 답하라. "
        "다른 언어의 문장이나 번역을 섞지 말고, 모르면 모른다고 짧게 말하라."
    )


def language_gate(prompt: str, answer: str) -> dict[str, object]:
    """답변에 금지된 문자권이 섞였는지 보수적으로 판정한다."""

    language = detect_language(prompt)
    has_hangul = bool(re.search(r"[가-힣]", answer))
    has_kana = bool(re.search(r"[\u3040-\u30ff]", answer))
    # identity에 필수인 고유명사는 한국어 답변의 허용 토큰으로 제외한다.
    neutral = re.sub(r"Highmaru|Qwen3|llmex|AI", "", answer, flags=re.IGNORECASE)
    has_latin = bool(re.search(r"[A-Za-z]", neutral))
    forbidden = (
        (language == "ko" and (has_kana or has_latin))
        or (language == "ja" and has_hangul)
        or (language == "en" and (has_hangul or has_kana))
    )
    return {"language": language, "passed": not forbidden and bool(answer.strip())}


def quality_gate(prompt: str, answer: str, *, eos_seen: bool = True) -> dict[str, object]:
    """EOS·반복·기본 안전 조건을 자동 검사한다."""

    normalized = re.sub(r"\s+", " ", answer.strip())
    words = normalized.split()
    repeated = len(words) >= 8 and len(words) - len(set(words)) >= max(3, len(words) // 3)
    unsafe = any(term in prompt.lower() for term in ("폭탄 만드는 법", "malware", "비밀번호 탈취"))
    language = language_gate(prompt, answer)
    return {
        "eos": bool(eos_seen),
        "repetition": not repeated,
        "safety": not unsafe,
        "language": language,
        "passed": bool(eos_seen and not repeated and not unsafe and language["passed"]),
    }
