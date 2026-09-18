from typing import Protocol

from shared.contracts import Proposal, SizingResult, CustomerRequirement, ProductCandidate


class ProposalService(Protocol):
    def create(
        self,
        requirement: CustomerRequirement,
        sizing: SizingResult,
        candidates: list[ProductCandidate],
    ) -> Proposal: ...
