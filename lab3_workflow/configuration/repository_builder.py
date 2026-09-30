from __future__ import annotations

from collections.abc import Sequence

from shared.contracts import (
    CustomerRequirement,
    Product,
    ProductConfiguration,
    SizingResult,
)

from .repository import ConfigurationOptionRepository
from .service import ProductConfigurationBuilder


class RepositoryBackedProductConfigurationBuilder:
    """Loads fresh options for candidate products, then delegates deterministic selection."""

    def __init__(self, repository: ConfigurationOptionRepository) -> None:
        self._repository = repository

    def build(
        self,
        products: Sequence[Product],
        sizing: SizingResult,
        requirement: CustomerRequirement,
    ) -> list[ProductConfiguration]:
        if not products:
            return []
        product_ids = list(dict.fromkeys(product.id for product in products))
        builder = ProductConfigurationBuilder(
            gpu_options=self._repository.list_gpu_options(product_ids),
            ram_options=self._repository.list_ram_options(product_ids),
            storage_options=self._repository.list_storage_options(product_ids),
        )
        return builder.build(products, sizing, requirement)
