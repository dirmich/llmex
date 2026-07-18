"""우회 정규화를 포함한 휴리스틱 pre-filter이며 최종 safety gate가 아니다."""

import re
import unicodedata
from collections.abc import Sequence

from llmex.chat.data import ResponseQualityContract
from llmex.config import DistillationConfig

from .prompts import normalize_text
from .schema import LogicalRequest

SAFETY_FILTER_SCOPE = "heuristic_pre_filter_not_final_safety_gate"

_CHOSEONG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNGSEONG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONGSEONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"


def _compose_compatibility_jamo(value: str) -> str:
    """호환 자모열의 음절 경계를 추론해 완성형 한글로 조합한다."""

    result: list[str] = []
    index = 0
    while index < len(value):
        onset = value[index]
        if onset not in _CHOSEONG or index + 1 >= len(value) or value[index + 1] not in _JUNGSEONG:
            result.append(onset)
            index += 1
            continue
        vowel = value[index + 1]
        final_index = 0
        consumed = 2
        if index + 2 < len(value):
            final = value[index + 2]
            next_is_vowel = index + 3 < len(value) and value[index + 3] in _JUNGSEONG
            if final in _JONGSEONG and not next_is_vowel:
                final_index = _JONGSEONG.index(final)
                consumed = 3
        codepoint = (
            0xAC00 + _CHOSEONG.index(onset) * 21 * 28 + _JUNGSEONG.index(vowel) * 28 + final_index
        )
        result.append(chr(codepoint))
        index += consumed
    return "".join(result)


def compact_skeleton(value: str) -> str:
    """NFC/NFKC·자모 합성 후 공백과 구두점을 제거한 비교 문자열."""

    composed = _compose_compatibility_jamo(value)
    normalized = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", composed)).casefold()
    return "".join(
        char
        for char in normalized
        if not unicodedata.category(char).startswith(("P", "Z")) and not char.isspace()
    )


def repetition_ratio(text: str, width: int = 4) -> float:
    tokens = normalize_text(text).split()
    if len(tokens) < width:
        return 0.0
    grams = [tuple(tokens[index : index + width]) for index in range(len(tokens) - width + 1)]
    return 1.0 - len(set(grams)) / len(grams)


def _copy_ratio(prompt: str, response: str) -> float:
    prompt_skeleton = compact_skeleton(prompt)
    response_skeleton = compact_skeleton(response)
    if not response_skeleton:
        return 1.0
    if response_skeleton == prompt_skeleton:
        return 1.0
    if not prompt_skeleton or len(response_skeleton) < 32:
        return 0.0

    width = min(8, len(prompt_skeleton), len(response_skeleton))
    prompt_shingles = {
        prompt_skeleton[index : index + width] for index in range(len(prompt_skeleton) - width + 1)
    }
    response_shingles = {
        response_skeleton[index : index + width]
        for index in range(len(response_skeleton) - width + 1)
    }
    return len(prompt_shingles & response_shingles) / min(
        len(prompt_shingles), len(response_shingles)
    )


def filter_response(prompt: str, response: str, config: DistillationConfig) -> str | None:
    normalized = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", response)).strip()
    if not (config.min_response_chars <= len(normalized) <= config.max_response_chars):
        return "length"
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in normalized):
        return "control_character"
    if "�" in normalized:
        return "invalid_unicode"
    skeleton = compact_skeleton(response)
    for concept in config.unsafe_concepts:
        if any(re.search(pattern, skeleton) for pattern in concept.patterns):
            return f"unsafe:{concept.name}"
    if repetition_ratio(normalized) > config.max_repetition_ratio:
        return "repetition"
    if _copy_ratio(prompt, normalized) > config.max_prompt_copy_ratio:
        return "prompt_copy"
    return None


def _script_counts(value: str) -> tuple[int, int, int, int]:
    hangul = kana = han = latin = 0
    for char in value:
        codepoint = ord(char)
        if 0xAC00 <= codepoint <= 0xD7A3 or 0x1100 <= codepoint <= 0x11FF:
            hangul += 1
        elif 0x3040 <= codepoint <= 0x30FF or 0x31F0 <= codepoint <= 0x31FF:
            kana += 1
        elif 0x3400 <= codepoint <= 0x9FFF:
            han += 1
        elif "a" <= char.casefold() <= "z":
            latin += 1
    return hangul, kana, han, latin


