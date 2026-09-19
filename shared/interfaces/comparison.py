from collections.abc import Sequence
from typing import Protocol

from shared.contracts import ComparisonResult, ProductConfiguration


class ComparisonService(Protocol):
    def compare_configurations(
        self, configurations: Sequence[ProductConfiguration]
    ) -> ComparisonResult: ...
