import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

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


def test_book_readme_chapter_links_exist() -> None:
    index = (ROOT / "docs" / "book" / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)#]+\.md)\)", index)

    assert "20-offline-chat-e2e.md" in links
    assert "environment-profiles.md" in links
    for link in links:
        assert (ROOT / "docs" / "book" / unquote(link)).is_file(), link


def test_offline_chat_fixture_builder_has_help() -> None:
    script = ROOT / "docs" / "book" / "examples" / "build-chat-smoke-fixtures.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "offline chat fixture" in result.stdout
