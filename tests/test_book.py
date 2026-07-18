import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_CARD = re.compile(r"^### `(?P<path>src/llmex/[^`]+\.py)`$", re.MULTILINE)


def test_every_python_module_has_exactly_one_learning_card() -> None:
    source_modules = {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "src" / "llmex").rglob("*.py")
    }
    cards: list[str] = []
    for path in sorted((ROOT / "docs" / "book" / "modules").glob("*.md")):
        cards.extend(MODULE_CARD.findall(path.read_text(encoding="utf-8")))

    assert len(cards) == len(set(cards)), "같은 Python 모듈 학습 카드가 중복됐다"
    assert set(cards) == source_modules


def test_module_chapter_links_exist() -> None:
    index = (ROOT / "docs" / "book" / "modules" / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)#]+\.md)\)", index)

    assert links
    for link in links:
        assert (ROOT / "docs" / "book" / "modules" / link).is_file(), link
