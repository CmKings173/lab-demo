from __future__ import annotations

from lab3_workflow.proposal.evidence import build_evidence, verify_derived
from shared.contracts import (
    ComparisonResult,
    CustomerRequirement,
    DocumentHit,
    PriceStatus,
    ProductConfiguration,
    Proposal,
    ProposalOption,
    ProposalVerificationResult,
    SizingResult,
)
from shared.contracts.models import EvidenceKind
from shared.storage import required_storage_target_gb


class RuleBasedProposalService:
    def create(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        configurations: list[ProductConfiguration],
        comparison: ComparisonResult,
        document_hits: list[DocumentHit],
    ) -> Proposal:
        selected = configurations[:2]
        evidence = build_evidence(selected, document_hits)
        options = [
            ProposalOption(
                name=f"Option {chr(ord('A') + index)}",
                configuration=configuration,
                rationale="Rule-valid configuration supported by catalog and document evidence.",
                estimated_price_vnd=configuration.estimated_price_vnd,
                limitations=list(sizing.warnings),
                evidence=[item for item in evidence if item.product_id == configuration.product.id],
            )
            for index, configuration in enumerate(selected)
        ]
        sources = sorted({item.source_url for item in evidence if item.source_url})
        technical_claims = {
            f"{configuration.configuration_id}.total_vram_gb": configuration.total_vram_gb
            for configuration in selected
        }
        technical_claims.update(
            {
                f"{configuration.configuration_id}.configured_ram_gb": (
                    configuration.configured_ram_gb
                )
                for configuration in selected
            }
        )
        return Proposal(
            customer_requirement=requirement,
            interpreted_workload=f"{requirement.usage} for a {requirement.model_size_b:g}B model.",
            sizing_result=sizing,
            selected_configurations=selected,
            options=options,
            comparison=comparison,
            technical_claims=technical_claims,
            evidence=evidence,
            technical_reasoning=[
                "Sizing was produced by deterministic rules.",
                "Configurations passed code-driven validation before proposal generation.",
            ],
            limitations=list(sizing.warnings),
            unknown_information=[],
            sources=sources,
            estimated_price_vnd=(selected[0].estimated_price_vnd if selected else None),
        )


class RuleBasedProposalVerifier:
    def verify(self, proposal: Proposal) -> ProposalVerificationResult:
        errors: list[str] = []
        evidence_by_claim = {item.claim: item for item in proposal.evidence}
        configuration_ids = {
            configuration.configuration_id for configuration in proposal.selected_configurations
        }
        for option in proposal.options:
            if option.configuration.configuration_id not in configuration_ids:
                errors.append(f"Unknown configuration: {option.configuration.configuration_id}")
        for claim, value in proposal.technical_claims.items():
            item = evidence_by_claim.get(claim)
            if item is None:
                errors.append(f"Unsupported claim: {claim}")
                continue
            configuration_id = claim.rsplit(".", 1)[0]
            configuration = next(
                (
                    candidate
                    for candidate in proposal.selected_configurations
                    if candidate.configuration_id == configuration_id
                ),
                None,
            )
            if item.value != value:
                errors.append(f"Evidence value mismatch: {claim}")
            if configuration is None or item.product_id != configuration.product.id:
                errors.append(f"Evidence has wrong product: {claim}")
            if item.kind == EvidenceKind.DERIVED:
                if configuration is None or not verify_derived(
                    item, configuration, proposal.evidence
                ):
                    errors.append(f"Invalid derivation: {claim}")
            else:
                if not item.verified:
                    errors.append(f"Unverified evidence: {claim}")
                if item.document_id is None:
                    errors.append(f"Evidence lacks document linkage: {claim}")
        for configuration in proposal.selected_configurations:
            if configuration.total_vram_gb is None:
                errors.append(f"Configuration {configuration.configuration_id} has unknown VRAM")
            elif configuration.total_vram_gb < proposal.sizing_result.recommended_total_vram_gb:
                errors.append(
                    f"Configuration {configuration.configuration_id} does not meet sizing"
                )
            if configuration.configured_ram_gb is None:
                errors.append(f"Configuration {configuration.configuration_id} has unknown RAM")
            elif (
                configuration.configured_ram_gb
                < proposal.sizing_result.recommended_system_ram_gb
            ):
                errors.append(
                    f"Configuration {configuration.configuration_id} does not meet RAM sizing"
                )
            recommended_storage = required_storage_target_gb(
                proposal.customer_requirement, proposal.sizing_result,
            )
            if recommended_storage is not None:
                if configuration.configured_storage_gb is None:
                    errors.append(
                        f"Configuration {configuration.configuration_id} has unknown storage"
                    )
                elif configuration.configured_storage_gb < recommended_storage:
                    errors.append(
                        "Configuration "
                        f"{configuration.configuration_id} does not meet storage sizing"
                    )
            budget = proposal.customer_requirement.budget_vnd
            if budget is not None:
                if (
                    configuration.price_status != PriceStatus.COMPLETE
                    or configuration.estimated_price_vnd is None
                ):
                    errors.append(
                        f"Configuration {configuration.configuration_id} has incomplete price"
                    )
                elif configuration.estimated_price_vnd > budget:
                    errors.append(
                        f"Configuration {configuration.configuration_id} exceeds budget"
                    )
        if not proposal.options:
            errors.append("Proposal has no options")
        return ProposalVerificationResult(valid=not errors, errors=errors)


def create_proposal(
    requirement: CustomerRequirement,
    sizing: SizingResult,
    configurations: list[ProductConfiguration],
    comparison: ComparisonResult,
    document_hits: list[DocumentHit],
) -> Proposal:
    return RuleBasedProposalService().create(
        requirement, sizing, configurations, comparison, document_hits
    )
