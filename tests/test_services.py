from shared.contracts import (
    CustomerRequirement,
    Product,
    ProductType,
    SizingRequest,
    UsageType,
)
from services.sizing.service import estimate_ai_requirements
from services.validation.service import validate_configuration


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
    assert first.estimated_vram_gb > 0
    assert first.recommended_vram_gb >= first.estimated_vram_gb
    assert first.assumptions


def test_validation_is_code_driven_and_reports_unknown_product_data() -> None:
    requirement = CustomerRequirement(
        model_size_b=32,
        usage=UsageType.INFERENCE,
        budget_vnd=300_000_000,
    )
    sizing = estimate_ai_requirements(
        SizingRequest(model_parameters_b=32, usage=UsageType.INFERENCE)
    )
    product = Product(
        id="incomplete",
        sku="INCOMPLETE",
        name="Incomplete Product",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        price_vnd=200_000_000,
    )

    result = validate_configuration(requirement, sizing, product)

    assert not result.valid
    assert "max_gpu_count" in result.unknown_fields
    assert "vram_gb" in result.unknown_fields
