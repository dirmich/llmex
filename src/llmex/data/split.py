"""document hash 기반 상호 배타적 split."""

import hashlib


def split_for(document_hash: str, *, seed: int) -> str:
    value = (
        int.from_bytes(hashlib.sha256(f"{seed}:{document_hash}".encode()).digest()[:8], "big")
        % 10_000
    )
    if value < 9_800:
        return "train"
    if value < 9_900:
        return "validation"
    return "test"
