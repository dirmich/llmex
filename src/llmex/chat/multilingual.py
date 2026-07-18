"""Qwen·Gemma teacher용 영어·일본어 대화/번역 prompt inventory."""

import hashlib
import json
import re
from pathlib import Path
from typing import Literal, cast

from llmex.chat.data import ChatRow, Message, Provenance, ResponseQualityContract
from llmex.errors import ConflictError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file

_TASKS = ("conversation-en", "conversation-ja", "ko-en", "en-ko", "ko-ja", "ja-ko")
_TEACHERS = ("qwen", "gemma")
_COLLECTED_AT = "2026-07-18"
_MultilingualProfile = Literal[
    "compact-v1", "expanded-v2", "natural-v3", "natural-v4", "natural-v5"
]

_ENTITY_MAPS: dict[str, dict[str, tuple[str, ...]]] = {
    "ko-en": {
        "민준": ("Minjun", "Min-jun"),
        "서연": ("Seoyeon", "Seo-yeon"),
        "도윤": ("Doyun", "Do-yun"),
        "하린": ("Harin", "Ha-rin"),
        "지호": ("Jiho", "Ji-ho", "Jihoo"),
        "수아": ("Sua", "Su-a", "Sooah"),
        "현우": ("Hyeonwoo", "Hyunwoo", "Hyeon-woo", "Hyun-woo"),
        "나은": ("Naeun", "Na-eun", "Nae-eun"),
    },
    "en-ko": {
        "Alex": ("알렉스", "Alex"),
        "Jamie": ("제이미", "Jamie"),
        "Morgan": ("모건", "Morgan"),
        "Taylor": ("테일러", "Taylor"),
        "Casey": ("케이시", "캐시", "Casey"),
        "Riley": ("라일리", "라이리", "Riley"),
        "Jordan": ("조던", "Jordan"),
        "Avery": ("에이버리", "에이브리", "Avery"),
    },
    "ko-ja": {
        "민준": ("ミンジュン",),
        "서연": ("ソヨン",),
        "도윤": ("ドユン",),
        "하린": ("ハリン",),
        "지호": ("ジホ",),
        "수아": ("スア",),
        "현우": ("ヒョヌ", "ヒョンウ"),
        "나은": ("ナウン",),
    },
    "ja-ko": {
        "葵": ("아오이",),
        "蓮": ("렌",),
        "陽菜": ("히나",),
        "湊": ("미나토",),
        "結衣": ("유이",),
        "悠真": ("유마",),
        "凛": ("린",),
        "蒼": ("아오이", "소우", "소오"),
    },
}

_NUMBER_WORDS = {
    "en": {
        2: ("two",),
        3: ("three",),
        4: ("four",),
        5: ("five",),
        6: ("six",),
        7: ("seven",),
        8: ("eight",),
        9: ("nine",),
        10: ("ten",),
        11: ("eleven",),
        12: ("twelve", "noon"),
    },
    "ko": {
        2: ("두", "둘"),
        3: ("세", "셋"),
        4: ("네", "넷"),
        5: ("다섯",),
        6: ("여섯",),
        7: ("일곱",),
        8: ("여덟",),
        9: ("아홉",),
        10: ("열",),
        11: ("열한",),
        12: ("열두", "정오"),
    },
    "ja": {
        2: ("二",),
        3: ("三",),
        4: ("四",),
        5: ("五",),
        6: ("六",),
        7: ("七",),
        8: ("八",),
        9: ("九",),
        10: ("十",),
        11: ("十一",),
        12: ("十二", "正午"),
    },
}


def _number_group(target: str, value: str) -> list[str]:
    return [value, *_NUMBER_WORDS[target].get(int(value), ())]


_TERM_MAPS: dict[str, dict[str, tuple[str, ...]]] = {
    "ko-en": {
        "노트": ("notebook", "notebooks"),
        "우산": ("umbrella", "umbrellas"),
        "책": ("book", "books"),
        "사진": ("photo", "photos"),
        "열쇠": ("key", "keys"),
        "선물": ("gift", "gifts"),
        "보고서": ("report", "reports"),
        "표": ("ticket", "tickets"),
    },
    "en-ko": {
        "notebooks": ("노트",),
        "umbrellas": ("우산",),
        "books": ("책",),
        "photos": ("사진",),
        "keys": ("열쇠",),
        "gifts": ("선물",),
        "reports": ("보고서", "리포트"),
        "tickets": ("표", "티켓"),
    },
    "ko-ja": {
        "노트": ("ノート",),
        "우산": ("傘",),
        "책": ("本",),
        "사진": ("写真",),
        "열쇠": ("鍵",),
        "선물": ("贈り物", "プレゼント"),
        "보고서": ("報告書",),
        "표": ("切符", "チケット"),
    },
    "ja-ko": {
        "ノート": ("노트",),
        "傘": ("우산",),
        "本": ("책",),
        "写真": ("사진",),
        "鍵": ("열쇠",),
        "贈り物": ("선물",),
        "報告書": ("보고서",),
        "切符": ("표", "티켓"),
    },
}

