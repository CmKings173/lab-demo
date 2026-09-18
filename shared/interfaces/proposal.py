from typing import Protocol

from shared.contracts import (
    ComparisonResult,
    CustomerRequirement,
    DocumentHit,
    ProductConfiguration,
    Proposal,
    SizingResult,
)


class ProposalService(Protocol):
    def create(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        configurations: list[ProductConfiguration],
        comparison: ComparisonResult,
        document_hits: list[DocumentHit],
    ) -> Proposal: ...
