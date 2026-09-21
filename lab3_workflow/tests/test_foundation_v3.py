from adapters.fake.options import ram_options
from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab2_rag_agent.retrieval.documents import FakeDocumentSearch
from lab3_workflow.comparison.service import RuleBasedComparisonService
from lab3_workflow.configuration.service import ProductConfigurationBuilder
from lab3_workflow.evidence.service import DeterministicProductFactResolver
from lab3_workflow.proposal.service import RuleBasedProposalService, RuleBasedProposalVerifier
from lab3_workflow.sizing.service import DeterministicSizingService, estimate_ai_requirements
from lab3_workflow.validation.service import RuleBasedConfigurationValidator
from lab3_workflow.workflow.orchestrator import DeterministicWorkflow
from shared.contracts import (
    CustomerRequirement,
    DocumentChunk,
    GPUOption,
    PriceStatus,
    Product,
    ProductType,
    SizingRequest,
    UsageType,
    ValidationStatus,
    WorkflowState,
)


def product(*, max_ram_gb: int | None = 512) -> Product:
    return Product(
        id="p-1",
        sku="P-1",
        name="Máy chủ AI",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        cpu_options=["CPU-A", "CPU-B"],
        max_ram_gb=max_ram_gb,
        max_gpu_slots=4,
        max_storage_gb=8000,
        base_price_vnd=100_000_000,
        source_urls=["https://example.invalid/p-1"],
    )


def gpu() -> GPUOption:
    return GPUOption(
        gpu_id="g-96",
        name="GPU 96GB",
        memory_gb=96,
        supported_product_ids=["p-1"],
        price_vnd=50_000_000,
        source_urls=["https://example.invalid/g-96"],
    )


def requirement() -> CustomerRequirement:
    return CustomerRequirement(
        model_size_b=14,
        usage=UsageType.INFERENCE,
        budget_vnd=300_000_000,
    )


def sizing():
    return estimate_ai_requirements(
        SizingRequest(model_parameters_b=14, usage=UsageType.INFERENCE)
    )


def test_builder_does_not_invent_storage_or_cpu_and_marks_partial_price() -> None:
    configuration = ProductConfigurationBuilder([gpu()]).build(
        [product()], sizing(), requirement()
    )[0]

    assert configuration.configured_storage_gb is None
    assert configuration.selected_cpu is None
    assert configuration.price_status == PriceStatus.PARTIAL
    assert {"base_chassis", "gpu"} <= set(configuration.priced_components)
    assert {"ram", "cpu"} <= set(configuration.missing_price_components)
    assert "storage" in configuration.missing_price_components


def test_partial_price_makes_budget_validation_unknown() -> None:
    configuration = ProductConfigurationBuilder([gpu()]).build(
        [product()], sizing(), requirement()
    )[0]

    result = RuleBasedConfigurationValidator().validate(
        requirement(), sizing(), configuration
    )

    assert result.status == ValidationStatus.UNKNOWN
    assert "price" in result.unknown_fields


def test_complete_price_can_pass_or_fail_budget() -> None:
    configuration = ProductConfigurationBuilder([gpu()], ram_options(["p-1"])).build(
        [
            product().model_copy(
                update={"base_price_includes": {"chassis", "cpu", "storage"}}
            )
        ],
        sizing(), requirement(),
    )[0]
    validator = RuleBasedConfigurationValidator()

    assert (
        validator.validate(requirement(), sizing(), configuration).status
        == ValidationStatus.PASS
    )
    over_budget = configuration.model_copy(update={"estimated_price_vnd": 400_000_000})
    assert validator.validate(requirement(), sizing(), over_budget).status == ValidationStatus.FAIL


