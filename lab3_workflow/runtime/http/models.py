from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field

from shared.contracts import ProductConfiguration, Proposal, WorkflowContext, WorkflowState
from shared.contracts.models import ContractModel

from ...errors import normalize_public_error, result_error_codes
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


class ConfigurationSummary(ContractModel):
    """Display-safe configuration facts without the workflow or raw evidence payloads."""

    configuration_id: str
    product_name: str
    manufacturer: str | None = None
    gpu: str | None = None
    gpu_count: int | None = None
    ram_gb: int | None = None
    storage_gb: int | None = None
    estimated_price_vnd: int | None = None
    evidence_sources: list[str]

    @classmethod
    def from_configuration(
        cls, configuration: ProductConfiguration, sources: list[str]
    ) -> ConfigurationSummary:
        product = configuration.product
        return cls(
            configuration_id=configuration.configuration_id,
            product_name=product.name,
            manufacturer=product.manufacturer,
            gpu=(
                configuration.selected_gpu.name
                if configuration.selected_gpu is not None
                else product.gpu_model
            ),
            gpu_count=configuration.gpu_count or product.gpu_count,
            ram_gb=configuration.configured_ram_gb or product.installed_ram_gb,
            storage_gb=configuration.configured_storage_gb or product.installed_storage_gb,
            estimated_price_vnd=configuration.estimated_price_vnd,
            evidence_sources=sources,
        )


class ProposalOptionSummary(ContractModel):
    name: str
    rationale: str
    configuration: ConfigurationSummary
    estimated_price_vnd: int | None = None
    limitations: list[str]


def _public_source_label(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    try:
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    except ValueError:
        return None


class ProposalSummary(ContractModel):
    selected_configuration_ids: list[str]
    option_count: int
    evidence_count: int
    estimated_price_vnd: int | None = None
    limitations: list[str]
    sources: list[str]
    selected_configurations: list[ConfigurationSummary] = Field(default_factory=list)
    options: list[ProposalOptionSummary] = Field(default_factory=list)

    @classmethod
    def from_proposal(cls, proposal: Proposal) -> ProposalSummary:
        by_product: dict[str, list[str]] = {}
        evidence_items = [
            *proposal.evidence,
            *(evidence for option in proposal.options for evidence in option.evidence),
        ]
        for evidence in evidence_items:
            label = _public_source_label(evidence.source_url)
            if label is not None:
                product_sources = by_product.setdefault(evidence.product_id, [])
                if label not in product_sources:
                    product_sources.append(label)

        def summarize(configuration: ProductConfiguration) -> ConfigurationSummary:
            product_id = configuration.product.id
            source_candidates = [
                *configuration.source_urls,
                *by_product.get(product_id, []),
            ]
            safe_sources: list[str] = []
            for candidate in source_candidates:
                label = _public_source_label(candidate)
                if label is not None and label not in safe_sources:
                    safe_sources.append(label)
            return ConfigurationSummary.from_configuration(configuration, safe_sources)

        return cls(
            selected_configuration_ids=[
                configuration.configuration_id
                for configuration in proposal.selected_configurations
            ],
            option_count=len(proposal.options),
            evidence_count=len(proposal.evidence),
            estimated_price_vnd=proposal.estimated_price_vnd,
            limitations=list(proposal.limitations),
            sources=[
                label
                for source in proposal.sources
                if (label := _public_source_label(source)) is not None
            ],
            selected_configurations=[
                summarize(configuration) for configuration in proposal.selected_configurations
            ],
            options=[
                ProposalOptionSummary(
                    name=option.name,
                    rationale=option.rationale,
                    configuration=summarize(option.configuration),
                    estimated_price_vnd=option.estimated_price_vnd,
                    limitations=list(option.limitations),
                )
                for option in proposal.options
            ],
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
            errors=result_error_codes(context),
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
            error=(
                normalize_public_error(record.error)
                if record.error is not None
                else None
            ),
            event_count=len(record.events),
        )