def _language_failure(value: str, target: str) -> bool:
    hangul, kana, han, latin = _script_counts(value)
    letters = hangul + kana + han + latin
    if target == "en":
        return latin < 2 or hangul + kana + han > 0 or latin / max(letters, 1) < 0.75
    if target == "ko":
        return hangul < 2 or kana + han > 0 or hangul / max(letters, 1) < 0.45
    return kana < 1 or hangul > 0 or (kana + han) / max(letters, 1) < 0.5


_KOREAN_POSTPOSITIONS = (
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "에게",
    "께",
    "와",
    "과",
    "도",
    "의",
    "로",
    "으로",
    "에서",
    "시",
    "분",
    "초",
    "개",
    "권",
    "장",
    "부",
    "잔",
    "명",
    "時",
    "個",
    "冊",
    "本",
    "枚",
    "部",
)


def _contains_surface(value: str, surface: str) -> bool:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    target = unicodedata.normalize("NFKC", surface).casefold()
    start = 0
    while (index := normalized.find(target, start)) >= 0:
        before = normalized[index - 1] if index else ""
        after = normalized[index + len(target) :]
        if target.isascii():
            if (not before or not (before.isascii() and before.isalnum())) and (
                not after
                or not (after[0].isascii() and after[0].isalnum())
                or after.startswith(_KOREAN_POSTPOSITIONS)
            ):
                return True
        elif any("가" <= char <= "힣" for char in target):
            if (not before or not ("가" <= before <= "힣")) and (
                not after
                or not ("가" <= after[0] <= "힣")
                or after.startswith(_KOREAN_POSTPOSITIONS)
            ):
                return True
        else:
            return True
        start = index + 1
    return False


def _missing_group(value: str, groups: Sequence[Sequence[str]]) -> bool:
    return any(not any(_contains_surface(value, term) for term in group) for group in groups)


def _sentence_count(value: str) -> int:
    stripped = value.strip().strip("\"“”'\u2018\u2019「」『』")
    protected = re.sub(
        r"\b(?:a\.m\.|p\.m\.|e\.g\.|i\.e\.)",
        lambda match: match.group().replace(".", "\u2024"),
        stripped,
        flags=re.IGNORECASE,
    )
    parts = re.split(r"[.!?。\uFF01\uFF1F]+", protected)
    return sum(bool(part.strip().strip('"”\u2019」』')) for part in parts) or 1


_TRANSLATION_META = re.compile(
    r"(?:번역(?:문|은|하면)?|translation\s*:|translated|訳文|翻訳(?:は|すると)?|"
    r"다음과\s*같|以下の(?:通り|よう))",
    re.IGNORECASE,
)
_DIRECT_MESSAGE_META = re.compile(
    r"(?:라고\s*(?:보내|말해)|(?:이런|다음)\s*(?:메시지|표현)|표현입니다|"
    r"메시지는|혹은|또는\s*[\"“\u2018「]|"
    r"(?:이렇게|그대로)\s*(?:보내|말|사용|쓰)(?:보|하)?(?:면|해|세요)|"
    r"(?:문구|내용|말).{0,15}(?:그대로\s*)?(?:사용|보내|쓰)(?:하)?(?:면|해|세요))"
)
_UNCERTAINTY_BOUNDARY = re.compile(
    r"(?:확인할\s*수(?:는)?\s*없|확인(?:하기는?|이)?\s*(?:어렵|불가)|"
    r"알\s*수(?:는)?\s*없|(?:측정|파악)할\s*수(?:는)?\s*없|"
    r"접근할\s*수(?:는)?\s*없|"
    r"실시간.{0,12}(?:확인|파악).{0,8}(?:못|어렵|불가))"
)
_UNCERTAINTY_ACTION = re.compile(
    r"(?:주최|운영|공식|예약|전화|문의|웹사이트|홈페이지|공지|SNS|현장)"
)
_UNSUPPORTED_REALTIME = re.compile(
    r"(?:(?:네이버|카카오|구글|google|지도|맵|지도\s*앱|지도\s*서비스).{0,35}"
    r"실시간.{0,15}(?:혼잡도|혼잡|붐빔).{0,25}"
    r"(?:기능|활용|확인|제공|표시|보여|알\s*수|가능)|"
    r"실시간.{0,15}(?:혼잡도|혼잡|붐빔).{0,35}"
    r"(?:네이버|카카오|구글|google|지도|맵|지도\s*앱|지도\s*서비스).{0,25}"
    r"(?:기능|활용|확인|제공|표시|보여|알\s*수|가능)|"
    r"(?:네이버|카카오|구글|google|지도|맵|지도\s*앱|지도\s*서비스).{0,35}"
    r"(?:(?:제공하는|제공되는).{0,15}(?:혼잡도|혼잡|붐빔)|"
    r"(?:혼잡도|혼잡|붐빔).{0,20}(?:정보.{0,8}참고|제공|표시|확인)))",
    re.IGNORECASE,
)

