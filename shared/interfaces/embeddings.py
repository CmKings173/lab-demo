from typing import Protocol, Sequence

from shared.contracts import EmbeddingVector


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[EmbeddingVector]: ...
