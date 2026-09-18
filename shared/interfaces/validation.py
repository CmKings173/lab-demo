from typing import Protocol

from shared.contracts import (
    CustomerRequirement,
    ProductConfiguration,
    SizingResult,
    ValidationResult,
)


class ValidationService(Protocol):
    def validate(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        configuration: ProductConfiguration,
    ) -> ValidationResult: ...
