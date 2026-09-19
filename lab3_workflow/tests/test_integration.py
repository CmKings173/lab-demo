from lab2_rag_agent.rag.service import RAGService
from lab2_rag_agent.reranking.service import FakeReranker
from lab2_rag_agent.retrieval.documents import FakeDocumentSearch
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

    assert [hit.chunk.id for hit in result.hits] == ["high", "low"]
    assert result.total == 2
