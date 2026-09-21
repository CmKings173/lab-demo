from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.contracts import (
    CustomerRequirement,
    PriceBreakdown,
    PriceStatus,
    Product,
    ProductConfiguration,
    ProductFilter,
    ProductType,
    UsageType,
)


def test_customer_requirement_accepts_partial_input_for_missing_information_flow() -> None:
    requirement = CustomerRequirement(model_size_b=32, usage=UsageType.INFERENCE)

    assert requirement.budget_vnd is None
    assert requirement.missing_required_fields() == ["budget_vnd"]


def test_customer_requirement_rejects_invalid_positive_constraints() -> None:
    with pytest.raises(ValidationError):
        CustomerRequirement(model_size_b=0, usage=UsageType.INFERENCE)


def test_product_and_filter_are_json_serializable() -> None:
    product = Product(
        id="p-1",
        sku="SKU-1",
        name="Demo Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
        cpu_options=["2x CPU"],
        max_gpu_slots=4,
        max_ram_gb=1024,
        max_storage_gb=4000,
        storage_slots=4,
        power_w=1600,
        form_factor="4U",
        base_price_vnd=250_000_000,
        availability="in_stock",
        source_urls=[
            "https://example.invalid/products/p-1",
            "https://example.invalid/products/p-1.pdf",
        ],
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    product_filter = ProductFilter(
        min_ram_gb=512,
        min_gpu_count=4,
        max_base_price_vnd=350_000_000,
        product_type=ProductType.AI_SERVER,
    )

    assert Product.model_validate_json(product.model_dump_json()).sku == "SKU-1"
    assert product_filter.model_dump()["min_gpu_count"] == 4


def test_complete_price_requires_every_component_and_consistent_missing_fields() -> None:
    with pytest.raises(ValidationError, match="COMPLETE price requires all components"):
        PriceBreakdown(
            base_chassis_vnd=100,
            gpu_vnd=None,
            ram_vnd=20,
            storage_vnd=30,
            cpu_vnd=0,
            total_vnd=150,
            missing_components=[],
            status=PriceStatus.COMPLETE,
        )


def test_price_status_must_match_actual_component_completeness() -> None:
    with pytest.raises(ValidationError, match="missing_components must match"):
        PriceBreakdown(
            base_chassis_vnd=100,
            gpu_vnd=None,
            ram_vnd=20,
            storage_vnd=30,
            cpu_vnd=0,
            total_vnd=150,
            missing_components=[],
            status=PriceStatus.PARTIAL,
        )


def test_unknown_price_breakdown_default_declares_all_components_missing() -> None:
    breakdown = PriceBreakdown()

    assert breakdown.status == PriceStatus.UNKNOWN
    assert breakdown.total_vnd is None
    assert breakdown.missing_components == ["base_chassis", "gpu", "ram", "storage", "cpu"]


def test_product_configuration_derives_priced_components_from_breakdown() -> None:
    product = Product(
        id="p-1",
        sku="P-1",
        name="Demo Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
    )
    breakdown = PriceBreakdown(
        base_chassis_vnd=100,
        gpu_vnd=200,
        ram_vnd=None,
        storage_vnd=None,
        cpu_vnd=0,
        total_vnd=300,
        missing_components=["ram", "storage"],
        status=PriceStatus.PARTIAL,
    )

    configuration = ProductConfiguration(
        configuration_id="cfg-1",
        product=product,
        price_breakdown=breakdown,
        priced_components=["forged"],
    )

    assert configuration.priced_components == ["base_chassis", "gpu", "cpu"]


def test_product_configuration_pricing_requires_breakdown() -> None:
    product = Product(
        id="p-1",
        sku="P-1",
        name="Demo Server",
        manufacturer="Demo",
        product_type=ProductType.AI_SERVER,
    )

    with pytest.raises(ValidationError, match="Pricing fields require price_breakdown"):
        ProductConfiguration(
            configuration_id="cfg-1",
            product=product,
            estimated_price_vnd=123,
            price_status=PriceStatus.COMPLETE,
        )
