from __future__ import annotations

from shared.contracts import (
    ComparisonResult,
    CustomerRequirement,
    DocumentHit,
    Evidence,
    ProductConfiguration,
    Proposal,
    ProposalOption,
    ProposalVerificationResult,
    SizingResult,
)


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
        evidence = self._build_evidence(selected, document_hits)
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
        sources = sorted({item.source_url for item in evidence})
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

    @staticmethod
    def _build_evidence(
        configurations: list[ProductConfiguration], document_hits: list[DocumentHit]
    ) -> list[Evidence]:
        evidence: list[Evidence] = []
        hits_by_product: dict[str, list[DocumentHit]] = {}
        for hit in document_hits:
            if hit.chunk.product_id:
                hits_by_product.setdefault(hit.chunk.product_id, []).append(hit)
        for configuration in configurations:
            product_id = configuration.product.id
            product_hits = hits_by_product.get(product_id, [])
            fallback_sources = [
                hit.chunk.source_url for hit in product_hits if hit.chunk.source_url
            ]
            fallback_sources.extend(configuration.source_urls)
            field_sources = {
                "total_vram_gb": (
                    configuration.selected_gpu.source_urls
                    if configuration.selected_gpu is not None
                    else []
                ),
                "configured_ram_gb": configuration.product.source_urls,
            }
            for field, value in (
                ("total_vram_gb", configuration.total_vram_gb),
                ("configured_ram_gb", configuration.configured_ram_gb),
            ):
                sources = field_sources[field] or fallback_sources
                if not sources:
                    continue
                source_url = sorted(set(sources))[0]
                matching_hit = next(
                    (hit for hit in product_hits if hit.chunk.source_url == source_url), None
                )
                evidence.append(
                    Evidence(
                        claim=f"{configuration.configuration_id}.{field}",
                        value=value,
                        source_url=source_url,
                        product_id=product_id,
                        document_id=(matching_hit.chunk.id if matching_hit else None),
                        page=(matching_hit.chunk.page if matching_hit else None),
                        verified=True,
                    )
                )
        return evidence


class RuleBasedProposalVerifier:
    def verify(self, proposal: Proposal) -> ProposalVerificationResult:
        errors: list[str] = []
        evidence_by_claim = {item.claim: item for item in proposal.evidence if item.verified}
        configuration_ids = {
            configuration.configuration_id for configuration in proposal.selected_configurations
        }
        for option in proposal.options:
            if option.configuration.configuration_id not in configuration_ids:
                errors.append(f"Unknown configuration: {option.configuration.configuration_id}")
        for claim, value in proposal.technical_claims.items():
            item = evidence_by_claim.get(claim)
            if item is None or item.value != value:
                errors.append(f"Unsupported claim: {claim}")
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
            recommended_storage = proposal.sizing_result.recommended_storage_gb
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
            if (
                budget is not None
                and configuration.estimated_price_vnd is not None
                and configuration.estimated_price_vnd > budget
            ):
                errors.append(f"Configuration {configuration.configuration_id} exceeds budget")
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
