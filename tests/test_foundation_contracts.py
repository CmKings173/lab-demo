from services.sizing.service import estimate_ai_requirements
from shared.contracts import (
    DocumentChunk,
    DocumentHit,
    EmbeddingVector,
    GPUOption,
    Product,
    ProductConfiguration,
    ProductType,
    SizingRequest,
    UsageType,
)


def test_product_platform_is_separate_from_selected_gpu_configuration() -> None:
    product = Product(
        id="server-1",
        sku="SERVER-1",
        name="AI Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        cpu_options=["2x CPU"],
        max_ram_gb=2048,
        max_gpu_slots=8,
        max_storage_gb=16_000,
        source_urls=["https://example.invalid/server-1"],
    )
    gpu = GPUOption(
        gpu_id="gpu-96",
        name="96 GB GPU",
        memory_gb=96,
        supported_product_ids=[product.id],
        source_urls=["https://example.invalid/gpu-96"],
    )
    configuration = ProductConfiguration(
        configuration_id="server-1:gpu-96:1",
        product=product,
        selected_gpu=gpu,
        gpu_count=1,
        configured_ram_gb=512,
        configured_storage_gb=4000,
    )

    assert not hasattr(product, "vram_gb")
    assert configuration.total_vram_gb == 96


def test_sizing_returns_resource_need_without_assuming_48gb_gpus() -> None:
    result = estimate_ai_requirements(
        SizingRequest(model_parameters_b=32, usage=UsageType.INFERENCE)
    )

    assert result.estimated_model_memory_gb > 0
    assert result.recommended_total_vram_gb >= result.estimated_model_memory_gb
    assert result.recommended_system_ram_gb >= 64
    assert not hasattr(result, "minimum_gpu_count")
    assert all("48 GB" not in assumption for assumption in result.assumptions)


def test_embedding_vector_supports_dense_and_sparse_components() -> None:
    embedding = EmbeddingVector(
        dense=[0.1, 0.2],
        sparse_indices=[4, 10],
        sparse_values=[0.8, 0.3],
    )

    assert embedding.dense == [0.1, 0.2]
    assert dict(zip(embedding.sparse_indices, embedding.sparse_values, strict=True)) == {
        4: 0.8,
        10: 0.3,
    }


def test_document_hit_preserves_retrieval_and_rerank_scores() -> None:
    hit = DocumentHit(
        chunk=DocumentChunk(id="chunk-1", text="GPU evidence"),
        retrieval_score=0.72,
        rerank_score=0.91,
        rank=1,
        retrieval_method="hybrid",
    )

    assert hit.chunk.id == "chunk-1"
    assert hit.retrieval_score == 0.72
    assert hit.rerank_score == 0.91
    assert hit.retrieval_method == "hybrid"
