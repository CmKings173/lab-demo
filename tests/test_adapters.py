from shared.contracts import (
    DocumentChunk,
    DocumentSearchRequest,
    Product,
    ProductFilter,
    ProductSearchRequest,
    ProductType,
)
from adapters.catalog import InMemoryProductRepository
from adapters.documents import FakeDocumentSearch
from adapters.embeddings import FakeEmbeddingProvider
from adapters.model import FakeModelClient
from adapters.reranking import FakeReranker


def make_product(product_id: str, price: int, ram: int, gpu_count: int) -> Product:
    return Product(
        id=product_id,
        sku=product_id.upper(),
        name=f"Product {product_id}",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_gpu_count=gpu_count,
        vram_gb=48,
        default_ram_gb=ram,
        max_ram_gb=1024,
        price_vnd=price,
    )


def test_in_memory_catalog_applies_numeric_filters() -> None:
    repository = InMemoryProductRepository(
        [make_product("small", 100, 256, 2), make_product("large", 300, 512, 4)]
    )

    result = repository.search(
        ProductSearchRequest(
            filters=ProductFilter(min_ram_gb=512, min_gpu_count=4, max_price_vnd=350)
        )
    )

    assert [product.id for product in result.products] == ["large"]


def test_fake_document_search_and_reranker_are_deterministic() -> None:
    chunks = [
        DocumentChunk(id="1", text="GPU and RAM requirements", product_id="p-1"),
        DocumentChunk(id="2", text="Warranty information", product_id="p-1"),
    ]
    search = FakeDocumentSearch(chunks)
    found = search.search(DocumentSearchRequest(query="GPU", product_id="p-1"))
    ranked = FakeReranker().rank("GPU", found.chunks)

    assert [chunk.id for chunk in ranked] == ["1"]


def test_fake_embeddings_return_repeatable_vectors() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)

    assert provider.embed(["hello"]) == provider.embed(["hello"])
    assert len(provider.embed(["hello"])[0]) == 4


def test_fake_embeddings_support_dimensions_beyond_single_digest() -> None:
    provider = FakeEmbeddingProvider(dimensions=64)

    first = provider.embed(["hello", "world"])
    second = provider.embed(["hello", "world"])

    assert first == second
    assert [len(vector) for vector in first] == [64, 64]
    assert first[0] != first[1]


def test_fake_model_client_returns_configured_deterministic_response() -> None:
    client = FakeModelClient(response="stable response")

    assert client.generate("first prompt") == "stable response"
    assert client.generate("second prompt") == "stable response"
