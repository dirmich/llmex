"""결정적 byte-level BPE 학습과 artifact 무결성."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from tokenizers import Tokenizer
from tokenizers.decoders import ByteLevel as ByteLevelDecoder
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.trainers import BpeTrainer

from llmex.config import TokenizerConfig
from llmex.data.io import prepare_output, read_jsonl_zst, write_json
from llmex.errors import InputError, IntegrityError
from llmex.fingerprint import fingerprint, sha256_file

SPECIAL_TOKENS = ("<pad>", "<bos>", "<eos>", "<unk>")
SPECIAL_IDS = {token: index for index, token in enumerate(SPECIAL_TOKENS)}


def iter_documents(corpus: Path, *, split: str | None = None) -> Iterator[dict[str, Any]]:
    """압축 corpus를 메모리에 적재하지 않고 순서대로 검증해 읽는다."""

    if not corpus.is_file():
        raise InputError(f"corpus 파일이 없습니다: {corpus}")
    for row in read_jsonl_zst(corpus):
        row_split = row.get("split")
        if row_split not in {"train", "validation", "test"}:
            raise IntegrityError("corpus 문서의 split이 없거나 올바르지 않습니다")
        if split is None or row_split == split:
            text = row.get("text")
            digest = row.get("sha256")
            if not isinstance(text, str) or not text or not isinstance(digest, str):
                raise IntegrityError("corpus 문서 text/sha256가 올바르지 않습니다")
            yield row


def corpus_fingerprint(corpus: Path) -> dict[str, Any]:
    """파일 checksum과 split별 source 문서 집합을 함께 고정한다."""

    splits: dict[str, list[str]] = {name: [] for name in ("train", "validation", "test")}
    for row in iter_documents(corpus):
        splits[str(row["split"])].append(str(row["sha256"]))
    overlap = (
        (set(splits["train"]) & set(splits["validation"]))
        | (set(splits["train"]) & set(splits["test"]))
        | (set(splits["validation"]) & set(splits["test"]))
    )
    if overlap:
        raise IntegrityError("source/split 누출을 발견했습니다")
    value = {"corpus_sha256": sha256_file(corpus), "splits": splits}
    return {**value, "fingerprint": fingerprint(value)}


def build_tokenizer() -> Tokenizer:
    tokenizer = Tokenizer(BPE(unk_token="<unk>", byte_fallback=True))
    byte_level = ByteLevel(add_prefix_space=False, use_regex=True)
    tokenizer.pre_tokenizer = byte_level
    tokenizer.decoder = ByteLevelDecoder()
    return tokenizer


def _assert_contract(tokenizer: Tokenizer) -> None:
    for token, expected in SPECIAL_IDS.items():
        if tokenizer.token_to_id(token) != expected:
            raise IntegrityError(f"special token ID 계약 위반: {token}={expected}")


def train(config: TokenizerConfig, *, force: bool = False) -> dict[str, Any]:
    """train split만 streaming 학습하고 표준 artifact와 checksum manifest를 쓴다."""

    corpus = corpus_fingerprint(config.corpus)
    operation = {
        "command": "tokenizer train",
        "config": config.model_dump(mode="json"),
        "corpus": corpus,
    }
    manifest_path = config.output_dir / "tokenizer-manifest.json"
    prepare_output(manifest_path, operation, force=force)
    temporary = config.output_dir.with_name(config.output_dir.name + ".tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    tokenizer = build_tokenizer()
    trainer = BpeTrainer(
        vocab_size=config.vocab_size,
        special_tokens=list(SPECIAL_TOKENS),
        initial_alphabet=ByteLevel.alphabet(),
        show_progress=False,
    )
    tokenizer.train_from_iterator(
        (str(row["text"]) for row in iter_documents(config.corpus, split="train")), trainer=trainer
    )
    _assert_contract(tokenizer)
    tokenizer.save(str(temporary / "tokenizer.json"))
    model_files = tokenizer.model.save(str(temporary))
    Path(model_files[0]).replace(temporary / "vocab.json")
    Path(model_files[1]).replace(temporary / "merges.txt")
    write_json(temporary / "config.json", config.model_dump(mode="json"))
    artifacts = {}
    for name in ("tokenizer.json", "vocab.json", "merges.txt", "config.json"):
        artifacts[name] = {
            "sha256": sha256_file(temporary / name),
            "bytes": (temporary / name).stat().st_size,
        }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "algorithm": "Hugging Face tokenizers byte-level BPE",
        "byte_fallback": True,
        "vocab_size_requested": config.vocab_size,
        "vocab_size_actual": tokenizer.get_vocab_size(),
        "special_token_ids": SPECIAL_IDS,
        "training_split": "train",
        "training_documents": len(corpus["splits"]["train"]),
        "corpus": corpus,
        "artifacts": artifacts,
    }
    manifest["fingerprint"] = fingerprint(manifest)
    write_json(temporary / "tokenizer-manifest.json", manifest)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    for path in temporary.iterdir():
        os.replace(path, config.output_dir / path.name)
    temporary.rmdir()
    return manifest


def load_tokenizer(directory: Path) -> Tokenizer:
    manifest_path = directory / "tokenizer-manifest.json"
    if not manifest_path.is_file():
        raise InputError(f"tokenizer manifest가 없습니다: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, metadata in manifest["artifacts"].items():
        if sha256_file(directory / name) != metadata["sha256"]:
            raise IntegrityError(f"tokenizer artifact checksum 불일치: {name}")
    tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
    _assert_contract(tokenizer)
    return tokenizer


def verify_round_trip(tokenizer: Tokenizer, samples: Iterator[str]) -> int:
    count = 0
    for text in samples:
        encoded = tokenizer.encode(text)
        if SPECIAL_IDS["<unk>"] in encoded.ids:
            raise IntegrityError(f"UNK가 생성되었습니다: sample={count}")
        if tokenizer.decode(encoded.ids, skip_special_tokens=False) != text:
            raise IntegrityError(f"Unicode round-trip 실패: sample={count}")
        count += 1
    return count
