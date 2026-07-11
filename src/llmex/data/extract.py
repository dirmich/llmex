"""bzip2 MediaWiki XML의 메모리 제한 streaming 추출."""

import bz2
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import TypedDict

from llmex.errors import IntegrityError


class RawPage(TypedDict):
    page_id: int
    revision_id: int
    title: str
    text: str


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return element.find(f"{{*}}{name}")


def stream_pages(path: Path, *, max_documents: int | None = None) -> Iterator[RawPage]:
    """namespace 0의 비 redirect 문서에서 가장 최신 revision만 방출한다."""

    emitted = 0
    try:
        with bz2.open(path, "rb") as stream:
            for _event, element in ET.iterparse(stream, events=("end",)):
                if element.tag.rsplit("}", 1)[-1] != "page":
                    continue
                namespace = _child(element, "ns")
                redirect = _child(element, "redirect")
                if namespace is not None and namespace.text == "0" and redirect is None:
                    title = _child(element, "title")
                    page_id = _child(element, "id")
                    revisions = element.findall("{*}revision")
                    revision = revisions[-1] if revisions else None
                    revision_id = _child(revision, "id") if revision is not None else None
                    text = _child(revision, "text") if revision is not None else None
                    title_text = title.text if title is not None else None
                    page_id_text = page_id.text if page_id is not None else None
                    revision_id_text = revision_id.text if revision_id is not None else None
                    body_text = text.text if text is not None else None
                    if (
                        title_text is not None
                        and page_id_text is not None
                        and revision_id_text is not None
                        and body_text is not None
                    ):
                        yield RawPage(
                            page_id=int(page_id_text),
                            revision_id=int(revision_id_text),
                            title=title_text,
                            text=body_text,
                        )
                        emitted += 1
                element.clear()
                if max_documents is not None and emitted >= max_documents:
                    return
    except (OSError, EOFError, ET.ParseError) as exc:
        raise IntegrityError(f"MediaWiki bzip2 XML을 읽을 수 없습니다: {path}: {exc}") from exc
