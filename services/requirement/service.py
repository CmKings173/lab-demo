from shared.contracts import CustomerRequirement, MissingInformation


class RequirementAnalyzer:
    def analyze(self, requirement: CustomerRequirement) -> MissingInformation | None:
        missing = requirement.missing_required_fields()
        if not missing:
            return None
        labels = ", ".join(missing)
        return MissingInformation(
            missing_fields=missing,
            question=f"Please provide the required information: {labels}.",
        )
