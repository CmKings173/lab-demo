import pytest

from adapters.catalog import InMemoryProductRepository
from adapters.documents import FakeDocumentSearch
from services.comparison.service import RuleBasedComparisonService
from services.configuration.service import ProductConfigurationBuilder
from services.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from services.sizing.service import DeterministicSizingService
from services.validation.service import RuleBasedConfigurationValidator
from shared.contracts import (
    CustomerRequirement,
    DocumentChunk,
    GPUOption,
    Product,
    ProductType,
    UsageType,
    WorkflowContext,
    WorkflowState,
)
from workflow.orchestrator import DeterministicWorkflow, WorkflowTransitionError


def make_compatible_product() -> Product:
    return Product(
        id="server-1",
        sku="SERVER-1",
        name="Demo 4U AI Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_gpu_slots=4,
        max_ram_gb=1024,
        max_storage_gb=8000,
        storage_slots=8,
        base_price_vnd=100_000_000,
        source_urls=["https://example.invalid/server-1"],
    )


def build_workflow(repository: InMemoryProductRepository) -> DeterministicWorkflow:
    gpu = GPUOption(
        gpu_id="gpu-96",
        name="GPU 96",
        memory_gb=96,
        supported_product_ids=["server-1"],
        price_vnd=50_000_000,
        source_urls=["https://example.invalid/gpu-96"],
    )
    return DeterministicWorkflow(
        repository=repository,
        sizing_service=DeterministicSizingService(),
        configuration_builder=ProductConfigurationBuilder(
            [gpu], {"server-1": {"ram": 20_000_000, "storage": 10_000_000}}
        ),
        validator=RuleBasedConfigurationValidator(),
        document_search=FakeDocumentSearch(
            [
                DocumentChunk(
                    id="doc-vram",
                    text="VRAM được xác minh",
                    product_id="server-1",
                    source_url="https://example.invalid/doc-vram",
                    metadata={
                        "field_name": "total_vram_gb",
                        "value": "96",
                        "verified": "true",
                    },
                ),
                DocumentChunk(
                    id="doc-ram",
                    text="RAM được xác minh",
                    product_id="server-1",
                    source_url="https://example.invalid/doc-ram",
                    metadata={
                        "field_name": "configured_ram_gb",
                        "value": "192",
                        "verified": "true",
                    },
                ),
            ]
        ),
        comparison_service=RuleBasedComparisonService(),
        proposal_service=RuleBasedProposalService(),
        proposal_verifier=RuleBasedProposalVerifier(),
    )


def test_workflow_reaches_complete_with_evidence() -> None:
    workflow = build_workflow(InMemoryProductRepository([make_compatible_product()]))
    context = workflow.run(
        CustomerRequirement(
            model_size_b=20,
            usage=UsageType.INFERENCE,
            concurrent_users=2,
            budget_vnd=300_000_000,
            storage_requirement_gb=1000,
        )
    )

    assert context.state == WorkflowState.COMPLETE
    assert context.candidates
    assert context.proposal is not None
    assert context.proposal.evidence


def test_missing_budget_stops_before_product_search() -> None:
    class CountingRepository(InMemoryProductRepository):
        searches = 0

        def search(self, request):
            self.searches += 1
            return super().search(request)

    repository = CountingRepository([make_compatible_product()])
    context = build_workflow(repository).run(
        CustomerRequirement(model_size_b=32, usage=UsageType.INFERENCE)
    )

    assert context.state == WorkflowState.MISSING_INFORMATION
    assert context.missing_fields == ["budget_vnd"]
    assert repository.searches == 0


def test_workflow_rejects_illegal_transition() -> None:
    context = WorkflowContext(
        requirement=CustomerRequirement(
            model_size_b=32,
            usage=UsageType.INFERENCE,
            budget_vnd=300_000_000,
        ),
        history=[WorkflowState.RECEIVED],
    )

    with pytest.raises(WorkflowTransitionError):
        DeterministicWorkflow._transition(context, WorkflowState.SIZE)


def test_workflow_terminal_failure_cannot_return_to_active_state() -> None:
    context = WorkflowContext(
        requirement=CustomerRequirement(
            model_size_b=32,
            usage=UsageType.INFERENCE,
            budget_vnd=300_000_000,
        ),
        state=WorkflowState.SIZING_FAILED,
        history=[WorkflowState.RECEIVED, WorkflowState.SIZING_FAILED],
    )

    with pytest.raises(WorkflowTransitionError):
        DeterministicWorkflow._transition(context, WorkflowState.SEARCH_PRODUCTS)
