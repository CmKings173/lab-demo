from __future__ import annotations

from shared.contracts import (
    CustomerRequirement,
    ProductCandidate,
    Proposal,
    ProposalOption,
    SizingResult,
)


class RuleBasedProposalService:
    def create(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        candidates: list[ProductCandidate],
    ) -> Proposal:
        sources = sorted(
            {
                source
                for candidate in candidates
                for source in (candidate.product.product_url, candidate.product.datasheet_url)
                if source
            }
        )
        total_price = sum(
            candidate.product.price_vnd or 0 for candidate in candidates[:1]
        ) or None
        option = ProposalOption(
            name="Option A",
            products=candidates[:1],
            rationale="First rule-valid candidate returned by the controlled catalog search.",
            estimated_price_vnd=total_price,
            limitations=list(sizing.warnings),
            sources=sources,
        )
        return Proposal(
            customer_requirement=requirement,
            interpreted_workload=f"{requirement.usage} for a {requirement.model_size_b:g}B model.",
            sizing_result=sizing,
            selected_products=candidates[:1],
            options=[option],
            technical_reasoning=[
                "Sizing was produced by deterministic rules.",
                "Product validity was checked by code before proposal generation.",
            ],
            limitations=list(sizing.warnings),
            unknown_information=[],
            sources=sources,
            estimated_price_vnd=total_price,
        )


def create_proposal(
    requirement: CustomerRequirement,
    sizing: SizingResult,
    candidates: list[ProductCandidate],
) -> Proposal:
    return RuleBasedProposalService().create(requirement, sizing, candidates)
