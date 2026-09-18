from collections.abc import Sequence
from typing import Protocol

from shared.contracts import ComparisonResult, ProductConfiguration


class ComparisonService(Protocol):
    def compare(self, configurations: Sequence[ProductConfiguration]) -> ComparisonResult: ...
