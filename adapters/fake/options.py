"""Explicit fictional options for integration fixtures, never runtime defaults."""
from shared.contracts.models import RAMOption, StorageOption


def ram_options(product_ids: list[str]) -> list[RAMOption]:
    return [RAMOption(option_id=f"ram-{capacity}", capacity_gb=capacity,
                      supported_product_ids=product_ids, price_vnd=20_000_000,
                      source_urls=[f"https://example.invalid/ram-{capacity}"])
            for capacity in (128, 256, 512)]


def storage_options(product_ids: list[str]) -> list[StorageOption]:
    return [StorageOption(option_id=f"storage-{capacity}", capacity_gb=capacity,
                          supported_product_ids=product_ids, price_vnd=10_000_000,
                          source_urls=[f"https://example.invalid/storage-{capacity}"])
            for capacity in (1000, 2000)]
