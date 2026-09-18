from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from shared.contracts import (
    CustomerRequirement,
    GPUOption,
    Product,
    ProductConfiguration,
    SizingResult,
)


class ProductConfigurationBuilder:
    def __init__(self, gpu_options: Iterable[GPUOption]) -> None:
        self.gpu_options = list(gpu_options)

    def build(
        self,
        products: Sequence[Product],
        sizing: SizingResult,
        requirement: CustomerRequirement,
    ) -> list[ProductConfiguration]:
        configurations: list[ProductConfiguration] = []
        for product in products:
            compatible = [gpu for gpu in self.gpu_options if gpu.supports(product)]
            if not compatible:
                configurations.append(self._unknown_gpu_configuration(product, sizing, requirement))
                continue
            for gpu in compatible:
                gpu_count = max(1, math.ceil(sizing.recommended_total_vram_gb / gpu.memory_gb))
                estimated_price = None
                if product.base_price_vnd is not None and gpu.price_vnd is not None:
                    estimated_price = product.base_price_vnd + gpu.price_vnd * gpu_count
                configurations.append(
                    ProductConfiguration(
                        configuration_id=f"{product.id}:{gpu.gpu_id}:{gpu_count}",
                        product=product,
                        selected_gpu=gpu,
                        gpu_count=gpu_count,
                        configured_ram_gb=sizing.recommended_system_ram_gb,
                        configured_storage_gb=(
                            requirement.storage_requirement_gb
                            or sizing.recommended_storage_gb
                            or 1000
                        ),
                        selected_cpu=product.cpu_options[0] if product.cpu_options else None,
                        estimated_price_vnd=estimated_price,
                        source_urls=sorted(set(product.source_urls + gpu.source_urls)),
                    )
                )
        return configurations

    @staticmethod
    def _unknown_gpu_configuration(
        product: Product,
        sizing: SizingResult,
        requirement: CustomerRequirement,
    ) -> ProductConfiguration:
        return ProductConfiguration(
            configuration_id=f"{product.id}:unknown-gpu",
            product=product,
            configured_ram_gb=sizing.recommended_system_ram_gb,
            configured_storage_gb=(
                requirement.storage_requirement_gb or sizing.recommended_storage_gb or 1000
            ),
            selected_cpu=product.cpu_options[0] if product.cpu_options else None,
            source_urls=list(product.source_urls),
        )
