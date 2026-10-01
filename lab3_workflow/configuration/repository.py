from collections.abc import Sequence
from typing import Protocol

from shared.contracts import GPUOption, RAMOption, StorageOption


class ConfigurationOptionRepository(Protocol):
    """Loads explicitly product-compatible options for deterministic builds."""

    def list_gpu_options(self, product_ids: Sequence[str]) -> list[GPUOption]: ...

    def list_ram_options(self, product_ids: Sequence[str]) -> list[RAMOption]: ...

    def list_storage_options(self, product_ids: Sequence[str]) -> list[StorageOption]: ...
