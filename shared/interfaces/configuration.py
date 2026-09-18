from collections.abc import Sequence
from typing import Protocol

from shared.contracts import CustomerRequirement, Product, ProductConfiguration, SizingResult


class ConfigurationBuilder(Protocol):
    def build(
        self,
        products: Sequence[Product],
        sizing: SizingResult,
        requirement: CustomerRequirement,
    ) -> list[ProductConfiguration]: ...
