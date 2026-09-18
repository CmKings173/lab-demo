from collections.abc import Sequence

from shared.contracts import DocumentChunk


class FakeReranker:
    def rank(self, query: str, chunks: Sequence[DocumentChunk]) -> list[DocumentChunk]:
        terms = set(query.casefold().split())
        return sorted(
            chunks,
            key=lambda chunk: len(terms.intersection(chunk.text.casefold().split())),
            reverse=True,
        )


class BGEReranker:
    """Reserved for a local BGE reranker; model loading is deferred."""

    def rank(self, query: str, chunks: Sequence[DocumentChunk]) -> list[DocumentChunk]:
        raise NotImplementedError("BGE reranker is planned for a later phase")
