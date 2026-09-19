from shared.contracts import DocumentSearchRequest, DocumentSearchResult
from shared.interfaces import DocumentSearch, Reranker


class RAGService:
    """Retrieval seam; real Docling/BGE-M3/Qdrant integration is out of scope."""

    def __init__(self, search: DocumentSearch, reranker: Reranker) -> None:
        self.search_backend = search
        self.reranker = reranker

    def search_documents(self, request: DocumentSearchRequest) -> DocumentSearchResult:
        result = self.search_backend.search(request)
        ranked = self.reranker.rank(request.query, result.hits)
        selected = ranked[: request.top_k]
        return DocumentSearchResult(hits=selected, total=len(selected))