def test_unknown_fact_is_resolved_from_verified_document_then_revalidated() -> None:
    chunk = DocumentChunk(
        id="doc-1",
        product_id="p-1",
        source_url="https://example.invalid/datasheet",
        page=14,
        text="Máy chủ hỗ trợ tối đa 512GB RAM.",
        metadata={"field_name": "max_ram_gb", "value": "512", "verified": "true"},
    )
    workflow = DeterministicWorkflow(
        repository=InMemoryProductRepository([product(max_ram_gb=None)]),
        sizing_service=DeterministicSizingService(),
        configuration_builder=ProductConfigurationBuilder([gpu()]),
        validator=RuleBasedConfigurationValidator(),
        document_search=FakeDocumentSearch([chunk]),
        fact_resolver=DeterministicProductFactResolver(),
        comparison_service=RuleBasedComparisonService(),
        proposal_service=RuleBasedProposalService(),
        proposal_verifier=RuleBasedProposalVerifier(),
    )

    context = workflow.run(requirement())

    assert WorkflowState.APPLY_VERIFIED_FACTS in context.history
    assert WorkflowState.REVALIDATE in context.history
    assert context.resolved_facts[0].field_name == "max_ram_gb"
    assert context.configurations[0].product.max_ram_gb == 512


def test_unresolved_fact_finishes_as_insufficient_product_data() -> None:
    workflow = DeterministicWorkflow(
        repository=InMemoryProductRepository([product(max_ram_gb=None)]),
        sizing_service=DeterministicSizingService(),
        configuration_builder=ProductConfigurationBuilder([gpu()]),
        validator=RuleBasedConfigurationValidator(),
        document_search=FakeDocumentSearch([]),
        fact_resolver=DeterministicProductFactResolver(),
        comparison_service=RuleBasedComparisonService(),
        proposal_service=RuleBasedProposalService(),
        proposal_verifier=RuleBasedProposalVerifier(),
    )

    context = workflow.run(requirement())

    assert context.state == WorkflowState.INSUFFICIENT_PRODUCT_DATA


def test_comparison_contains_real_configuration_values() -> None:
    configuration = ProductConfigurationBuilder([gpu()]).build(
        [product()], sizing(), requirement()
    )[0]

    result = RuleBasedComparisonService().compare_configurations([configuration])

    row = result.configurations[0]
    assert row.configuration_id == configuration.configuration_id
    assert row.gpu_model == "GPU 96GB"
    assert row.gpu_count == 1
    assert row.total_vram_gb == 96
    assert row.price_status == PriceStatus.PARTIAL


def test_verifier_rejects_evidence_with_wrong_product_or_value() -> None:
    configuration = ProductConfigurationBuilder([gpu()]).build(
        [product()], sizing(), requirement()
    )[0].model_copy(
        update={
            "price_status": PriceStatus.COMPLETE,
            "missing_price_components": [],
            "configured_storage_gb": 1000,
        }
    )
    comparison = RuleBasedComparisonService().compare_configurations([configuration])
    hits = FakeDocumentSearch(
        [
            DocumentChunk(
                id="doc-vram",
                product_id="p-1",
                source_url="https://example.invalid/gpu-doc",
                page=2,
                text="Tổng VRAM cấu hình là 96GB.",
                metadata={"field_name": "total_vram_gb", "value": "96", "verified": "true"},
            ),
            DocumentChunk(
                id="doc-ram",
                product_id="p-1",
                source_url="https://example.invalid/ram-doc",
                page=14,
                text="Cấu hình dùng 128GB RAM.",
                metadata={
                    "field_name": "configured_ram_gb",
                    "value": str(configuration.configured_ram_gb),
                    "verified": "true",
                },
            ),
        ]
    ).search
    document_hits = hits(
        __import__("shared.contracts", fromlist=["DocumentSearchRequest"]).DocumentSearchRequest(
            query="VRAM RAM configured_ram_gb", product_id="p-1"
        )
    ).hits
    proposal = RuleBasedProposalService().create(
        requirement(), sizing(), [configuration], comparison, document_hits
    )

    proposal.evidence[0].product_id = "wrong-product"
    proposal.evidence[0].value = -1
    result = RuleBasedProposalVerifier().verify(proposal)

    assert result.valid is False
    assert any("wrong product" in error.lower() for error in result.errors)
    assert any("value mismatch" in error.lower() for error in result.errors)
