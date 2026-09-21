from adapters.fake.catalog import InMemoryProductRepository
from adapters.fake.documents import FakeDocumentSearch
from adapters.fake.embeddings import FakeEmbeddingProvider
from adapters.fake.model import FakeModelClient
from adapters.fake.reranking import FakeReranker
from shared.contracts import (
    ChatMessage,
    DocumentChunk,
    DocumentSearchRequest,
    Product,
    ProductFilter,
    ProductSearchRequest,
    ProductType,
)


def make_product(product_id: str, price: int, ram: int, gpu_count: int) -> Product:
    return Product(
        id=product_id,
        sku=product_id.upper(),
        name=f"Product {product_id}",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_gpu_slots=gpu_count,
        max_ram_gb=ram,
        base_price_vnd=price,
    )


def test_in_memory_catalog_applies_numeric_filters() -> None:
    repository = InMemoryProductRepository(
        [make_product("small", 100, 256, 2), make_product("large", 300, 512, 4)]
    )

    result = repository.search(
        ProductSearchRequest(
            filters=ProductFilter(min_ram_gb=512, min_gpu_count=4, max_base_price_vnd=350)
        )
    )

    assert [product.id for product in result.products] == ["large"]


def test_product_search_total_is_counted_before_limit() -> None:
    repository = InMemoryProductRepository(
        [make_product(f"p-{index:02d}", 100, 256, 2) for index in range(30)]
    )

    result = repository.search(ProductSearchRequest(limit=10))

    assert len(result.products) == 10
    assert result.total == 30


def test_fake_document_search_and_reranker_are_deterministic() -> None:
    chunks = [
        DocumentChunk(id="1", text="GPU and RAM requirements", product_id="p-1"),
        DocumentChunk(id="2", text="Warranty information", product_id="p-1"),
    ]
    search = FakeDocumentSearch(chunks)
    found = search.search(DocumentSearchRequest(query="GPU", product_id="p-1"))
    ranked = FakeReranker().rank("GPU", found.hits)

    assert [hit.chunk.id for hit in ranked] == ["1"]


def test_fake_embeddings_return_repeatable_vectors() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)

    assert provider.embed(["hello"]) == provider.embed(["hello"])
    assert len(provider.embed(["hello"])[0].dense) == 4


def test_fake_embeddings_support_dimensions_beyond_single_digest() -> None:
    provider = FakeEmbeddingProvider(dimensions=64)

    first = provider.embed(["hello", "world"])
    second = provider.embed(["hello", "world"])

    assert first == second
    assert [len(vector.dense) for vector in first] == [64, 64]
    assert first[0] != first[1]


def test_fake_model_client_returns_configured_deterministic_response() -> None:
    client = FakeModelClient(response="stable response")

    first = client.complete([ChatMessage(role="user", content="first prompt")])
    second = client.complete([ChatMessage(role="user", content="second prompt")])
    assert first.message.content == "stable response"
    assert second.message.content == "stable response"