_CONTEXT_TERM_MAPS: dict[str, dict[str, tuple[str, ...]]] = {
    "ko-en": {
        "월요일": ("Monday",),
        "화요일": ("Tuesday",),
        "수요일": ("Wednesday",),
        "목요일": ("Thursday",),
        "도서관": ("library",),
        "공원": ("park",),
        "카페": ("cafe", "café"),
        "미술관": ("museum",),
        "시장": ("market",),
        "강변": ("riverside", "river"),
        "역": ("station",),
        "회의실": ("meeting room",),
        "받아": ("receive", "collect", "pick up"),
        "전합니다": ("give", "deliver", "pass"),
    },
    "en-ko": {
        "Monday": ("월요일",),
        "Tuesday": ("화요일",),
        "Wednesday": ("수요일",),
        "Thursday": ("목요일",),
        "library": ("도서관",),
        "park": ("공원",),
        "café": ("카페",),
        "museum": ("미술관",),
        "market": ("시장",),
        "riverside": ("강변",),
        "station": ("역",),
        "community center": ("주민센터", "커뮤니티 센터"),
        "collect": ("받", "수령", "수거"),
        "give": ("주", "건네", "전하"),
    },
    "ko-ja": {
        "월요일": ("月曜日",),
        "화요일": ("火曜日",),
        "수요일": ("水曜日",),
        "목요일": ("木曜日",),
        "도서관": ("図書館",),
        "공원": ("公園",),
        "카페": ("カフェ",),
        "미술관": ("美術館",),
        "시장": ("市場",),
        "강변": ("川辺", "川沿い"),
        "역": ("駅",),
        "회의실": ("会議室",),
        "받아": ("受け取",),
        "전합니다": ("渡", "届け"),
    },
    "ja-ko": {
        "月曜日": ("월요일",),
        "火曜日": ("화요일",),
        "水曜日": ("수요일",),
        "木曜日": ("목요일",),
        "図書館": ("도서관",),
        "公園": ("공원",),
        "カフェ": ("카페",),
        "美術館": ("미술관",),
        "市場": ("시장",),
        "川辺": ("강변", "강가"),
        "駅": ("역",),
        "公民館": ("주민센터", "커뮤니티 센터"),
        "受け取り": ("받", "수령"),
        "渡します": ("주", "건네", "전하"),
    },
}

_KO_RECEIVE_FORMS_V5 = (
    "받아",
    "받아서",
    "받고",
    "받은",
    "받을",
    "받습니다",
    "수령해",
    "수령해서",
    "수령하여",
    "수령하고",
    "수령합니다",
    "수거해",
    "수거해서",
    "수거하여",
    "수거하고",
    "수거합니다",
    "수집해",
    "수집해서",
    "수집하여",
    "수집하고",
    "수집합니다",
)
_KO_GIVE_FORMS_V5 = (
    "주고",
    "줍니다",
    "건네어",
    "건네서",
    "건네고",
    "건넬",
    "건넵니다",
    "건넸",
    "전해",
    "전해서",
    "전하여",
    "전하고",
    "전할",
    "전합니다",
    "전달해",
    "전달해서",
    "전달하여",
    "전달하고",
    "전달할",
    "전달합니다",
)
_EN_GIVE_FORMS_V5 = (
    "give them to",
    "gives them to",
    "gave them to",
    "giving them to",
    "deliver them to",
    "delivers them to",
    "delivered them to",
    "delivering them to",
    "pass them to",
    "passes them to",
    "passed them to",
    "passing them to",
    "send them to",
    "sends them to",
    "sent them to",
    "sending them to",
    "forward them to",
    "forwards them to",
    "forwarded them to",
    "forwarding them to",
    "hand them to",
    "hands them to",
    "handed them to",
    "handing them to",
)
_V5_CONTEXT_TERM_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "ko-en": {
        "미술관": ("art gallery",),
        "강변": ("riverbank",),
        "회의실": ("conference room",),
        "받아": (
            "receives",
            "received",
            "receiving",
            "collects",
            "collected",
            "collecting",
            "picks up",
            "picked up",
            "picking up",
        ),
    },
    "en-ko": {
        "museum": ("박물관",),
        "riverside": ("강가",),
        "station": ("기차역",),
    },
    "ja-ko": {
        "美術館": ("박물관",),
        "駅": ("기차역",),
    },
}
_V5_CONTEXT_TERM_REPLACEMENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "ko-en": {"전합니다": _EN_GIVE_FORMS_V5},
    "en-ko": {"collect": _KO_RECEIVE_FORMS_V5, "give": _KO_GIVE_FORMS_V5},
    "ja-ko": {"受け取り": _KO_RECEIVE_FORMS_V5, "渡します": _KO_GIVE_FORMS_V5},
}

