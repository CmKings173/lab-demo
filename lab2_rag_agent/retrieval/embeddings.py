from __future__ import annotations

import hashlib
from collections.abc import Sequence

from shared.contracts import EmbeddingVector


class FakeEmbeddingProvider:
    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        vectors: list[EmbeddingVector] = []
        for text in texts:
            raw = bytearray(hashlib.sha256(text.encode("utf-8")).digest())
            block = 1
            while len(raw) < self.dimensions:
                raw.extend(
                    hashlib.sha256(f"{text}\x00{block}".encode("utf-8")).digest()
                )
                block += 1
            vectors.append(
                EmbeddingVector(dense=[value / 255 for value in raw[: self.dimensions]])
            )
        return vectors


class BGEM3EmbeddingProvider:
    """Reserved for BGE-M3; model loading is intentionally deferred."""

    def embed(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        raise NotImplementedError("BGE-M3 model adapter is planned for a later phase")
