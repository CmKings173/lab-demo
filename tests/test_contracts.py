from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.contracts import (
    CustomerRequirement,
    Product,
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
        supported_gpu=["RTX PRO 5000"],
        max_gpu_count=4,
        vram_gb=48,
        default_ram_gb=256,
        max_ram_gb=1024,
        storage_gb=4000,
        storage_slots=4,
        power_w=1600,
        form_factor="4U",
        price_vnd=250_000_000,
        availability="in_stock",
        product_url="https://example.invalid/products/p-1",
        datasheet_url="https://example.invalid/products/p-1.pdf",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    product_filter = ProductFilter(
        min_ram_gb=512,
        min_gpu_count=4,
        max_price_vnd=350_000_000,
        product_type=ProductType.AI_SERVER,
    )

    assert Product.model_validate_json(product.model_dump_json()).sku == "SKU-1"
    assert product_filter.model_dump()["min_gpu_count"] == 4
