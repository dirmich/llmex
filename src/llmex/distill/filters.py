"""우회 정규화를 포함한 휴리스틱 pre-filter이며 최종 safety gate가 아니다."""

import re
import unicodedata

from llmex.config import DistillationConfig

from .prompts import normalize_text

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


def canonical_response(value: str) -> str:
    return normalize_text(unicodedata.normalize("NFKC", value)).casefold()
