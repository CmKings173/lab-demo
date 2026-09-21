from adapters.fake.evidence import option_documents
from adapters.fake.options import ram_options, storage_options
from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab2_rag_agent.retrieval.documents import FakeDocumentSearch
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.configuration.service import ProductConfigurationBuilder
from lab3_workflow.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from lab3_workflow.sizing.service import DeterministicSizingService, estimate_ai_requirements
from lab3_workflow.validation.service import RuleBasedConfigurationValidator
from lab3_workflow.workflow.orchestrator import DeterministicWorkflow
from shared.contracts import (
    CustomerRequirement,
    DocumentChunk,
    DocumentSearchRequest,
    GPUOption,
    Product,
    ProductConfiguration,
    ProductType,
    SizingRequest,
    UsageType,
    ValidationStatus,
    WorkflowState,
)


def make_product(product_id: str, *, ram: int | None = 1024) -> Product:
    return Product(
        id=product_id,
        sku=product_id.upper(),
        name=f"Server {product_id}",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_ram_gb=ram,
        max_gpu_slots=4,
        max_storage_gb=8000,
        base_price_vnd=100_000_000,
        base_price_includes={"chassis", "cpu", "storage"},
        source_urls=[f"https://example.invalid/{product_id}"],
    )


def make_gpu(product_ids: list[str], memory_gb: int = 96) -> GPUOption:
    return GPUOption(
        gpu_id=f"gpu-{memory_gb}",
        name=f"GPU {memory_gb}",
        memory_gb=memory_gb,
        supported_product_ids=product_ids,
        price_vnd=50_000_000,
        source_urls=[f"https://example.invalid/gpu-{memory_gb}"],
    )


def requirement() -> CustomerRequirement:
    return CustomerRequirement(
        model_size_b=20,
        usage=UsageType.INFERENCE,
        budget_vnd=500_000_000,
        storage_requirement_gb=1000,
    )


def test_96gb_gpu_can_satisfy_vram_without_a_48gb_assumption() -> None:
    sizing = estimate_ai_requirements(
        SizingRequest(model_parameters_b=20, usage=UsageType.INFERENCE)
    )
    product = make_product("p-1")
    configurations = ProductConfigurationBuilder([make_gpu([product.id])]).build(
        [product], sizing, requirement()
    )

    assert configurations[0].gpu_count == 1
    assert configurations[0].total_vram_gb == 96


def test_validation_distinguishes_pass_fail_and_unknown() -> None:
    sizing = estimate_ai_requirements(
        SizingRequest(model_parameters_b=20, usage=UsageType.INFERENCE)
    )
    validator = RuleBasedConfigurationValidator()
    passing = ProductConfigurationBuilder(
        [make_gpu(["pass"])], ram_options(["pass"]), storage_options(["pass"])
    ).build(
        [make_product("pass")], sizing, requirement()
    )[0]
    failing = passing.model_copy(
        update={"configured_ram_gb": 2048, "configuration_id": "fail"}
    )
    unknown = ProductConfiguration(
        configuration_id="unknown",
        product=make_product("unknown", ram=None),
        configured_storage_gb=1000,
    )

    assert validator.validate(requirement(), sizing, passing).status == ValidationStatus.PASS
    assert validator.validate(requirement(), sizing, failing).status == ValidationStatus.FAIL
    unknown_result = validator.validate(requirement(), sizing, unknown)
    assert unknown_result.status == ValidationStatus.UNKNOWN
    assert "selected_gpu" in unknown_result.unknown_fields


def build_workflow(
    products: list[Product],
    gpu_options: list[GPUOption],
    chunks: list[DocumentChunk],
):
    return DeterministicWorkflow(
        repository=InMemoryProductRepository(products),
        sizing_service=DeterministicSizingService(),
        configuration_builder=ProductConfigurationBuilder(
            gpu_options,
            ram_options([product.id for product in products]),
            storage_options([product.id for product in products]),
        ),
        validator=RuleBasedConfigurationValidator(),
        document_search=FakeDocumentSearch(chunks),
        comparison_service=RuleBasedComparisonService(),
        proposal_service=RuleBasedProposalService(),
        proposal_verifier=RuleBasedProposalVerifier(),
    )


def test_workflow_calls_document_search_and_builds_option_a_and_b() -> None:
    products = [make_product("p-1"), make_product("p-2")]
    gpu = make_gpu([product.id for product in products])
    workflow = build_workflow(
        products,
        [gpu],
        [chunk for product in products for chunk in option_documents(product, gpu, 256)],
    )

    context = workflow.run(requirement())

    assert context.state == WorkflowState.COMPLETE
    assert WorkflowState.READ_DOCUMENTS in context.history
    assert context.document_hits
    assert [option.name for option in context.proposal.options] == ["Option A", "Option B"]
    assert context.comparison is not None


def test_complete_workflow_does_not_require_storage_when_customer_and_sizing_do_not() -> None:
    products = [make_product("p-1")]
    gpu = make_gpu(["p-1"])
    workflow = build_workflow(products, [gpu], option_documents(products[0], gpu, 256))
    no_storage_requirement = CustomerRequirement(
        model_size_b=20,
        usage=UsageType.INFERENCE,
        budget_vnd=500_000_000,
    )

    context = workflow.run(no_storage_requirement)

    assert context.state == WorkflowState.COMPLETE
    assert context.configurations[0].selected_storage is None
    assert context.configurations[0].configured_storage_gb is None
    assert "configured_storage_gb" not in context.validation_results[
        context.configurations[0].configuration_id
    ].unknown_fields


