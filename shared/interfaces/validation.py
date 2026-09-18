from typing import Protocol

from shared.contracts import (
    CustomerRequirement,
    Product,
    SizingResult,
    ValidationResult,
)


class ValidationService(Protocol):
    def validate(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        product: Product,
    ) -> ValidationResult: ...
