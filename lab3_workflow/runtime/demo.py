"""Runnable deterministic demo composition for local API and UI development."""

from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab2_rag_agent.retrieval.documents import FakeDocumentSearch
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.configuration.service import ProductConfigurationBuilder
from lab3_workflow.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from lab3_workflow.sizing.service import DeterministicSizingService
from lab3_workflow.validation.service import RuleBasedConfigurationValidator
from lab3_workflow.workflow.orchestrator import DeterministicWorkflow
from shared.contracts import (
    DocumentChunk,
    GPUOption,
    Product,
    ProductType,
    RAMOption,
    StorageOption,
)


def create_demo_workflow() -> DeterministicWorkflow:
    """Build the explicit in-memory composition used by the local demo app."""

    product = Product(
        id="demo-server-1",
        sku="DEMO-SERVER-1",
        name="Demo 4U AI Server",
        manufacturer="Lab Demo",
        product_type=ProductType.AI_SERVER,
        max_gpu_slots=4,
        max_ram_gb=1024,
        max_storage_gb=8000,
        storage_slots=8,
        base_price_vnd=100_000_000,
        base_price_includes={"chassis", "cpu", "storage"},
        source_urls=["https://example.invalid/catalog/demo-server-1"],
    )
    gpu = GPUOption(
        gpu_id="demo-gpu-96",
        name="Demo GPU 96",
        memory_gb=96,
        supported_product_ids=[product.id],
        price_vnd=50_000_000,
        source_urls=["https://example.invalid/catalog/demo-gpu-96"],
    )
    ram_options = [
        RAMOption(
            option_id=f"demo-ram-{capacity}",
            capacity_gb=capacity,
            supported_product_ids=[product.id],
            price_vnd=20_000_000,
            source_urls=[f"https://example.invalid/catalog/demo-ram-{capacity}"],
        )
        for capacity in (128, 256, 512)
    ]
    storage_options = [
        StorageOption(
            option_id=f"demo-storage-{capacity}",
            capacity_gb=capacity,
            supported_product_ids=[product.id],
            price_vnd=10_000_000,
            storage_type="ssd",
            source_urls=[f"https://example.invalid/catalog/demo-storage-{capacity}"],
        )
        for capacity in (1000, 2000)
    ]
    evidence = [
        DocumentChunk(
            id=f"{product.id}-max-gpu-slots",
            text="Verified max_gpu_slots 4",
            product_id=product.id,
            source_url="https://example.invalid/docs/demo-server-1#gpu-slots",
            metadata={
                "field_name": "max_gpu_slots",
                "value": "4",
                "verified": "true",
            },
        ),
        DocumentChunk(
            id=f"{product.id}-max-ram-gb",
            text="Verified max_ram_gb 1024",
            product_id=product.id,
            source_url="https://example.invalid/docs/demo-server-1#ram",
            metadata={
                "field_name": "max_ram_gb",
                "value": "1024",
                "verified": "true",
            },
        ),
        DocumentChunk(
            id=f"{product.id}-{gpu.gpu_id}-memory",
            text="Verified memory_gb 96",
            product_id=product.id,
            source_url="https://example.invalid/docs/demo-gpu-96#memory",
            metadata={
                "field_name": "memory_gb",
                "value": "96",
                "verified": "true",
            },
        ),
    ]
    return DeterministicWorkflow(
        repository=InMemoryProductRepository([product]),
        sizing_service=DeterministicSizingService(),
        configuration_builder=ProductConfigurationBuilder(
            [gpu], ram_options, storage_options
        ),
        validator=RuleBasedConfigurationValidator(),
        document_search=FakeDocumentSearch(evidence),
        comparison_service=RuleBasedComparisonService(),
        proposal_service=RuleBasedProposalService(),
        proposal_verifier=RuleBasedProposalVerifier(),
    )
