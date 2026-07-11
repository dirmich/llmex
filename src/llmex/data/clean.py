"""결정적 MediaWiki markup 정책, Unicode 정제와 품질 측정."""

import hashlib
import html
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from llmex.config import CleaningConfig
from llmex.data.schema import Document, Quality

LICENSE = "CC BY-SA 4.0 / GFDL; 문서별 고지와 Wikimedia 이용 약관 확인 필요"
MARKUP = re.compile(r"(\{\{|\}\}|\[\[|\]\]|<[^>]+>|={2,}|'{2,})")


@dataclass(frozen=True)
class CleanResult:
    document: Document | None
    reason: str | None


def parse_markup(source: str) -> tuple[str, dict[str, int]]:
    """stdlib 기반 보수적 parser: 구조물 정책을 먼저 적용하고 링크 표시문을 보존한다."""

    stats: Counter[str] = Counter()

    def drop(pattern: str, name: str, text: str, flags: int = 0) -> str:
        matches = re.findall(pattern, text, flags)
        stats[name] += len(matches)
        return re.sub(pattern, " ", text, flags=flags)

    text = source
    text = drop(r"\{\|.*?\|\}", "tables_dropped", text, re.DOTALL)
    text = drop(
        r"<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*/\s*>",
        "references_dropped",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    text = drop(r"<!--.*?-->", "comments_dropped", text, re.DOTALL)
    math = re.findall(r"<math\b[^>]*>(.*?)</math\s*>", text, re.DOTALL | re.IGNORECASE)
    stats["math_as_text"] += len(math)
    text = re.sub(
        r"<math\b[^>]*>(.*?)</math\s*>",
        lambda match: f" {match.group(1)} ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    templates = re.findall(r"\{\{[^{}]*\}\}", text)
    stats["templates_dropped"] += len(templates)
    while re.search(r"\{\{[^{}]*\}\}", text):
        text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
    stats["links_kept"] += len(re.findall(r"\[\[", text))
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    stats["external_links_kept"] += len(re.findall(r"\[https?://", text))
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"\[https?://[^\]]+\]", " ", text)
    stats["list_items_kept"] += len(re.findall(r"(?m)^\s*[*#;:]", text))
    text = re.sub(r"(?m)^\s*[*#;:]+\s*", "", text)
    text = re.sub(r"(?m)^\s*=+\s*(.*?)\s*=+\s*$", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text), dict(sorted(stats.items()))


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        character
        for character in text
        if character in "\n\t" or unicodedata.category(character) not in {"Cc", "Cf"}
    )
    lines = [
        re.sub(r"[\t \f\v]+", " ", line).strip() for line in text.replace("\r", "\n").split("\n")
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line)).strip()


def quality(text: str, policy_stats: dict[str, int]) -> Quality:
    nonspace = [character for character in text if not character.isspace()]
    hangul = sum("가" <= character <= "힣" or "ㄱ" <= character <= "ㅣ" for character in nonspace)
    counts = Counter(nonspace)
    repetition = max(counts.values(), default=0) / max(len(nonspace), 1)
    markup_chars = sum(len(match.group(0)) for match in MARKUP.finditer(text))
    return Quality(
        chars=len(text),
        bytes=len(text.encode("utf-8")),
        hangul_ratio=hangul / max(len(nonspace), 1),
        repetition_ratio=repetition,
        markup_ratio=markup_chars / max(len(text), 1),
        policy_stats=policy_stats,
    )


def clean_page(
    raw: dict[str, object], *, dump_url: str, dump_date: str, config: CleaningConfig
) -> CleanResult:
    parsed, stats = parse_markup(str(raw["text"]))
    text = normalize_text(parsed)
    measured = quality(text, stats)
    if measured.chars < config.min_chars:
        return CleanResult(None, "min_chars")
    if measured.hangul_ratio < config.min_hangul_ratio:
        return CleanResult(None, "hangul_ratio")
    if measured.repetition_ratio > config.max_repetition_ratio:
        return CleanResult(None, "repetition")
    if measured.markup_ratio > config.max_markup_ratio:
        return CleanResult(None, "markup")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    page_id = int(str(raw["page_id"]))
    document = Document(
        page_id=page_id,
        revision_id=int(str(raw["revision_id"])),
        title=str(raw["title"]),
        text=text,
        source_url=f"https://ko.wikipedia.org/?curid={page_id}",
        dump_url=dump_url,
        dump_date=dump_date,
        license=LICENSE,
        sha256=digest,
        quality=measured,
    )
    return CleanResult(document, None)
