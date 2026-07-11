import bz2
import hashlib
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import CleaningConfig, DataConfig
from llmex.data.clean import clean_page, normalize_text, parse_markup
from llmex.data.dedup import deduplicate
from llmex.data.download import download
from llmex.data.extract import stream_pages
from llmex.data.io import read_jsonl_zst
from llmex.data.pipeline import run_e2e
from llmex.data.schema import Document
from llmex.data.split import split_for
from llmex.errors import IntegrityError
from llmex.fingerprint import sha256_file

ROOT = Path(__file__).parents[1]
XML = ROOT / "tests/fixtures/kowiki-expanded.xml"
CONFIG = ROOT / "configs/data/sample.yaml"


@pytest.fixture
def expanded_bz2(tmp_path: Path) -> Path:
    path = tmp_path / "expanded.xml.bz2"
    path.write_bytes(bz2.compress(XML.read_bytes()))
    return path


def test_stream_extract_latest_main_namespace_without_redirect(expanded_bz2: Path) -> None:
    pages = list(stream_pages(expanded_bz2))
    assert [page["page_id"] for page in pages] == [10, 13, 14, 15]
    assert pages[0]["revision_id"] == 101
    assert "이전 판" not in pages[0]["text"]


def test_markup_policy_unicode_quality_and_attribution() -> None:
    source = XML.read_text(encoding="utf-8")
    fragment = source[
        source.index("== 개요 ==") : source.index("</text>", source.index("== 개요 =="))
    ]
    parsed, stats = parse_markup(html.unescape(fragment))
    assert "삭제할 표" not in parsed
    assert "삭제할 출처" not in parsed
    assert "수도" in parsed and "목록 첫째" in parsed and "x^2" in parsed
    assert stats["tables_dropped"] == 1 and stats["references_dropped"] == 1
    assert normalize_text("A\x00  e\u0301\t\t나") == "A é 나"
    result = clean_page(
        {
            "page_id": 1,
            "revision_id": 2,
            "title": "제목",
            "text": "대한민국의 [[수도]]는 서울이다. 충분히 긴 한국어 문장이다.",
        },
        dump_url="https://dumps.wikimedia.org/kowiki/20260701/x.bz2",
        dump_date="20260701",
        config=CleaningConfig(min_chars=10),
    )
    assert result.document is not None
    assert result.document.attribution().source_url.endswith("curid=1")
    assert "CC BY-SA" in result.document.license


def _document(page_id: int, text: str) -> Document:
    digest = hashlib.sha256(text.encode()).hexdigest()
    result = clean_page(
        {"page_id": page_id, "revision_id": page_id, "title": str(page_id), "text": text},
        dump_url="https://dumps.wikimedia.org/kowiki/20260701/x.bz2",
        dump_date="20260701",
        config=CleaningConfig(min_chars=1, min_hangul_ratio=0),
    )
    assert result.document is not None and result.document.sha256 == digest
    return result.document


def test_filters_exact_and_near_dedup() -> None:
    repetitive = clean_page(
        {"page_id": 1, "revision_id": 1, "title": "반복", "text": "가" * 100},
        dump_url="https://dumps.wikimedia.org/kowiki/20260701/x.bz2",
        dump_date="20260701",
        config=CleaningConfig(min_chars=1),
    )
    assert repetitive.reason == "repetition"
    first = _document(1, "한국어 데이터 문장은 충분히 길고 서로 비슷합니다.")
    duplicate = first.model_copy(update={"page_id": 2})
    near = _document(3, "한국어 데이터 문장은 충분히 길고 서로 아주 비슷합니다.")
    rows, stats = deduplicate([first, duplicate, near], near=True, threshold=0.5, shingle_size=3)
    assert len(list(rows)) == 1
    assert stats == {"exact_duplicates": 1, "near_duplicates": 1}


class _RangeHandler(BaseHTTPRequestHandler):
    payload = b"local-http-resume-payload" * 100

    def do_GET(self) -> None:
        start = int(self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0])
        body = self.payload[start:]
        self.send_response(206 if start else 200)
        self.send_header("Content-Length", str(len(body)))
        if start:
            self.send_header(
                "Content-Range", f"bytes {start}-{len(self.payload) - 1}/{len(self.payload)}"
            )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def test_local_http_range_resume_and_corrupt_checksum(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    target = tmp_path / "raw.bin"
    target.with_suffix(".bin.part").write_bytes(_RangeHandler.payload[:73])
    expected = hashlib.sha256(_RangeHandler.payload).hexdigest()
    try:
        result = download(
            f"http://127.0.0.1:{server.server_port}/raw",
            target,
            expected_sha256=expected,
            timeout=2,
            retries=1,
            backoff=0,
            disk_overhead_ratio=1,
        )
        assert result["resumed_from"] == 73 and target.read_bytes() == _RangeHandler.payload
        bad = tmp_path / "bad.bin"
        with pytest.raises(IntegrityError):
            download(
                f"http://127.0.0.1:{server.server_port}/raw",
                bad,
                expected_sha256="0" * 64,
                timeout=2,
                retries=0,
                backoff=0,
                disk_overhead_ratio=1,
            )
    finally:
        server.shutdown()
        thread.join()


def test_split_disjoint_and_deterministic_e2e(expanded_bz2: Path, tmp_path: Path) -> None:
    config = DataConfig.model_validate(
        json.loads(json.dumps(__import__("yaml").safe_load(CONFIG.read_text())))
    )
    first = run_e2e(config, expanded_bz2, tmp_path / "one", max_documents=1000)
    second = run_e2e(config, expanded_bz2, tmp_path / "two", max_documents=1000)
    assert first["corpus"]["sha256"] == second["corpus"]["sha256"]
    documents = [
        Document.model_validate(row) for row in read_jsonl_zst(tmp_path / "one/corpus-v1.jsonl.zst")
    ]
    split_hashes: dict[str, set[str]] = {name: set() for name in ("train", "validation", "test")}
    for document in documents:
        assert document.split == split_for(document.sha256, seed=config.seed)
        assert document.split is not None
        split_hashes[document.split].add(document.sha256)
        document.attribution()
    assert not (
        split_hashes["train"] & split_hashes["validation"]
        | split_hashes["train"] & split_hashes["test"]
        | split_hashes["validation"] & split_hashes["test"]
    )
    assert (tmp_path / "one/audit-sample.json").exists()


def test_m1_cli_dry_run_conflict_and_e2e(expanded_bz2: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "result"
    dry = runner.invoke(
        app,
        [
            "data",
            "sample-e2e",
            "--config",
            str(CONFIG),
            "--input",
            str(expanded_bz2),
            "--output-dir",
            str(output),
            "--max-documents",
            "1000",
            "--dry-run",
        ],
    )
    assert dry.exit_code == 0 and not output.exists()
    result = runner.invoke(
        app,
        [
            "data",
            "sample-e2e",
            "--config",
            str(CONFIG),
            "--input",
            str(expanded_bz2),
            "--output-dir",
            str(output),
            "--max-documents",
            "1000",
        ],
    )
    assert result.exit_code == 0, result.output
    conflict = runner.invoke(
        app,
        [
            "data",
            "sample-e2e",
            "--config",
            str(CONFIG),
            "--input",
            str(expanded_bz2),
            "--output-dir",
            str(output),
            "--max-documents",
            "2",
            "--force",
        ],
    )
    assert conflict.exit_code == 4
    assert len(sha256_file(output / "corpus-v1.jsonl.zst")) == 64
