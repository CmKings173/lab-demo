from __future__ import annotations

import hashlib
from collections.abc import Sequence


class FakeEmbeddingProvider:
    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([digest[index] / 255 for index in range(self.dimensions)])
        return vectors


class BGEM3EmbeddingProvider:
    """Reserved for BGE-M3; model loading is intentionally deferred."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError("BGE-M3 model adapter is planned for a later phase")
