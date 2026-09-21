from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab2_rag_agent.retrieval.documents import FakeDocumentSearch
from lab3_workflow.tests.test_workflow import build_workflow, make_compatible_product
from shared.contracts import (
    CustomerRequirement,
    DocumentChunk,
    Product,
    UsageType,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowState,
)


@dataclass
class CollectingEventSink:
    events: list[WorkflowEvent] = field(default_factory=list)

    def emit(self, event: WorkflowEvent) -> None:
        self.events.append(event)


def observed_workflow(repository: InMemoryProductRepository) -> tuple[object, CollectingEventSink]:
    workflow = build_workflow(repository)
    sink = CollectingEventSink()
    workflow.event_sink = sink
    return workflow, sink


def complete_requirement() -> CustomerRequirement:
    return CustomerRequirement(
        model_size_b=20,
        usage=UsageType.INFERENCE,
        concurrent_users=2,
        budget_vnd=300_000_000,
        storage_requirement_gb=1000,
    )


def test_missing_information_path_emits_completed_lifecycle() -> None:
    workflow, sink = observed_workflow(InMemoryProductRepository([make_compatible_product()]))

    context = workflow.run(CustomerRequirement(model_size_b=20, usage=UsageType.INFERENCE))

    assert context.state == WorkflowState.MISSING_INFORMATION
    assert sink.events[0].type == WorkflowEventType.WORKFLOW_STARTED
    assert sink.events[-1].type == WorkflowEventType.WORKFLOW_COMPLETED
    assert sink.events[-1].payload == {"final_state": WorkflowState.MISSING_INFORMATION.value}


def test_complete_path_emits_domain_and_tool_events() -> None:
    workflow, sink = observed_workflow(InMemoryProductRepository([make_compatible_product()]))

    context = workflow.run(complete_requirement())

    assert context.state == WorkflowState.COMPLETE
    event_types = {event.type for event in sink.events}
    assert {
        WorkflowEventType.WORKFLOW_STARTED,
        WorkflowEventType.WORKFLOW_COMPLETED,
        WorkflowEventType.STATE_STARTED,
        WorkflowEventType.STATE_COMPLETED,
        WorkflowEventType.TOOL_STARTED,
        WorkflowEventType.TOOL_COMPLETED,
        WorkflowEventType.VALIDATION_RESULT,
        WorkflowEventType.DOCUMENT_HIT,
        WorkflowEventType.PROPOSAL_GENERATED,
        WorkflowEventType.PROPOSAL_VERIFIED,
    } <= event_types
    assert sink.events[-1].payload == {"final_state": WorkflowState.COMPLETE.value}


def test_no_suitable_product_path_emits_business_completion() -> None:
    workflow, sink = observed_workflow(InMemoryProductRepository([]))

    context = workflow.run(complete_requirement())

    assert context.state == WorkflowState.NO_SUITABLE_PRODUCT
    assert sink.events[-1].type == WorkflowEventType.WORKFLOW_COMPLETED
    assert sink.events[-1].payload == {"final_state": WorkflowState.NO_SUITABLE_PRODUCT.value}


def test_resolved_fact_emits_fact_resolved_event() -> None:
    product = Product.model_validate(
        make_compatible_product().model_dump(mode="python") | {"max_ram_gb": None}
    )
    workflow, sink = observed_workflow(InMemoryProductRepository([product]))
    workflow.document_search = FakeDocumentSearch(
        [
            DocumentChunk(
                id="server-1-max-ram",
                text="max_ram_gb 1024",
                product_id="server-1",
                source_url="https://example.invalid/server-1/max-ram",
                metadata={
                    "field_name": "max_ram_gb",
                    "value": "1024",
                    "verified": "true",
                },
            )
        ]
    )

    context = workflow.run(complete_requirement())

    assert context.resolved_facts
    assert context.resolved_facts[0].field_name == "max_ram_gb"
    assert context.resolved_facts[0].value == 1024
    assert WorkflowEventType.FACT_RESOLVED in {event.type for event in sink.events}


