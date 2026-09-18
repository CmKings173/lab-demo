from services.comparison.service import RuleBasedComparisonService
from services.configuration.service import ProductConfigurationBuilder
from services.proposal.service import RuleBasedProposalService
from services.sizing.service import estimate_ai_requirements
from services.validation.service import validate_configuration
from shared.contracts import (
    CustomerRequirement,
    GPUOption,
    Product,
    ProductConfiguration,
    ProductType,
    SizingRequest,
    UsageType,
    ValidationStatus,
)


def make_requirement_and_sizing():
    requirement = CustomerRequirement(
        model_size_b=32,
        usage=UsageType.INFERENCE,
        budget_vnd=300_000_000,
    )
    sizing = estimate_ai_requirements(
        SizingRequest(model_parameters_b=32, usage=UsageType.INFERENCE)
    )
    return requirement, sizing


def make_configuration() -> ProductConfiguration:
    requirement, sizing = make_requirement_and_sizing()
    product = Product(
        id="p-1",
        sku="P-1",
        name="Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        max_gpu_slots=4,
        max_ram_gb=1024,
        max_storage_gb=8000,
        base_price_vnd=100_000_000,
        source_urls=["https://example.invalid/p-1"],
    )
    gpu = GPUOption(
        gpu_id="gpu-96",
        name="GPU 96",
        memory_gb=96,
        supported_product_ids=[product.id],
        price_vnd=50_000_000,
        source_urls=["https://example.invalid/gpu-96"],
    )
    return ProductConfigurationBuilder([gpu]).build([product], sizing, requirement)[0]


def test_sizing_service_is_deterministic_and_explicit_about_assumptions() -> None:
    request = SizingRequest(
        model_parameters_b=32,
        usage=UsageType.INFERENCE,
        context_length=8192,
        concurrent_users=5,
    )

    first = estimate_ai_requirements(request)
    second = estimate_ai_requirements(request)

    assert first == second
    assert first.estimated_model_memory_gb > 0
    assert first.recommended_total_vram_gb >= first.estimated_model_memory_gb
    assert first.assumptions


def test_validation_reports_unknown_configuration_data() -> None:
    requirement, sizing = make_requirement_and_sizing()
    configuration = ProductConfiguration(
        configuration_id="incomplete",
        product=Product(
            id="incomplete",
            sku="INCOMPLETE",
            name="Incomplete Product",
            manufacturer="Demo",
            product_type=ProductType.AI_SERVER,
        ),
    )

    result = validate_configuration(requirement, sizing, configuration)

    assert result.status == ValidationStatus.UNKNOWN
    assert "selected_gpu" in result.unknown_fields
    assert "max_ram_gb" in result.unknown_fields


def test_comparison_service_returns_explicit_dimensions() -> None:
    configuration = make_configuration()

    result = RuleBasedComparisonService().compare([configuration])

    assert result.product_ids == ["p-1"]
    assert result.configuration_ids == [configuration.configuration_id]
    assert "estimated_price_vnd" in result.dimensions


def test_proposal_service_is_repeatable_for_identical_inputs() -> None:
    requirement, sizing = make_requirement_and_sizing()
    configuration = make_configuration()
    comparison = RuleBasedComparisonService().compare([configuration])

    first = RuleBasedProposalService().create(
        requirement, sizing, [configuration], comparison, []
    )
    second = RuleBasedProposalService().create(
        requirement, sizing, [configuration], comparison, []
    )

    assert first == second
