from __future__ import annotations

from shared.contracts import (
    CustomerRequirement,
    PriceStatus,
    ProductConfiguration,
    SizingResult,
    ValidationFailure,
    ValidationResult,
    ValidationStatus,
)
from shared.storage import required_storage_target_gb


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
        elif not configuration.selected_gpu.supports(product):
            failures.append(
                ValidationFailure(
                    field="selected_gpu", message="GPU option is incompatible."
                )
            )
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

        required_ram = sizing.recommended_system_ram_gb
        if product.max_ram_gb is None:
            unknown.append("max_ram_gb")
        elif product.max_ram_gb < required_ram:
            failures.append(
                ValidationFailure(
                    field="max_ram_gb",
                    message="Platform cannot meet the RAM requirement.",
                    actual=product.max_ram_gb,
                    required=required_ram,
                )
            )
        else:
            if configuration.selected_ram is None:
                unknown.append("ram_option")
            elif not configuration.selected_ram.supports(product):
                failures.append(
                    ValidationFailure(field="ram_option", message="RAM option is incompatible.")
                )
            if configuration.configured_ram_gb is None:
                unknown.append("configured_ram_gb")
            elif configuration.configured_ram_gb < required_ram:
                failures.append(
                    ValidationFailure(
                        field="configured_ram_gb",
                        message="Configured RAM is below the required capacity.",
                        actual=configuration.configured_ram_gb,
                        required=required_ram,
                    )
                )
            elif configuration.configured_ram_gb > product.max_ram_gb:
                failures.append(
                    ValidationFailure(
                        field="configured_ram_gb",
                        message="Configured RAM exceeds the platform maximum.",
                        actual=configuration.configured_ram_gb,
                        required=product.max_ram_gb,
                    )
                )

        storage_target = required_storage_target_gb(requirement, sizing)
        if (
            configuration.selected_storage is not None
            and not configuration.selected_storage.supports(product)
        ):
            failures.append(
                ValidationFailure(
                    field="storage_option", message="Storage option is incompatible."
                )
            )
        if storage_target is not None and product.max_storage_gb is None:
            unknown.append("max_storage_gb")
        elif storage_target is not None and product.max_storage_gb < storage_target:
            failures.append(
                ValidationFailure(
                    field="max_storage_gb",
                    message="Platform cannot meet the storage requirement.",
                    actual=product.max_storage_gb,
                    required=storage_target,
                )
            )
        elif storage_target is not None:
            if configuration.selected_storage is None:
                unknown.append("storage_option")
            if configuration.configured_storage_gb is None:
                unknown.append("configured_storage_gb")
            elif configuration.configured_storage_gb < storage_target:
                failures.append(
                    ValidationFailure(
                        field="configured_storage_gb",
                        message="Configured storage is below the required capacity.",
                        actual=configuration.configured_storage_gb,
                        required=storage_target,
                    )
                )
            elif configuration.configured_storage_gb > product.max_storage_gb:
                failures.append(
                    ValidationFailure(
                        field="configured_storage_gb",
                        message="Configured storage exceeds the platform capability.",
                        actual=configuration.configured_storage_gb,
                        required=product.max_storage_gb,
                    )
                )

        pricing_consistent = configuration.pricing_state_is_consistent()
        if not pricing_consistent:
            failures.append(
                ValidationFailure(
                    field="price_contract",
                    message="Configuration pricing fields are inconsistent with price_breakdown.",
                )
            )
        if requirement.budget_vnd is not None and pricing_consistent:
            breakdown = configuration.price_breakdown
            if breakdown is None or breakdown.status != PriceStatus.COMPLETE:
                unknown.append("price")
            elif breakdown.total_vnd is None:
                unknown.append("price")
            elif breakdown.total_vnd > requirement.budget_vnd:
                failures.append(
                    ValidationFailure(
                        field="estimated_price_vnd",
                        message="Configuration price exceeds the customer budget.",
                        actual=breakdown.total_vnd,
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
