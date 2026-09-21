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
from shared.contracts.models import PriceBreakdown, RAMOption, StorageOption
from shared.storage import required_storage_target_gb


class ProductConfigurationBuilder:
    def __init__(
        self, gpu_options: Iterable[GPUOption],
        ram_options: Iterable[RAMOption] = (),
        storage_options: Iterable[StorageOption] = (),
    ) -> None:
        self.gpu_options = list(gpu_options)
        self.ram_options = list(ram_options)
        self.storage_options = list(storage_options)

    def build(
        self, products: Sequence[Product], sizing: SizingResult,
        requirement: CustomerRequirement,
    ) -> list[ProductConfiguration]:
        configurations = []
        storage_target = required_storage_target_gb(requirement, sizing)
        for product in products:
            ram = min(
                (
                    option
                    for option in self.ram_options
                    if option.supports(product)
                    and option.capacity_gb >= sizing.recommended_system_ram_gb
                    and (product.max_ram_gb is None or option.capacity_gb <= product.max_ram_gb)
                ),
                key=lambda option: (option.capacity_gb, option.option_id), default=None,
            )
            storage = min(
                (
                    option
                    for option in self.storage_options
                    if storage_target is not None
                    and option.supports(product)
                    and option.capacity_gb >= storage_target
                    and (
                        product.max_storage_gb is None
                        or option.capacity_gb <= product.max_storage_gb
                    )
                ),
                key=lambda option: (option.capacity_gb, option.option_id), default=None,
            )
            compatible = [gpu for gpu in self.gpu_options if gpu.supports(product)]
            for gpu in compatible or [None]:
                count = (
                    max(1, math.ceil(sizing.recommended_total_vram_gb / gpu.memory_gb))
                    if gpu
                    else None
                )
                prices = {
                    "base_chassis": product.base_price_vnd,
                    "gpu": gpu.price_vnd * count if gpu and gpu.price_vnd is not None else None,
                    "ram": (
                        0
                        if ram and "ram" in product.base_price_includes
                        else ram.price_vnd if ram else None
                    ),
                    "cpu": 0 if "cpu" in product.base_price_includes else None,
                    "storage": (
                        0
                        if storage and "storage" in product.base_price_includes
                        else storage.price_vnd
                        if storage
                        else 0
                        if storage_target is None
                        and "storage" in product.base_price_includes
                        else None
                    ),
                }
                # A base RAM/storage inclusion does not prove a selected option's price.
                missing = [name for name, price in prices.items() if price is None]
                known = [price for price in prices.values() if price is not None]
                status = (
                    PriceStatus.COMPLETE
                    if not missing
                    else PriceStatus.PARTIAL
                    if known
                    else PriceStatus.UNKNOWN
                )
                breakdown = PriceBreakdown(
                    **{name + "_vnd": value for name, value in prices.items()},
                    total_vnd=sum(known) if known else None,
                    missing_components=missing, status=status,
                )
                option_ids = [
                    option.option_id if option else "unknown" for option in (ram, storage)
                ]
                identity = f"{product.id}:{gpu.gpu_id if gpu else 'unknown-gpu'}:{count}"
                configurations.append(ProductConfiguration(
                    configuration_id=identity + ":" + ":".join(option_ids),
                    product=product, selected_gpu=gpu, gpu_count=count,
                    selected_ram=ram, selected_storage=storage, selected_cpu=None,
                    price_breakdown=breakdown,
                    priced_components=[name for name, value in prices.items() if value is not None],
                    source_urls=sorted(
                        set(
                            product.source_urls
                            + [
                                url
                                for option in (gpu, ram, storage)
                                if option
                                for url in option.source_urls
                            ]
                        )
                    ),
                ))
        return configurations
