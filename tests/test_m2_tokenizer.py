import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner

from llmex.cli import app
from llmex.config import TokenizerConfig
from llmex.data.io import write_jsonl_zst
from llmex.errors import ConflictError, IntegrityError
from llmex.fingerprint import sha256_file
from llmex.tokenizer.core import SPECIAL_IDS, corpus_fingerprint, load_tokenizer, train
from llmex.tokenizer.evaluate import evaluate, fixed_unicode_samples
from llmex.tokenizer.pack import pack


def _row(index: int, split: str, text: str) -> dict[str, object]:
    digest = hashlib.sha256(f"{index}:{text}".encode()).hexdigest()
    return {"split": split, "text": text, "sha256": digest}


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    path = tmp_path / "corpus-v1.jsonl.zst"
    rows = [
        _row(1, "train", "대한민국 서울 한글 토크나이저 ASCII 123"),
        _row(2, "train", "한글 완성형과 자모 ㅎㅏㄴㄱㅡㄹ 그리고 漢字"),
        _row(3, "validation", "검증 전용 문자열 validation-only 👨‍👩‍👧‍👦"),
        _row(4, "test", "시험 전용 NFD 한글 e\u0301 A\u0327\u0301"),
    ]
    write_jsonl_zst(path, rows)
    return path


def _config(corpus: Path, output: Path, samples: int = 10_000) -> TokenizerConfig:
    return TokenizerConfig(
        name="fixture",
        seed=42,
        vocab_size=16000,
        corpus=corpus,
        output_dir=output,
        shard_tokens=7,
        evaluation_samples=samples,
    )


def test_special_ids_train_only_determinism_and_artifacts(corpus: Path, tmp_path: Path) -> None:
    first = _config(corpus, tmp_path / "one")
    second_corpus = tmp_path / "changed-validation.jsonl.zst"
    rows = list(__import__("llmex.data.io", fromlist=["read_jsonl_zst"]).read_jsonl_zst(corpus))
    rows[2]["text"] = "완전히 바뀐 검증 문자열"
    write_jsonl_zst(second_corpus, rows)
    second = _config(second_corpus, tmp_path / "two")
    manifest = train(first)
    train(second)
    tokenizer = load_tokenizer(first.output_dir)
    assert {token: tokenizer.token_to_id(token) for token in SPECIAL_IDS} == SPECIAL_IDS
    assert manifest["training_documents"] == 2 and manifest["training_split"] == "train"
    assert sha256_file(first.output_dir / "tokenizer.json") == sha256_file(
        second.output_dir / "tokenizer.json"
    )
    assert {path.name for path in first.output_dir.iterdir()} >= {
        "tokenizer.json",
        "vocab.json",
        "merges.txt",
        "config.json",
        "tokenizer-manifest.json",
    }


def test_unicode_round_trip_unk_zero_and_fixed_10000(corpus: Path, tmp_path: Path) -> None:
    config = _config(corpus, tmp_path / "tokenizer")
    train(config)
    tokenizer = load_tokenizer(config.output_dir)
    required = [
        "한글",
        "ㅎㅏㄴㄱㅡㄹ",
        "한글",
        "👨‍👩‍👧‍👦",
        "漢字",
        "ASCII",
        "e\u0301",
        "A\u0327\u0301",
    ]
    samples = [*required, *fixed_unicode_samples(10_000 - len(required), 777)]
    for text in samples:
        encoded = tokenizer.encode(text)
        assert SPECIAL_IDS["<unk>"] not in encoded.ids
        assert tokenizer.decode(encoded.ids) == text


@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(st.text(alphabet=st.characters(exclude_categories=("Cs",))))
def test_unicode_property_round_trip(corpus: Path, tmp_path: Path, text: str) -> None:
    output = tmp_path / "property-tokenizer"
    config = _config(corpus, output, 1)
    if not output.exists():
        train(config)
    tokenizer = load_tokenizer(output)
    encoded = tokenizer.encode(text)
    assert SPECIAL_IDS["<unk>"] not in encoded.ids
    assert tokenizer.decode(encoded.ids) == text


def test_eos_dtype_boundaries_alignment_and_deterministic_shards(
    corpus: Path, tmp_path: Path
) -> None:
    first = _config(corpus, tmp_path / "one")
    second = _config(corpus, tmp_path / "two")
    train(first)
    train(second)
    evaluate(first)
    assert json.loads((first.output_dir / "evaluation.json").read_text())["unk_tokens"] == 0
    one = pack(first)
    two = pack(second)
    assert one["dtype"] == "<u2"
    for split in ("train", "validation", "test"):
        one_hashes = [item["sha256"] for item in one["splits"][split]["shards"]]
        two_hashes = [item["sha256"] for item in two["splits"][split]["shards"]]
        assert one_hashes == two_hashes
        arrays = [
            np.fromfile(first.output_dir / "shards" / item["path"], dtype=one["dtype"])
            for item in one["splits"][split]["shards"]
        ]
        tokens: list[int] = np.concatenate(arrays).astype(np.uint32).tolist() if arrays else []
        previous = 0
        for boundary in one["splits"][split]["boundaries"]:
            assert boundary["start"] == previous
            assert tokens[boundary["eos"]] == SPECIAL_IDS["<eos>"]
            previous = boundary["end"]
        assert previous == len(tokens)


def test_split_leak_and_fingerprint_conflict(corpus: Path, tmp_path: Path) -> None:
    leaked = tmp_path / "leaked.jsonl.zst"
    duplicate = "a" * 64
    write_jsonl_zst(
        leaked,
        [
            _row(1, "train", "가") | {"sha256": duplicate},
            _row(2, "test", "나") | {"sha256": duplicate},
        ],
    )
    with pytest.raises(IntegrityError, match="누출"):
        corpus_fingerprint(leaked)
    config = _config(corpus, tmp_path / "output", 1)
    train(config)
    with pytest.raises(ConflictError):
        train(config.model_copy(update={"seed": 43}), force=True)


def test_cli_dry_run_train_evaluate_pack(corpus: Path, tmp_path: Path) -> None:
    output = tmp_path / "cli-output"
    config = tmp_path / "tokenizer.yaml"
    config.write_text(
        "name: fixture\n"
        "seed: 42\n"
        "vocab_size: 16000\n"
        f"corpus: {corpus}\n"
        f"output_dir: {output}\n"
        "shard_tokens: 7\n"
        "evaluation_samples: 32\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    dry = runner.invoke(app, ["tokenizer", "train", "--config", str(config), "--dry-run"])
    assert dry.exit_code == 0 and not output.exists()
    for command in ("train", "evaluate", "pack"):
        result = runner.invoke(app, ["tokenizer", command, "--config", str(config)])
        assert result.exit_code == 0, result.output
    assert (output / "shards/manifest.json").is_file()
