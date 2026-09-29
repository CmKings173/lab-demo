"""Lab 2 product comparison output built only from catalog facts."""

from __future__ import annotations

from shared.contracts import Product, ProductComparison

PRODUCT_COMPARISON_DIMENSIONS = (
    "sku",
    "manufacturer",
    "platform",
    "cpu_model",
    "gpu_vendor",
    "gpu_model",
    "gpu_count",
    "gpu_vram_per_gpu_gb",
    "total_gpu_vram_gb",
    "max_gpu_slots",
    "installed_ram_gb",
    "max_ram_gb",
    "installed_storage_gb",
    "max_storage_gb",
    "storage_slots",
    "power_w",
    "form_factor",
    "base_price_vnd",
    "listed_price_vnd",
    "availability",
    "source_url",
)


def product_comparison_from_catalog(product: Product) -> ProductComparison:
    """Expose catalog values and explicitly mark fields that remain unknown."""

    return ProductComparison(
        product=product,
        unknown_facts=[
            dimension
            for dimension in PRODUCT_COMPARISON_DIMENSIONS
            if getattr(product, dimension) is None
        ],
    )