_NUMBER_SURFACES: dict[str, dict[str, str]] = {
    "en": {
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "eleven": "11",
        "twelve": "12",
        "noon": "12",
    },
    "ko": {
        "두": "2",
        "둘": "2",
        "세": "3",
        "셋": "3",
        "네": "4",
        "넷": "4",
        "다섯": "5",
        "여섯": "6",
        "일곱": "7",
        "여덟": "8",
        "아홉": "9",
        "열": "10",
        "열한": "11",
        "열두": "12",
        "정오": "12",
    },
    "ja": {
        "二": "2",
        "三": "3",
        "四": "4",
        "五": "5",
        "六": "6",
        "七": "7",
        "八": "8",
        "九": "9",
        "十": "10",
        "十一": "11",
        "十二": "12",
        "正午": "12",
    },
}


def _canonical_numbers(value: str, target_language: str) -> set[str]:
    """숫자와 지원 숫자 단어를 같은 십진 표면형으로 정규화한다."""

    number_text = re.sub(r"(?<=\d):00\b", "", value)
    found = set(re.findall(r"(?<!\d)\d+(?!\d)", number_text))
    surfaces = _NUMBER_SURFACES[target_language]
    if target_language == "ja":
        pattern = "|".join(
            re.escape(surface) for surface in sorted(surfaces, key=len, reverse=True)
        )
        found.update(surfaces[match] for match in re.findall(pattern, number_text))
        return found
    for surface, canonical in surfaces.items():
        if _contains_surface(number_text, surface):
            found.add(canonical)
    return found


def _allowed_numbers(contract: ResponseQualityContract) -> set[str]:
    surface_map = _NUMBER_SURFACES[contract.target_language]
    allowed: set[str] = set()
    for group in contract.required_numbers:
        for surface in group:
            normalized = unicodedata.normalize("NFKC", surface).casefold()
            if normalized.isdigit():
                allowed.add(normalized)
            elif normalized in surface_map:
                allowed.add(surface_map[normalized])
    return allowed


def _quality_failure(response: str, contract: ResponseQualityContract) -> str | None:
    normalized = unicodedata.normalize("NFKC", response).strip()
    if _language_failure(normalized, contract.target_language):
        return f"quality:language:{contract.target_language}"
    if _sentence_count(normalized) > contract.max_sentences:
        return "quality:sentence_count"
    if contract.mode == "translation-only" and (
        normalized.startswith(('"', "“", "'", "\u2018", "「", "『"))
        or _TRANSLATION_META.search(normalized)
    ):
        return "quality:translation_meta"
    if _missing_group(normalized, contract.required_numbers):
        return "quality:number"
    if contract.required_numbers and (
        _canonical_numbers(normalized, contract.target_language) - _allowed_numbers(contract)
    ):
        return "quality:number"
    if _missing_group(normalized, contract.required_entities):
        return "quality:entity"
    if _missing_group(normalized, contract.required_terms):
        return "quality:term"
    if contract.mode == "direct-message" and _DIRECT_MESSAGE_META.search(normalized):
        return "quality:writing_direct"
    if contract.mode == "uncertainty":
        if not _UNCERTAINTY_BOUNDARY.search(normalized) or not _UNCERTAINTY_ACTION.search(
            normalized
        ):
            return "quality:uncertainty_boundary"
        if _UNSUPPORTED_REALTIME.search(normalized):
            return "quality:unsupported_realtime_claim"
    return None


def filter_logical_response(
    item: LogicalRequest, response: str, config: DistillationConfig
) -> str | None:
    """일반 pre-filter와 source 결속 task 품질 계약을 같은 순서로 적용한다."""

    generic_reason = filter_response(item.prompt, response, config)
    if generic_reason is not None:
        return generic_reason
    contract = item.source.response_quality
    if contract is None:
        return "quality:missing_contract" if config.quality_gate_version == "metadata-v1" else None
    return _quality_failure(response, contract)


def canonical_response(value: str) -> str:
    return normalize_text(unicodedata.normalize("NFKC", value)).casefold()
