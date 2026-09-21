from shared.contracts import CustomerRequirement, SizingResult


def required_storage_target_gb(
    requirement: CustomerRequirement, sizing: SizingResult,
) -> int | None:
    values = [value for value in (
        requirement.storage_requirement_gb, sizing.recommended_storage_gb,
    ) if value is not None]
    return max(values) if values else None
