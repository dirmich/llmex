"""token shard dataset과 상태 복구 가능한 결정적 sampler."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import bisect
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from torch import Tensor

from llmex.errors import IntegrityError
from llmex.fingerprint import sha256_file


class TokenShardDataset:
    """manifest의 shard를 읽고 shard 경계를 가로지르는 연속 token window를 제공한다."""

    def __init__(self, manifest_path: Path, split: str, sequence_length: int) -> None:
        self.manifest_path = manifest_path.resolve()
        self.manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.sequence_length = sequence_length
        split_data = self.manifest.get("splits", {}).get(split)
        if not isinstance(split_data, dict):
            raise IntegrityError(f"shard manifest에 {split} split이 없습니다")
        dtype = np.dtype(str(self.manifest["dtype"]))
        self.shards: list[np.memmap[Any, Any]] = []
        self.ends: list[int] = []
        total = 0
        items = split_data.get("shards", [])
        if not isinstance(items, list):
            raise IntegrityError("shard 목록 형식이 올바르지 않습니다")
        for raw_item in items:
            if not isinstance(raw_item, dict):
                raise IntegrityError("shard 항목 형식이 올바르지 않습니다")
            item = raw_item
            path = manifest_path.parent / str(item["path"])
            if not path.is_file() or sha256_file(path) != item["sha256"]:
                raise IntegrityError(f"token shard checksum이 일치하지 않습니다: {path}")
            array = np.memmap(path, dtype=dtype, mode="r")
            if len(array) != int(item["tokens"]):
                raise IntegrityError(f"token shard 길이가 manifest와 다릅니다: {path}")
            self.shards.append(array)
            total += len(array)
            self.ends.append(total)
        self.token_count = total
        self.window_count = max(0, total - sequence_length + 1)
        if self.window_count == 0:
            raise IntegrityError(f"{split} token 수가 sequence_length보다 작습니다")

    def window(self, start: int) -> Tensor:
        if not 0 <= start < self.window_count:
            raise IndexError(start)
        remaining = self.sequence_length
        position = start
        chunks: list[np.ndarray[Any, Any]] = []
        while remaining:
            index = bisect.bisect_right(self.ends, position)
            shard_start = 0 if index == 0 else self.ends[index - 1]
            offset = position - shard_start
            take = min(remaining, len(self.shards[index]) - offset)
            chunks.append(np.asarray(self.shards[index][offset : offset + take], dtype=np.int64))
            position += take
            remaining -= take
        values = chunks[0].copy() if len(chunks) == 1 else np.concatenate(chunks)
        return torch.from_numpy(values)


class DeterministicBatchSampler:
    """epoch별 randperm와 cursor를 checkpoint로 완전 복구하는 batch sampler."""

    def __init__(self, size: int, batch_size: int, seed: int) -> None:
        if size < batch_size:
            raise IntegrityError("sampler dataset 크기가 batch_size보다 작습니다")
        self.size = size
        self.batch_size = batch_size
        self.seed = seed
        self.epoch = 0
        self.cursor = 0
        self._order = self._make_order()

    def _make_order(self) -> Tensor:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(self.seed + self.epoch)
        return torch.randperm(self.size, generator=generator)

    def next(self) -> list[int]:
        if self.cursor + self.batch_size > self.size:
            self.epoch += 1
            self.cursor = 0
            self._order = self._make_order()
        result = self._order[self.cursor : self.cursor + self.batch_size].tolist()
        self.cursor += self.batch_size
        return [int(value) for value in result]

    def state_dict(self) -> dict[str, int]:
        return {"seed": self.seed, "epoch": self.epoch, "cursor": self.cursor}

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        if set(state) != {"seed", "epoch", "cursor"}:
            raise IntegrityError("sampler checkpoint 구조가 올바르지 않습니다")
        raw_seed, raw_epoch, raw_cursor = state["seed"], state["epoch"], state["cursor"]
        for value in (raw_seed, raw_epoch, raw_cursor):
            if not isinstance(value, int) or isinstance(value, bool):
                raise IntegrityError("sampler checkpoint 값이 올바른 정수가 아닙니다")
        seed = cast(int, raw_seed)
        epoch = cast(int, raw_epoch)
        cursor = cast(int, raw_cursor)
        if seed != self.seed:
            raise IntegrityError("sampler seed가 checkpoint와 다릅니다")
        if epoch < 0:
            raise IntegrityError("sampler epoch가 범위를 벗어났습니다")
        if not 0 <= cursor <= self.size or cursor % self.batch_size != 0:
            raise IntegrityError("sampler cursor가 범위를 벗어났습니다")
        self.epoch = epoch
        self.cursor = cursor
        self._order = self._make_order()


def batch(dataset: TokenShardDataset, sampler: DeterministicBatchSampler) -> Tensor:
    return torch.stack([dataset.window(index) for index in sampler.next()])
