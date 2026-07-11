"""exact SHA-256와 선택적 결정적 MinHash near-dedup."""

import hashlib
from collections.abc import Iterable, Iterator

from llmex.data.schema import Document


def shingles(text: str, size: int) -> set[str]:
    compact = " ".join(text.split())
    if len(compact) <= size:
        return {compact}
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def signature(text: str, *, size: int, permutations: int = 64) -> tuple[int, ...]:
    values = shingles(text, size)
    return tuple(
        min(
            int.from_bytes(hashlib.sha256(f"{seed}:".encode() + item.encode()).digest()[:8], "big")
            for item in values
        )
        for seed in range(permutations)
    )


def deduplicate(
    documents: Iterable[Document], *, near: bool, threshold: float, shingle_size: int
) -> tuple[Iterator[Document], dict[str, int]]:
    stats = {"exact_duplicates": 0, "near_duplicates": 0}

    def iterator() -> Iterator[Document]:
        exact: set[str] = set()
        signatures: list[tuple[int, ...]] = []
        for document in documents:
            if document.sha256 in exact:
                stats["exact_duplicates"] += 1
                continue
            exact.add(document.sha256)
            if near:
                candidate = signature(document.text, size=shingle_size)
                if any(
                    sum(left == right for left, right in zip(candidate, previous, strict=True))
                    / len(candidate)
                    >= threshold
                    for previous in signatures
                ):
                    stats["near_duplicates"] += 1
                    continue
                signatures.append(candidate)
            yield document

    return iterator(), stats