_V5_PROMPT_SUFFIXES = {
    "conversation-en": " Keep the response directly relevant.",
    "conversation-ja": "内容に直接関係する返答にしてください。",
    "ko-en": " 모든 이름·시각·수량·장소·물체와 두 동작의 의미를 보존하세요.",
    "en-ko": " Preserve every name, time, quantity, place, object, and both actions.",
    "ko-ja": " 모든 이름·시각·수량·장소·물체와 두 동작의 의미를 보존하세요.",
    "ja-ko": "人名・時刻・数量・場所・物と二つの動作の意味をすべて保ってください。",
}


def _detected_groups(
    prompt: str,
    mapping: dict[str, tuple[str, ...]],
    *,
    strict_ascii_boundaries: bool = False,
) -> list[list[str]]:
    def present(source: str) -> bool:
        if source == "本":
            return f"{source}を" in prompt
        if source == "역":
            return (
                re.search(
                    r"(?<![가-힣])역(?=(?:에서|에|으로|은|는|이|가|을|를|과|와|도|의)?(?:[^가-힣]|$))",
                    prompt,
                )
                is not None
            )
        if strict_ascii_boundaries and source.isascii() and source[:1].isalnum():
            return (
                re.search(rf"(?<![A-Za-z0-9]){re.escape(source)}(?![A-Za-z0-9])", prompt)
                is not None
            )
        return source in prompt

    return [list(targets) for source, targets in mapping.items() if present(source)]


def response_quality_contract(
    task: str,
    prompt: str,
    *,
    conversation_act: Literal["question", "suggestion"] | None = None,
    translation_contract: Literal["base", "natural-v5"] = "base",
) -> ResponseQualityContract:
    target = cast(
        Literal["ko", "en", "ja"],
        {
            "conversation-en": "en",
            "conversation-ja": "ja",
            "ko-en": "en",
            "en-ko": "ko",
            "ko-ja": "ja",
            "ja-ko": "ko",
        }[task],
    )
    if task.startswith("conversation-"):
        mode = "conversation" if conversation_act is None else f"conversation-{conversation_act}"
        return ResponseQualityContract(
            mode=cast(
                Literal["conversation", "conversation-question", "conversation-suggestion"],
                mode,
            ),
            target_language=target,
            max_sentences=2,
        )
    number_source = re.sub(r"(?<=\d):00\b", "", prompt)
    numbers = list(dict.fromkeys(re.findall(r"(?<!\d)\d+(?!\d)", number_source)))
    term_maps = _CONTEXT_TERM_MAPS[task]
    if translation_contract == "natural-v5":
        aliases = _V5_CONTEXT_TERM_ALIASES.get(task, {})
        replacements = _V5_CONTEXT_TERM_REPLACEMENTS.get(task, {})
        term_maps = {
            source: replacements.get(
                source,
                tuple(dict.fromkeys((*targets, *aliases.get(source, ())))),
            )
            for source, targets in term_maps.items()
        }
    strict_detection = translation_contract == "natural-v5"
    return ResponseQualityContract(
        mode="translation-only",
        target_language=target,
        max_sentences=2,
        required_numbers=[_number_group(target, number) for number in numbers],
        required_entities=_detected_groups(
            prompt, _ENTITY_MAPS[task], strict_ascii_boundaries=strict_detection
        ),
        required_terms=[
            *_detected_groups(prompt, _TERM_MAPS[task], strict_ascii_boundaries=strict_detection),
            *_detected_groups(prompt, term_maps, strict_ascii_boundaries=strict_detection),
        ],
    )


def _topic_particle(value: str) -> str:
    """마지막 한글 음절의 받침에 맞는 주제 조사를 붙인다."""
    last = value[-1]
    has_batchim = "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 != 0
    return f"{value}{'은' if has_batchim else '는'}"


def _object_particle(value: str) -> str:
    """마지막 한글 음절의 받침에 맞는 목적격 조사를 붙인다."""
    last = value[-1]
    has_batchim = "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 != 0
    return f"{value}{'을' if has_batchim else '를'}"


