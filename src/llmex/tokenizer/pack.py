"""문서 경계를 보존하는 원자적 memory-mapped token shard writer."""

import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from llmex.config import TokenizerConfig
from llmex.data.io import prepare_output, write_json
from llmex.errors import IntegrityError
from llmex.fingerprint import fingerprint, sha256_file
from llmex.tokenizer.core import SPECIAL_IDS, corpus_fingerprint, iter_documents, load_tokenizer


def _write_shard(path: Path, ids: list[int], dtype: np.dtype[Any]) -> dict[str, Any]:
    temporary = path.with_suffix(path.suffix + ".tmp")
    mmap = np.memmap(temporary, dtype=dtype, mode="w+", shape=(len(ids),))
    mmap[:] = ids
    mmap.flush()
    del mmap
    descriptor = os.open(temporary, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    return {
        "path": path.name,
        "tokens": len(ids),
        "sha256": sha256_file(path),
        "min_id": min(ids),
        "max_id": max(ids),
    }


def pack(config: TokenizerConfig, *, force: bool = False) -> dict[str, Any]:
    tokenizer = load_tokenizer(config.output_dir)
    corpus = corpus_fingerprint(config.corpus)
    tokenizer_sha256 = sha256_file(config.output_dir / "tokenizer.json")
    operation = {
        "command": "tokenizer pack",
        "config": config.model_dump(mode="json"),
        "corpus": corpus,
        "tokenizer_sha256": tokenizer_sha256,
    }
    output = config.output_dir / "shards"
    manifest_path = output / "manifest.json"
    prepare_output(manifest_path, operation, force=force)
    temporary = output.with_name("shards.tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    vocab_max = tokenizer.get_vocab_size() - 1
    dtype = np.dtype("<u2" if vocab_max <= np.iinfo(np.uint16).max else "<u4")
    if vocab_max > np.iinfo(np.uint32).max:
        raise IntegrityError("token ID가 uint32 범위를 초과합니다")
    split_manifests: dict[str, Any] = {}
    for split in ("train", "validation", "test"):
        shards: list[dict[str, Any]] = []
        boundaries: list[dict[str, Any]] = []
        pending: list[int] = []
        total = 0
        for row in iter_documents(config.corpus, split=split):
            ids = [*tokenizer.encode(str(row["text"])).ids, SPECIAL_IDS["<eos>"]]
            boundaries.append(
                {
                    "sha256": row["sha256"],
                    "start": total,
                    "end": total + len(ids),
                    "eos": total + len(ids) - 1,
                }
            )
            total += len(ids)
            pending.extend(ids)
            while len(pending) >= config.shard_tokens:
                chunk, pending = pending[: config.shard_tokens], pending[config.shard_tokens :]
                shards.append(
                    _write_shard(temporary / f"{split}-{len(shards):05d}.bin", chunk, dtype)
                )
        if pending:
            shards.append(
                _write_shard(temporary / f"{split}-{len(shards):05d}.bin", pending, dtype)
            )
        split_manifests[split] = {
            "tokens": total,
            "documents": len(boundaries),
            "boundaries": boundaries,
            "shards": shards,
        }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "dtype": dtype.str,
        "tokenizer_sha256": tokenizer_sha256,
        "tokenizer_fingerprint": json.loads(
            (config.output_dir / "tokenizer-manifest.json").read_text()
        )["fingerprint"],
        "corpus": corpus,
        "eos_id": SPECIAL_IDS["<eos>"],
        "splits": split_manifests,
    }
    manifest["fingerprint"] = fingerprint(manifest)
    write_json(temporary / "manifest.json", manifest)
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("*.bin"):
        old.unlink()
    for path in temporary.iterdir():
        os.replace(path, output / path.name)
    temporary.rmdir()
    return manifest
