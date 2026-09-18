from __future__ import annotations

from shared.contracts import (
    CustomerRequirement,
    ProductConfiguration,
    SizingResult,
    ValidationFailure,
    ValidationResult,
    ValidationStatus,
)


class RuleBasedConfigurationValidator:
    def validate(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        configuration: ProductConfiguration,
    ) -> ValidationResult:
        failures: list[ValidationFailure] = []
        unknown: list[str] = []
        product = configuration.product

        if configuration.selected_gpu is None:
            unknown.append("selected_gpu")
        if configuration.gpu_count is None:
            unknown.append("gpu_count")
        if product.max_gpu_slots is None:
            unknown.append("max_gpu_slots")
        elif (
            configuration.gpu_count is not None
            and configuration.gpu_count > product.max_gpu_slots
        ):
            failures.append(
                ValidationFailure(
                    field="gpu_count",
                    message="Configured GPU count exceeds available platform slots.",
                    actual=configuration.gpu_count,
                    required=product.max_gpu_slots,
                )
            )

        total_vram = configuration.total_vram_gb
        if total_vram is None:
            unknown.append("total_vram_gb")
        elif total_vram < sizing.recommended_total_vram_gb:
            failures.append(
                ValidationFailure(
                    field="total_vram_gb",
                    message="Configuration does not provide the recommended total VRAM.",
                    actual=total_vram,
                    required=sizing.recommended_total_vram_gb,
                )
            )

        if product.max_ram_gb is None:
            unknown.append("max_ram_gb")
        elif configuration.configured_ram_gb is None:
            unknown.append("configured_ram_gb")
        elif configuration.configured_ram_gb > product.max_ram_gb:
            failures.append(
                ValidationFailure(
                    field="configured_ram_gb",
                    message="Configured RAM exceeds the platform maximum.",
                    actual=configuration.configured_ram_gb,
                    required=product.max_ram_gb,
                )
            )

        if product.max_storage_gb is None:
            unknown.append("max_storage_gb")
        elif configuration.configured_storage_gb is None:
            unknown.append("configured_storage_gb")
        elif configuration.configured_storage_gb > product.max_storage_gb:
            failures.append(
                ValidationFailure(
                    field="configured_storage_gb",
                    message="Configured storage exceeds the platform capability.",
                    actual=configuration.configured_storage_gb,
                    required=product.max_storage_gb,
                )
            )

        if requirement.budget_vnd is not None:
            if configuration.estimated_price_vnd is None:
                unknown.append("estimated_price_vnd")
            elif configuration.estimated_price_vnd > requirement.budget_vnd:
                failures.append(
                    ValidationFailure(
                        field="estimated_price_vnd",
                        message="Configuration price exceeds the customer budget.",
                        actual=configuration.estimated_price_vnd,
                        required=requirement.budget_vnd,
                    )
                )

        status = ValidationStatus.PASS
        if failures:
            status = ValidationStatus.FAIL
        elif unknown:
            status = ValidationStatus.UNKNOWN
        warnings = []
        if unknown:
            warnings.append("Final validity cannot be confirmed for unknown configuration fields.")
        return ValidationResult(
            status=status,
            failures=failures,
            warnings=warnings,
            unknown_fields=sorted(set(unknown)),
        )


def validate_configuration(
    requirement: CustomerRequirement,
    sizing: SizingResult,
    configuration: ProductConfiguration,
) -> ValidationResult:
    return RuleBasedConfigurationValidator().validate(requirement, sizing, configuration)
