from __future__ import annotations

from shared.contracts import (
    CustomerRequirement,
    Product,
    SizingResult,
    ValidationFailure,
    ValidationResult,
)


class RuleBasedConfigurationValidator:
    def validate(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        product: Product,
    ) -> ValidationResult:
        failures: list[ValidationFailure] = []
        warnings: list[str] = []
        unknown: list[str] = []

        for field in ("max_gpu_count", "vram_gb", "max_ram_gb", "price_vnd"):
            if getattr(product, field) is None:
                unknown.append(field)

        if product.max_gpu_count is not None and product.vram_gb is not None:
            available_vram = product.max_gpu_count * product.vram_gb
            if available_vram < sizing.recommended_vram_gb:
                failures.append(
                    ValidationFailure(
                        field="vram_gb",
                        message="Product does not provide the recommended total VRAM.",
                        actual=available_vram,
                        required=sizing.recommended_vram_gb,
                    )
                )
        if product.max_ram_gb is not None and product.max_ram_gb < sizing.recommended_ram_gb:
            failures.append(
                ValidationFailure(
                    field="max_ram_gb",
                    message="Product maximum RAM is below the recommendation.",
                    actual=product.max_ram_gb,
                    required=sizing.recommended_ram_gb,
                )
            )
        if requirement.budget_vnd is not None and product.price_vnd is not None:
            if product.price_vnd > requirement.budget_vnd:
                failures.append(
                    ValidationFailure(
                        field="price_vnd",
                        message="Product price exceeds the customer budget.",
                        actual=product.price_vnd,
                        required=requirement.budget_vnd,
                    )
                )
        if requirement.storage_requirement_gb is not None:
            if product.storage_gb is None:
                unknown.append("storage_gb")
            elif product.storage_gb < requirement.storage_requirement_gb:
                failures.append(
                    ValidationFailure(
                        field="storage_gb",
                        message="Product storage is below the requirement.",
                        actual=product.storage_gb,
                        required=requirement.storage_requirement_gb,
                    )
                )
        if unknown:
            warnings.append("Final validity cannot be confirmed for unknown product fields.")

        return ValidationResult(
            valid=not failures and not unknown,
            failures=failures,
            warnings=warnings,
            unknown_fields=sorted(set(unknown)),
        )


def validate_configuration(
    requirement: CustomerRequirement,
    sizing: SizingResult,
    product: Product,
) -> ValidationResult:
    return RuleBasedConfigurationValidator().validate(requirement, sizing, product)
