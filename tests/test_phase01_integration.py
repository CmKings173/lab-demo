from adapters.documents import FakeDocumentSearch
from adapters.reranking import FakeReranker
from services.rag import RAGService
from shared.contracts import DocumentChunk, DocumentSearchRequest


def test_rag_service_composes_fake_search_and_reranker_offline() -> None:
    service = RAGService(
        search=FakeDocumentSearch(
            [
                DocumentChunk(id="low", text="GPU information", product_id="p-1"),
                DocumentChunk(
                    id="high",
                    text="GPU RAM requirements and GPU sizing",
                    product_id="p-1",
                ),
            ]
        ),
        reranker=FakeReranker(),
    )

    result = service.search_documents(
        DocumentSearchRequest(query="GPU RAM", product_id="p-1", top_k=2)
    )

    assert [chunk.id for chunk in result.chunks] == ["high", "low"]
    assert result.total == 2