def test_unknown_validation_path_emits_insufficient_data_completion() -> None:
    product = make_compatible_product()
    product = Product.model_validate(
        product.model_dump(mode="python") | {"max_ram_gb": None}
    )
    workflow, sink = observed_workflow(InMemoryProductRepository([product]))
    workflow.document_search = FakeDocumentSearch([])

    context = workflow.run(complete_requirement())

    assert context.state == WorkflowState.INSUFFICIENT_PRODUCT_DATA
    assert sink.events[-1].type == WorkflowEventType.WORKFLOW_COMPLETED
    assert sink.events[-1].payload == {
        "final_state": WorkflowState.INSUFFICIENT_PRODUCT_DATA.value
    }


def test_proposal_failure_path_emits_failed_verification_without_crashing() -> None:
    workflow, sink = observed_workflow(InMemoryProductRepository([make_compatible_product()]))

    class FailingProposalService:
        def create(self, *args, **kwargs):
            raise RuntimeError("proposal service unavailable")

    workflow.proposal_service = FailingProposalService()
    context = workflow.run(complete_requirement())

    assert context.state == WorkflowState.PROPOSAL_FAILED
    assert WorkflowEventType.STATE_FAILED in {event.type for event in sink.events}
    assert WorkflowEventType.PROPOSAL_VERIFIED not in {event.type for event in sink.events}
    assert sink.events[-1].type == WorkflowEventType.WORKFLOW_COMPLETED
    assert sink.events[-1].payload == {"final_state": WorkflowState.PROPOSAL_FAILED.value}


def test_event_sequence_and_state_lifecycle_are_ordered() -> None:
    workflow, sink = observed_workflow(InMemoryProductRepository([make_compatible_product()]))

    workflow.run(complete_requirement(), run_id="run-sequence")

    assert [event.sequence for event in sink.events] == list(range(1, len(sink.events) + 1))
    assert {event.run_id for event in sink.events} == {"run-sequence"}
    assert sink.events[0].type == WorkflowEventType.WORKFLOW_STARTED
    assert sink.events[-1].type == WorkflowEventType.WORKFLOW_COMPLETED
    for index, event in enumerate(sink.events):
        if event.type != WorkflowEventType.STATE_STARTED:
            continue
        matching = next(
            candidate
            for candidate in sink.events[index + 1 :]
            if candidate.state == event.state
            and candidate.type
            in {WorkflowEventType.STATE_COMPLETED, WorkflowEventType.STATE_FAILED}
        )
        assert matching.sequence > event.sequence
        assert matching.duration_ms is not None
        assert matching.duration_ms >= 0


def test_event_payloads_are_summaries_not_workflow_contexts() -> None:
    workflow, sink = observed_workflow(InMemoryProductRepository([make_compatible_product()]))

    workflow.run(complete_requirement())

    for event in sink.events:
        assert "history" not in event.payload
        assert "configurations" not in event.payload
        event.model_dump_json()


def test_event_sink_does_not_change_workflow_result() -> None:
    requirement = complete_requirement()
    plain_context = build_workflow(
        InMemoryProductRepository([make_compatible_product()])
    ).run(requirement)
    observed, _ = observed_workflow(InMemoryProductRepository([make_compatible_product()]))
    observed_context = observed.run(requirement)

    assert observed_context.model_dump(mode="json") == plain_context.model_dump(mode="json")


def test_unhandled_tool_failure_emits_failed_workflow_event() -> None:
    class FailingRepository(InMemoryProductRepository):
        def search(self, request):
            raise RuntimeError("catalog unavailable")

    workflow, sink = observed_workflow(FailingRepository([make_compatible_product()]))

    with pytest.raises(RuntimeError, match="catalog unavailable"):
        workflow.run(complete_requirement(), run_id="run-failure")

    assert sink.events[0].type == WorkflowEventType.WORKFLOW_STARTED
    assert WorkflowEventType.TOOL_STARTED in {event.type for event in sink.events}
    assert WorkflowEventType.TOOL_FAILED in {event.type for event in sink.events}
    assert sink.events[-1].type == WorkflowEventType.WORKFLOW_FAILED
    assert {event.run_id for event in sink.events} == {"run-failure"}
