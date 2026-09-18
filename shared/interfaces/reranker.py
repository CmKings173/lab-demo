from typing import Protocol, Sequence

from shared.contracts import DocumentChunk


class Reranker(Protocol):
    def rank(self, query: str, chunks: Sequence[DocumentChunk]) -> list[DocumentChunk]: ...