def _natural_prompt(
    teacher: Literal["qwen", "gemma"],
    task: str,
    index: int,
    *,
    contracted_conversation: bool = False,
) -> str:
    """일련번호 없이 의미 조합으로 고유한 자연대화 v3 prompt를 만든다."""
    names_ko = ("민준", "서연", "도윤", "하린", "지호", "수아", "현우", "나은")
    names_en = ("Alex", "Jamie", "Morgan", "Taylor", "Casey", "Riley", "Jordan", "Avery")
    names_ja = ("葵", "蓮", "陽菜", "湊", "結衣", "悠真", "凛", "蒼")
    topics_en = (
        "finished a difficult task and finally feel relieved",
        "want a calm weekend but have not chosen what to do",
        "cooked a new dish and it turned out better than expected",
        "feel nervous about meeting a new team tomorrow",
        "took a short walk and cleared my head this evening",
        "found an old photo that brought back a happy memory",
        "keep postponing a book I genuinely want to read",
        "cannot decide whether to go out or rest at home",
    )
    topics_ja = (
        "難しい用事が終わって、やっとほっとしています",
        "静かな週末を過ごしたいのですが、まだ予定を決めていません",
        "初めて作った料理が思ったよりおいしくできました",
        "明日、新しいチームに会うので少し緊張しています",
        "夕方に少し歩いたら気分がすっきりしました",
        "古い写真を見つけて、楽しい思い出がよみがえりました",
        "読みたい本があるのに、つい後回しにしてしまいます",
        "出かけるか家で休むか迷っています",
    )
    activities_en = (
        "reading",
        "walking",
        "cooking",
        "drawing",
        "gardening",
        "cycling",
        "music",
        "photography",
    )
    activities_ja = ("読書", "散歩", "料理", "絵", "園芸", "サイクリング", "音楽", "写真")
    objects_ko = (
        ("노트", "권"),
        ("우산", "개"),
        ("책", "권"),
        ("사진", "장"),
        ("열쇠", "개"),
        ("선물", "개"),
        ("보고서", "부"),
        ("표", "장"),
    )
    objects_en = (
        "notebooks",
        "umbrellas",
        "books",
        "photos",
        "keys",
        "gifts",
        "reports",
        "tickets",
    )
    objects_ja = (
        ("ノート", "冊"),
        ("傘", "本"),
        ("本", "冊"),
        ("写真", "枚"),
        ("鍵", "本"),
        ("贈り物", "個"),
        ("報告書", "部"),
        ("切符", "枚"),
    )
    places_ko = ("도서관", "공원", "카페", "미술관", "시장", "강변", "역", "회의실")
    places_en = (
        "library",
        "park",
        "café",
        "museum",
        "market",
        "riverside",
        "station",
        "community center",
    )
    places_ja = ("図書館", "公園", "カフェ", "美術館", "市場", "川辺", "駅", "公民館")
    prompt_index = index + (1024 if teacher == "gemma" else 0)
    combination_index = (prompt_index * 641) % 2048
    a = combination_index % 8
    b = (combination_index // 8) % 8
    d = (combination_index // 64) % 4
    c = (combination_index // 256) % 8
    if task == "conversation-en":
        if contracted_conversation:
            instructions = (
                "Reply warmly in English and end with exactly one brief question",
                "Reply warmly in English with one practical, safe suggestion and no question",
                "Respond supportively in English and end with exactly one brief question",
                "Respond supportively in English with one practical, safe suggestion "
                "and no question",
            )
            return (
                f"{instructions[d]}. I am {names_en[a]} and spend time near the {places_en[c]}. "
                f"I {topics_en[b]}, and I usually enjoy {activities_en[a]}."
            )
        leads = (
            (
                "Reply warmly and ask one brief question",
                "Continue naturally in one or two sentences",
                "Respond like a supportive friend",
                "React naturally without echoing me",
            )
            if teacher == "qwen"
            else (
                "Answer warmly and add one short question",
                "Keep the conversation going in one or two sentences",
                "Reply as a caring friend",
                "Respond fluently without repeating my words",
            )
        )
        contexts = (
            "I could use a little encouragement",
            "I would appreciate one simple suggestion",
            "I am curious how you would react",
            "I just wanted to share this with someone",
        )
        return (
            f"{leads[d]} in English. I am {names_en[a]} and spend time near the "
            f"{places_en[c]}. I {topics_en[b]}, and I usually enjoy "
            f"{activities_en[a]}. {contexts[d]}."
        )
    if task == "conversation-ja":
        if contracted_conversation:
            instructions = (
                "自然な日本語で温かく返し、最後に短い質問を一つだけ書いてください",
                "自然な日本語で温かく返し、質問をせず無理のない具体的な提案を一つ書いてください",
                "自然な日本語で共感し、最後に短い質問を一つだけ書いてください",
                "自然な日本語で共感し、質問をせず安全で具体的な提案を一つ書いてください",
            )
            return (
                f"{instructions[d]}。私は{names_ja[a]}で、{places_ja[c]}の近くに住んでいます。"
                f"{topics_ja[b]}。普段は{activities_ja[a]}が好きです。"
            )
        leads = (
            (
                "自然な日本語で共感し、短い質問を一つ添えてください",
                "一、二文の自然な日本語で会話を続けてください",
                "親しい友達のように短く返事をしてください",
                "私の言葉を繰り返さず自然に反応してください",
            )
            if teacher == "qwen"
            else (
                "日常的な日本語で共感し、短い質問を一つ加えてください",
                "自然な日本語一、二文で会話を続けてください",
                "仲のよい友人のように簡潔に返してください",
                "同じ言葉を繰り返さず自然に応じてください",
            )
        )
        contexts = (
            "少し励ましてもらえるとうれしいです",
            "簡単な提案を一つ聞きたいです",
            "あなたならどう感じるか気になります",
            "誰かにこの話を聞いてほしかったです",
        )
        return (
            f"{leads[d]}。私は{names_ja[a]}で、{places_ja[c]}の近くに住んでいます。"
            f"{topics_ja[b]}。普段は{activities_ja[a]}が好きです。{contexts[d]}。"
        )
    quantity = 2 + c
    hour = 9 + d
    if task == "ko-en":
        lead = (
            "영어 번역문만 답하세요"
            if teacher == "qwen"
            else "설명 없이 자연스러운 영어 번역만 쓰세요"
        )
        timing = ("월요일", "화요일", "수요일", "목요일")[d]
        return (
            f"{lead}: {_topic_particle(names_ko[a])} {timing} {hour}시에 {places_ko[b]}에서 "
            f"{objects_ko[c][0]} {quantity}{_object_particle(objects_ko[c][1])} 받아 "
            f"{names_ko[(a + d + 1) % 8]}에게 전합니다."
        )
    if task == "en-ko":
        lead = (
            "Give only a natural Korean translation"
            if teacher == "qwen"
            else "Return only the fluent Korean translation"
        )
        timing = ("on Monday", "on Tuesday", "on Wednesday", "on Thursday")[d]
        return (
            f"{lead}: At {hour}:00 {timing}, {names_en[a]} will collect {quantity} "
            f"{objects_en[c]} at the {places_en[b]} and give them to "
            f"{names_en[(a + d + 1) % 8]}."
        )
    if task == "ko-ja":
        lead = (
            "일본어 번역문만 답하세요"
            if teacher == "qwen"
            else "설명 없이 자연스러운 일본어 번역만 쓰세요"
        )
        timing = ("월요일", "화요일", "수요일", "목요일")[d]
        return (
            f"{lead}: {_topic_particle(names_ko[a])} {timing} {hour}시에 {places_ko[b]}에서 "
            f"{objects_ko[c][0]} {quantity}{_object_particle(objects_ko[c][1])} 받아 "
            f"{names_ko[(a + d + 1) % 8]}에게 전합니다."
        )
    if task == "ja-ko":
        lead = (
            "自然な韓国語の訳文だけ答えてください"
            if teacher == "qwen"
            else "説明なしで自然な韓国語訳だけを書いてください"
        )
        timing = ("月曜日", "火曜日", "水曜日", "木曜日")[d]
        return (
            f"{lead}。{names_ja[a]}は{timing}{hour}時に{places_ja[b]}で"
            f"{objects_ja[c][0]}を{quantity}{objects_ja[c][1]}受け取り、"
            f"{names_ja[(a + d + 1) % 8]}に渡します。"
        )
    raise ValueError(f"지원하지 않는 다국어 task입니다: {task}")


def _expanded_prompt(
    teacher: Literal["qwen", "gemma"],
    task: str,
    index: int,
    split: Literal["train", "heldout"],
) -> str:
    """자유대화와 번역 문형을 넓힌 v2 teacher prompt를 만든다."""
    serial = index + (30_000 if split == "heldout" else 20_000)
    names_ko = ("민준", "서연", "도윤", "하린", "지호", "수아", "현우", "나은")
    names_en = ("Alex", "Jamie", "Morgan", "Taylor", "Casey", "Riley", "Jordan", "Avery")
    names_ja = ("葵", "蓮", "陽菜", "湊", "結衣", "悠真", "凛", "蒼")
    topics_en = (
        "I finished a difficult task and finally feel relieved",
        "I want a calm weekend but have not chosen what to do",
        "I tried cooking a new dish and it turned out better than expected",
        "I am nervous about meeting a new team tomorrow",
        "A short walk helped me clear my head this evening",
        "I found an old photo that brought back a happy memory",
        "I keep postponing a book that I genuinely want to read",
        "I am deciding whether to visit a museum or stay home",
    )
    topics_ja = (
        "難しい用事が終わって、やっとほっとしています",
        "静かな週末を過ごしたいのですが、まだ予定を決めていません",
        "初めて作った料理が思ったよりおいしくできました",
        "明日、新しいチームに会うので少し緊張しています",
        "夕方に少し歩いたら気分がすっきりしました",
        "古い写真を見つけて、楽しい思い出がよみがえりました",
        "読みたい本があるのに、つい後回しにしてしまいます",
        "美術館へ行くか家で休むか迷っています",
    )
    objects_ko = ("노트", "우산", "책", "사진", "열쇠", "선물", "보고서", "표")
    objects_en = (
        "notebooks",
        "umbrellas",
        "books",
        "photos",
        "keys",
        "gifts",
        "reports",
        "tickets",
    )
    objects_ja = ("ノート", "傘", "本", "写真", "鍵", "贈り物", "報告書", "切符")
    places_ko = ("도서관", "공원", "카페", "미술관", "시장", "강변", "역", "회의실")
    places_en = (
        "library",
        "park",
        "café",
        "museum",
        "market",
        "riverside",
        "station",
        "meeting room",
    )
    places_ja = ("図書館", "公園", "カフェ", "美術館", "市場", "川辺", "駅", "会議室")
    k = index % 8
    quantity = 2 + index % 17
    hour = 8 + index % 11
    style = index % 4
    if task == "conversation-en":
        leads = (
            (
                "Reply warmly in natural English and ask one short follow-up question",
                "Continue this conversation in one or two natural English sentences",
                "Respond like a supportive friend in concise English",
                "Give a natural English reaction without repeating my words",
            )
            if teacher == "qwen"
            else (
                "Answer warmly in everyday English and add one brief follow-up question",
                "Keep the conversation going in one or two fluent English sentences",
                "React as a caring friend using concise natural English",
                "Respond naturally in English without echoing what I said",
            )
        )
        return f"{leads[style]}. I am {names_en[k]}. {topics_en[k]}. Reference {serial}."
    if task == "conversation-ja":
        leads = (
            (
                "自然な日本語で共感し、短い質問を一つ添えてください",
                "一、二文の自然な日本語で会話を続けてください",
                "親しい友達のように短く返事をしてください",
                "私の言葉を繰り返さず、自然な日本語で反応してください",
            )
            if teacher == "qwen"
            else (
                "日常的な日本語で共感し、短い質問を一つ加えてください",
                "自然な日本語一、二文でこの会話を続けてください",
                "仲のよい友人のように簡潔に返してください",
                "同じ言葉を繰り返さず、日本語で自然に応じてください",
            )
        )
        return f"{leads[style]}。私は{names_ja[k]}です。{topics_ja[k]}。整理番号は{serial}です。"
    if task == "ko-en":
        leads = (
            ("영어 번역문만 답하세요", "자연스러운 영어 한 문장으로만 옮기세요")
            if teacher == "qwen"
            else (
                "설명 없이 영어 번역만 쓰세요",
                "다음 내용을 자연스러운 영어 한 문장으로 번역하세요",
            )
        )
        return (
            f"{leads[index % 2]}: {names_ko[k]}은 {hour}시에 {places_ko[k]}에서 "
            f"{objects_ko[k]} {quantity}개를 받고, 확인 번호 {serial}을 알려 줄 예정입니다."
        )
    if task == "en-ko":
        leads = (
            (
                "Give only a natural Korean translation",
                "Translate into one natural Korean sentence only",
            )
            if teacher == "qwen"
            else (
                "Return only the fluent Korean translation",
                "Render this as one natural Korean sentence without explanation",
            )
        )
        return (
            f"{leads[index % 2]}: {names_en[k]} will bring {quantity} {objects_en[k]} to the "
            f"{places_en[k]} at {hour}:00 and confirm reference {serial}."
        )
    if task == "ko-ja":
        leads = (
            ("일본어 번역문만 답하세요", "자연스러운 일본어 한 문장으로만 옮기세요")
            if teacher == "qwen"
            else (
                "설명 없이 일본어 번역만 쓰세요",
                "다음 내용을 자연스러운 일본어 한 문장으로 번역하세요",
            )
        )
        return (
            f"{leads[index % 2]}: {names_ko[k]}은 {hour}시에 {places_ko[k]}에서 "
            f"{objects_ko[k]} {quantity}개를 준비하고 예약 번호 {serial}을 확인합니다."
        )
    if task == "ja-ko":
        leads = (
            ("自然な韓国語の訳文だけ答えてください", "韓国語一文に訳し、説明は付けないでください")
            if teacher == "qwen"
            else (
                "説明なしで自然な韓国語訳だけを書いてください",
                "次の内容を自然な韓国語一文に訳してください",
            )
        )
        return (
            f"{leads[index % 2]}。{names_ja[k]}は{hour}時に{places_ja[k]}で"
            f"{objects_ja[k]}を{quantity}個受け取り、番号{serial}を確認します。"
        )
    raise ValueError(f"지원하지 않는 다국어 task입니다: {task}")


def _prompt(
    teacher: Literal["qwen", "gemma"],
    task: str,
    index: int,
    split: Literal["train", "heldout"],
) -> str:
    serial = index + (10_000 if split == "heldout" else 1_000)
    names_ko = ("민준", "서연", "도윤", "하린", "지호", "수아", "현우", "나은")
    names_en = ("Alex", "Jamie", "Morgan", "Taylor", "Casey", "Riley", "Jordan", "Avery")
    names_ja = ("葵", "蓮", "陽菜", "湊", "結衣", "悠真", "凛", "蒼")
    activities_en = ("reading", "walking", "cooking", "drawing", "gardening", "cycling")
    activities_ja = ("読書", "散歩", "料理", "絵を描くこと", "園芸", "サイクリング")
    places_ko = ("도서관", "공원", "카페", "미술관", "시장", "강변")
    places_en = ("library", "park", "café", "museum", "market", "riverside")
    places_ja = ("図書館", "公園", "カフェ", "美術館", "市場", "川辺")
    k = index % 8
    p = index % 6
    quantity = 2 + index % 17
    hour = 8 + index % 11
    if task == "conversation-en":
        lead = "Answer" if teacher == "qwen" else "Reply"
        return (
            f"{lead} naturally in English in one or two sentences. "
            f"I am {names_en[k]}; after finishing item {serial}, I am relaxing by "
            f"{activities_en[p]}. Continue the conversation warmly."
        )
    if task == "conversation-ja":
        lead = (
            "自然な日本語で一、二文で答えてください"
            if teacher == "qwen"
            else "自然な日本語で短く返事をしてください"
        )
        return (
            f"{lead}。私は{names_ja[k]}です。用事{serial}を終えて、"
            f"今は{activities_ja[p]}を楽しんでいます。会話を優しく続けてください。"
        )
    if task == "ko-en":
        lead = (
            "자연스러운 영어로만 번역하세요"
            if teacher == "qwen"
            else "다음 문장을 자연스러운 영어 한 문장으로 옮기세요"
        )
        return (
            f"{lead}: {names_ko[k]}은 {hour}시에 {places_ko[p]}에서 책 {quantity}권을 "
            f"받기로 했습니다. 확인 번호는 {serial}입니다."
        )
    if task == "en-ko":
        lead = (
            "Translate naturally into Korean only"
            if teacher == "qwen"
            else "Give only a natural Korean translation"
        )
        return (
            f"{lead}: {names_en[k]} will meet us at the {places_en[p]} at {hour}:00 "
            f"with {quantity} notebooks. The reference number is {serial}."
        )
    if task == "ko-ja":
        lead = (
            "자연스러운 일본어로만 번역하세요"
            if teacher == "qwen"
            else "다음 문장을 자연스러운 일본어 한 문장으로 옮기세요"
        )
        return (
            f"{lead}: {names_ko[k]}은 오후 {hour}시에 {places_ko[p]}에서 음료 {quantity}잔을 "
            f"준비합니다. 예약 번호는 {serial}입니다."
        )
    if task == "ja-ko":
        lead = (
            "自然な韓国語に翻訳し、訳文だけ答えてください"
            if teacher == "qwen"
            else "次の文を自然な韓国語一文に訳してください"
        )
        return (
            f"{lead}。{names_ja[k]}は{hour}時に{places_ja[p]}でノートを{quantity}冊受け取ります。"
            f"予約番号は{serial}です。"
        )
    raise ValueError(f"지원하지 않는 다국어 task입니다: {task}")


def _row(
    teacher: Literal["qwen", "gemma"],
    task: str,
    index: int,
    split: Literal["train", "heldout"],
    profile: _MultilingualProfile = "compact-v1",
    prompt_index: int | None = None,
) -> ChatRow:
    identifier = f"multilingual-{teacher}-{split}-{task}-{index:05d}"
    if profile in {"natural-v3", "natural-v4", "natural-v5"}:
        if prompt_index is None:
            raise IntegrityError(f"{profile} prompt index가 누락되었습니다")
        prompt = _natural_prompt(
            teacher,
            task,
            prompt_index,
            contracted_conversation=profile in {"natural-v4", "natural-v5"},
        )
        if profile == "natural-v5":
            prompt += _V5_PROMPT_SUFFIXES[task]
    elif profile == "expanded-v2":
        prompt = _expanded_prompt(teacher, task, index, split)
    else:
        prompt = _prompt(teacher, task, index, split)
    source_sha256 = fingerprint(
        {"teacher_pool": teacher, "task": task, "split": split, "prompt": prompt}
    )
    source_metadata: dict[str, str | int] = {"teacher_pool": teacher, "task": task}
    if profile != "compact-v1":
        source_metadata["profile"] = profile
    if profile in {"natural-v3", "natural-v4", "natural-v5"}:
        absolute_prompt_index = (prompt_index or 0) + (1024 if teacher == "gemma" else 0)
        source_metadata["prompt_index"] = absolute_prompt_index
        source_metadata["combination_index"] = (absolute_prompt_index * 641) % 2048
        if profile in {"natural-v4", "natural-v5"} and task.startswith("conversation-"):
            d = ((absolute_prompt_index * 641) % 2048) // 64 % 4
            source_metadata["conversation_act"] = "question" if d % 2 == 0 else "suggestion"
    provenance = Provenance(
        dataset=(
            "llmex-multilingual-teacher-prompts-v1"
            if profile == "compact-v1"
            else f"llmex-multilingual-teacher-prompts-{profile}"
        ),
        source="repository-authored-prompt-inventory",
        license="MIT",
        collected_at=_COLLECTED_AT,
        source_id=identifier,
        source_sha256=source_sha256,
        source_metadata=source_metadata,
        response_quality=(
            response_quality_contract(
                task,
                prompt,
                conversation_act=cast(
                    Literal["question", "suggestion"] | None,
                    source_metadata.get("conversation_act"),
                ),
                translation_contract="natural-v5" if profile == "natural-v5" else "base",
            )
            if profile in {"natural-v3", "natural-v4", "natural-v5"}
            else None
        ),
    )
    messages = [
        Message(role="user", content=prompt),
        Message(role="assistant", content="teacher 응답 수집용 prompt이며 학습 label이 아닙니다."),
    ]
    basis = {
        "id": identifier,
        "messages": [message.model_dump() for message in messages],
        "provenance": provenance.model_dump(exclude_none=True),
        "split": split,
    }
    return ChatRow(
        schema_version=1,
        id=identifier,
        split=split,
        messages=messages,
        provenance=provenance,
        sha256=fingerprint(basis),
    )


def _payload(
    teacher: Literal["qwen", "gemma"],
    train_rows: int,
    heldout_rows: int,
    profile: _MultilingualProfile,
) -> bytes:
    split_counts: tuple[tuple[Literal["train", "heldout"], int], ...] = (
        ("train", train_rows),
        ("heldout", heldout_rows),
    )
    rows = [
        _row(
            teacher,
            task,
            index,
            split,
            profile,
            index + train_rows
            if profile in {"natural-v3", "natural-v4", "natural-v5"} and split == "heldout"
            else index,
        )
        for split, count in split_counts
        for task in _TASKS
        for index in range(count)
    ]
    return "".join(
        json.dumps(
            row.model_dump(exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    ).encode("utf-8")


def prepare_multilingual_prompts(
    output_dir: Path,
    *,
    train_rows_per_task: int = 150,
    heldout_rows_per_task: int = 30,
    profile: _MultilingualProfile = "compact-v1",
) -> dict[str, object]:
    """두 teacher에 겹치지 않는 결정적 prompt inventory를 게시한다."""
    if train_rows_per_task < 1 or heldout_rows_per_task < 1:
        raise IntegrityError("다국어 task별 train/heldout 행 수는 1 이상이어야 합니다")
    if profile in {"natural-v3", "natural-v4", "natural-v5"} and (
        train_rows_per_task + heldout_rows_per_task > 1024
    ):
        raise IntegrityError(f"{profile}는 teacher별 task당 최대 1,024개 prompt를 지원합니다")
    payloads = {
        teacher: _payload(teacher, train_rows_per_task, heldout_rows_per_task, profile)
        for teacher in _TEACHERS
    }
    paths = {teacher: output_dir / f"{teacher}.jsonl" for teacher in _TEACHERS}
    manifest_path = output_dir / "manifest.json"
    expected = [*paths.values(), manifest_path]
    if any(path.exists() for path in expected):
        if not all(path.is_file() for path in expected):
            raise ConflictError("부분 다국어 prompt inventory가 발견되었습니다")
        if any(path.read_bytes() != payloads[teacher] for teacher, path in paths.items()):
            raise ConflictError("기존 다국어 prompt inventory가 현재 설정과 다릅니다")
        return json.loads(manifest_path.read_text(encoding="utf-8")) | {"reused": True}

    output_dir.mkdir(parents=True, exist_ok=True)
    for teacher, path in paths.items():
        path.write_bytes(payloads[teacher])
    manifest: dict[str, object] = {
        "schema_version": 1,
        "kind": "multilingual-teacher-prompt-inventory",
        "tasks": list(_TASKS),
        "rows_per_teacher": (train_rows_per_task + heldout_rows_per_task) * len(_TASKS),
        "split_rows_per_teacher": {
            "train": train_rows_per_task * len(_TASKS),
            "heldout": heldout_rows_per_task * len(_TASKS),
        },
        "outputs": {
            teacher: {"path": str(path), "sha256": hashlib.sha256(payloads[teacher]).hexdigest()}
            for teacher, path in paths.items()
        },
        "prompt_overlap": 0,
        "license": "MIT",
    }
    if profile != "compact-v1":
        manifest["profile"] = profile
    manifest["fingerprint"] = fingerprint(manifest)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    if sha256_file(paths["qwen"]) == sha256_file(paths["gemma"]):
        raise IntegrityError("두 teacher prompt inventory가 분리되지 않았습니다")
    return manifest | {"reused": False}
