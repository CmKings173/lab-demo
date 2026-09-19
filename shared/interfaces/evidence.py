from collections.abc import Sequence
from typing import Protocol

from shared.contracts import DocumentHit, ProductConfiguration, ResolvedProductFact


class ProductFactResolver(Protocol):
    def resolve(
        self,
        configuration: ProductConfiguration,
        unknown_fields: Sequence[str],
        hits: Sequence[DocumentHit],
    ) -> list[ResolvedProductFact]: ...

    def apply(
        self,
        configuration: ProductConfiguration,
        facts: Sequence[ResolvedProductFact],
    ) -> ProductConfiguration: ...