def test_partial_price_remains_unknown_and_is_not_sent_to_fact_resolver() -> None:
    product = make_product("p-1").model_copy(update={"base_price_includes": {"chassis"}})
    gpu = make_gpu(["p-1"])
    workflow = build_workflow([product], [gpu], option_documents(product, gpu, 256))

    context = workflow.run(requirement())

    assert context.state == WorkflowState.INSUFFICIENT_PRODUCT_DATA
    assert all(fact.field_name != "price" for fact in context.resolved_facts)
    result = context.validation_results[context.configurations[0].configuration_id]
    assert "price" in result.unknown_fields


def test_unknown_only_candidates_stop_as_insufficient_product_data() -> None:
    workflow = build_workflow([make_product("unknown", ram=None)], [], [])

    context = workflow.run(requirement())

    assert context.state == WorkflowState.INSUFFICIENT_PRODUCT_DATA


def test_missing_information_is_stateless_and_never_searches_catalog() -> None:
    class CountingRepository(InMemoryProductRepository):
        searches = 0

        def search(self, request):
            self.searches += 1
            return super().search(request)

    repository = CountingRepository([make_product("p-1")])
    workflow = DeterministicWorkflow(
        repository=repository,
        sizing_service=DeterministicSizingService(),
        configuration_builder=ProductConfigurationBuilder([]),
        validator=RuleBasedConfigurationValidator(),
        document_search=FakeDocumentSearch([]),
        comparison_service=RuleBasedComparisonService(),
        proposal_service=RuleBasedProposalService(),
        proposal_verifier=RuleBasedProposalVerifier(),
    )

    context = workflow.run(CustomerRequirement(model_size_b=20, usage=UsageType.INFERENCE))

    assert context.state == WorkflowState.MISSING_INFORMATION
    assert context.missing_information is not None
    assert context.missing_information.question
    assert repository.searches == 0


def test_proposal_verifier_rejects_unsupported_claims() -> None:
    sizing = estimate_ai_requirements(
        SizingRequest(model_parameters_b=20, usage=UsageType.INFERENCE)
    )
    configuration = ProductConfigurationBuilder([make_gpu(["p-1"])]).build(
        [make_product("p-1")], sizing, requirement()
    )[0]
    comparison = RuleBasedComparisonService().compare_configurations([configuration])
    proposal = RuleBasedProposalService().create(
        requirement(), sizing, [configuration], comparison, []
    )
    proposal.technical_claims["unsupported_claim"] = "not in evidence"

    result = RuleBasedProposalVerifier().verify(proposal)

    assert result.valid is False
    assert any("unsupported_claim" in error for error in result.errors)


def test_proposal_evidence_requires_field_specific_document_facts() -> None:
    sizing = estimate_ai_requirements(
        SizingRequest(model_parameters_b=20, usage=UsageType.INFERENCE)
    )
    configuration = ProductConfigurationBuilder([make_gpu(["p-1"])]).build(
        [make_product("p-1")], sizing, requirement()
    )[0]
    comparison = RuleBasedComparisonService().compare_configurations([configuration])

    hits = FakeDocumentSearch(
        [
            DocumentChunk(
                id="gpu-evidence",
                text="VRAM được xác minh",
                product_id="p-1",
                source_url="https://example.invalid/gpu-96",
                metadata={"field_name": "total_vram_gb", "value": "96", "verified": "true"},
            ),
            DocumentChunk(
                id="ram-evidence",
                text="RAM được xác minh",
                product_id="p-1",
                source_url="https://example.invalid/p-1",
                metadata={
                    "field_name": "configured_ram_gb",
                    "value": str(configuration.configured_ram_gb),
                    "verified": "true",
                },
            ),
        ]
    ).search(DocumentSearchRequest(query="VRAM RAM", product_id="p-1")).hits
    proposal = RuleBasedProposalService().create(
        requirement(), sizing, [configuration], comparison, hits
    )

    evidence = {item.claim.rsplit(".", 1)[-1]: item for item in proposal.evidence}
    assert evidence["total_vram_gb"].source_url is None
    assert evidence["total_vram_gb"].kind == "derived"
    assert not RuleBasedProposalVerifier().verify(proposal).valid


def test_proposal_verifier_rejects_undersized_ram_and_storage() -> None:
    sizing = estimate_ai_requirements(
        SizingRequest(model_parameters_b=20, usage=UsageType.INFERENCE)
    )
    configuration = ProductConfigurationBuilder([make_gpu(["p-1"])]).build(
        [make_product("p-1")], sizing, requirement()
    )[0]
    configuration.configured_ram_gb = sizing.recommended_system_ram_gb - 1
    if sizing.recommended_storage_gb is not None:
        configuration.configured_storage_gb = sizing.recommended_storage_gb - 1
    comparison = RuleBasedComparisonService().compare_configurations([configuration])
    proposal = RuleBasedProposalService().create(
        requirement(), sizing, [configuration], comparison, []
    )

    result = RuleBasedProposalVerifier().verify(proposal)

    assert result.valid is False
    assert any("RAM sizing" in error for error in result.errors)
    if sizing.recommended_storage_gb is not None:
        assert any("storage sizing" in error for error in result.errors)
