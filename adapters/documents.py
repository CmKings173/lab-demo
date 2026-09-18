from __future__ import annotations

from collections.abc import Iterable

from shared.contracts import DocumentChunk, DocumentHit, DocumentSearchRequest, DocumentSearchResult


class FakeDocumentSearch:
    def __init__(self, chunks: Iterable[DocumentChunk] = ()) -> None:
        self._chunks = list(chunks)

    def search(self, request: DocumentSearchRequest) -> DocumentSearchResult:
        query_terms = set(request.query.casefold().split())
        matches = [
            chunk
            for chunk in self._chunks
            if (request.product_id is None or chunk.product_id == request.product_id)
            and query_terms.intersection(chunk.text.casefold().split())
        ][: request.top_k]
        hits = [
            DocumentHit(
                chunk=chunk,
                retrieval_score=1.0,
                rank=index,
                retrieval_method="fake_keyword",
            )
            for index, chunk in enumerate(matches, start=1)
        ]
        return DocumentSearchResult(hits=hits, total=len(hits))


class QdrantDocumentSearch:
    """Reserved for hybrid Qdrant retrieval; unavailable in the foundation phase."""

    def search(self, request: DocumentSearchRequest) -> DocumentSearchResult:
        raise NotImplementedError("Qdrant document search is planned for a later phase")
