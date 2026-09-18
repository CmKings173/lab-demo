from shared.contracts import CustomerRequirement, Product, ProductType, UsageType, WorkflowState
from adapters.catalog import InMemoryProductRepository
from services.proposal.service import RuleBasedProposalService
from services.sizing.service import DeterministicSizingService
from services.validation.service import RuleBasedConfigurationValidator
from workflow.orchestrator import DeterministicWorkflow


def make_compatible_product() -> Product:
    return Product(
        id="server-1",
        sku="SERVER-1",
        name="Demo 4U AI Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        supported_gpu=["RTX PRO 5000"],
        max_gpu_count=4,
        vram_gb=48,
        default_ram_gb=512,
        max_ram_gb=1024,
        storage_gb=8000,
        storage_slots=8,
        price_vnd=250_000_000,
        product_url="https://example.invalid/server-1",
        datasheet_url="https://example.invalid/server-1.pdf",
    )


def build_workflow(repository: InMemoryProductRepository) -> DeterministicWorkflow:
    return DeterministicWorkflow(
        repository=repository,
        sizing_service=DeterministicSizingService(),
        validator=RuleBasedConfigurationValidator(),
        proposal_service=RuleBasedProposalService(),
    )


def test_minimum_gpu_free_workflow_reaches_completed_with_sources() -> None:
    workflow = build_workflow(InMemoryProductRepository([make_compatible_product()]))
    context = workflow.run(
        CustomerRequirement(
            model_size_b=32,
            usage=UsageType.INFERENCE,
            concurrent_users=5,
            budget_vnd=300_000_000,
        )
    )

    assert context.state == WorkflowState.COMPLETED
    assert context.candidates
    assert context.proposal is not None
    assert context.proposal.sources
    assert not context.proposal.unknown_information


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
