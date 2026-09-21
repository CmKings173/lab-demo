from __future__ import annotations

from datetime import datetime

from shared.contracts import Proposal, WorkflowContext, WorkflowState
from shared.contracts.models import ContractModel

from ..runs.models import RunRecord, RunStatus


class APIErrorDetail(ContractModel):
    code: str
    message: str
    details: object | None = None


class APIErrorResponse(ContractModel):
    error: APIErrorDetail


class CreateRunResponse(ContractModel):
    run_id: str
    status: RunStatus


class ProposalSummary(ContractModel):
    selected_configuration_ids: list[str]
    option_count: int
    evidence_count: int
    estimated_price_vnd: int | None = None
    limitations: list[str]
    sources: list[str]

    @classmethod
    def from_proposal(cls, proposal: Proposal) -> ProposalSummary:
        return cls(
            selected_configuration_ids=[
                configuration.configuration_id
                for configuration in proposal.selected_configurations
            ],
            option_count=len(proposal.options),
            evidence_count=len(proposal.evidence),
            estimated_price_vnd=proposal.estimated_price_vnd,
            limitations=list(proposal.limitations),
            sources=list(proposal.sources),
        )


class RunResultSummary(ContractModel):
    """Safe terminal result summary; it never exposes workflow internals."""

    final_state: WorkflowState
    history: list[WorkflowState]
    candidate_configuration_ids: list[str]
    proposal_available: bool
    proposal: ProposalSummary | None = None
    errors: list[str]

    @classmethod
    def from_context(cls, context: WorkflowContext) -> RunResultSummary:
        return cls(
            final_state=context.state,
            history=list(context.history),
            candidate_configuration_ids=[
                candidate.configuration.configuration_id for candidate in context.candidates
            ],
            proposal_available=context.proposal is not None,
            proposal=(
                ProposalSummary.from_proposal(context.proposal)
                if context.proposal is not None
                else None
            ),
            errors=list(context.errors),
        )


class RunSnapshot(ContractModel):
    run_id: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    final_state: WorkflowState | None = None
    result: RunResultSummary | None = None
    error: str | None = None
    event_count: int

    @classmethod
    def from_record(cls, record: RunRecord) -> RunSnapshot:
        return cls(
            run_id=record.run_id,
            status=record.status,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            final_state=record.final_state,
            result=(
                RunResultSummary.from_context(record.result)
                if record.result is not None
                else None
            ),
            error=record.error,
            event_count=len(record.events),
        )
