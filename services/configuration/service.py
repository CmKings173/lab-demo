from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from shared.contracts import (
    CustomerRequirement,
    GPUOption,
    PriceStatus,
    Product,
    ProductConfiguration,
    SizingResult,
)


class ProductConfigurationBuilder:
    def __init__(
        self,
        gpu_options: Iterable[GPUOption],
        component_prices_vnd: dict[str, dict[str, int]] | None = None,
    ) -> None:
        self.gpu_options = list(gpu_options)
        self.component_prices_vnd = component_prices_vnd or {}

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
                estimated_price = 0
                priced_components: list[str] = []
                missing_price_components: list[str] = []
                component_prices = self.component_prices_vnd.get(product.id, {})
                if product.base_price_vnd is None:
                    missing_price_components.append("base_chassis")
                else:
                    estimated_price += product.base_price_vnd
                    priced_components.append("base_chassis")
                if gpu.price_vnd is None:
                    missing_price_components.append("gpu")
                else:
                    estimated_price += gpu.price_vnd * gpu_count
                    priced_components.append("gpu")
                for component in ("ram", "storage"):
                    if component in component_prices:
                        estimated_price += component_prices[component]
                        priced_components.append(component)
                    else:
                        missing_price_components.append(component)
                price_status = (
                    PriceStatus.COMPLETE
                    if not missing_price_components
                    else PriceStatus.PARTIAL
                    if priced_components
                    else PriceStatus.UNKNOWN
                )
                configurations.append(
                    ProductConfiguration(
                        configuration_id=f"{product.id}:{gpu.gpu_id}:{gpu_count}",
                        product=product,
                        selected_gpu=gpu,
                        gpu_count=gpu_count,
                        configured_ram_gb=sizing.recommended_system_ram_gb,
                        configured_storage_gb=(
                            requirement.storage_requirement_gb or sizing.recommended_storage_gb
                        ),
                        selected_cpu=None,
                        estimated_price_vnd=(estimated_price if priced_components else None),
                        price_status=price_status,
                        priced_components=priced_components,
                        missing_price_components=sorted(set(missing_price_components)),
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
                requirement.storage_requirement_gb or sizing.recommended_storage_gb
            ),
            selected_cpu=None,
            price_status=PriceStatus.UNKNOWN,
            missing_price_components=["base_chassis", "gpu", "ram", "storage"],
            source_urls=list(product.source_urls),
        )
