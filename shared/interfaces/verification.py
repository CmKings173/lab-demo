from typing import Protocol

from shared.contracts import Proposal, ProposalVerificationResult


class ProposalVerifier(Protocol):
    def verify(self, proposal: Proposal) -> ProposalVerificationResult: ...
