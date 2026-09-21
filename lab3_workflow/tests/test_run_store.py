from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab3_workflow.runtime.runs import (
    EventSequenceError,
    InMemoryRunStore,
    RunAlreadyExistsError,
    RunStatus,
    RunStoreError,
    UnknownRunError,
)
from lab3_workflow.tests.test_workflow import build_workflow, make_compatible_product
from shared.contracts import (
    CustomerRequirement,
    UsageType,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowState,
)


def complete_requirement() -> CustomerRequirement:
    return CustomerRequirement(
        model_size_b=20,
        usage=UsageType.INFERENCE,
        concurrent_users=2,
        budget_vnd=300_000_000,
        storage_requirement_gb=1000,
    )


def make_event(
    run_id: str,
    sequence: int,
    event_type: WorkflowEventType,
    *,
    state: WorkflowState | None = None,
    payload: dict[str, object] | None = None,
) -> WorkflowEvent:
    return WorkflowEvent(
        event_id=f"event-{run_id}-{sequence}",
        run_id=run_id,
        sequence=sequence,
        type=event_type,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        state=state,
        payload=payload or {},
    )


def test_create_run_starts_pending_and_returns_isolated_snapshot() -> None:
    store = InMemoryRunStore()
    created = store.create_run("run-1")
    created.status = RunStatus.COMPLETED

    current = store.get("run-1")
    assert current is not None
    assert current.status == RunStatus.PENDING
    assert current.events == []


def test_duplicate_run_creation_is_rejected() -> None:
    store = InMemoryRunStore()
    store.create_run("run-1")

    with pytest.raises(RunAlreadyExistsError):
        store.create_run("run-1")


def test_event_append_is_ordered_and_events_after_replays_cursor() -> None:
    store = InMemoryRunStore()
    store.create_run("run-1")
    started = make_event(
        "run-1", 1, WorkflowEventType.WORKFLOW_STARTED, state=WorkflowState.RECEIVED
    )
    completed = make_event(
        "run-1",
        2,
        WorkflowEventType.WORKFLOW_COMPLETED,
        state=WorkflowState.COMPLETE,
        payload={"final_state": WorkflowState.COMPLETE.value},
    )

    store.append_event(started)
    store.append_event(completed)

    record = store.get("run-1")
    assert record is not None
    assert [event.sequence for event in record.events] == [1, 2]
    assert [event.sequence for event in store.events_after("run-1", 0)] == [1, 2]
    assert [event.sequence for event in store.events_after("run-1", 1)] == [2]
    assert record.status == RunStatus.COMPLETED
    assert record.final_state == WorkflowState.COMPLETE


@pytest.mark.parametrize("sequence", [1, 3])
def test_duplicate_or_out_of_order_event_is_rejected(sequence: int) -> None:
    store = InMemoryRunStore()
    store.create_run("run-1")
    store.append_event(make_event("run-1", 1, WorkflowEventType.WORKFLOW_STARTED))

    with pytest.raises(EventSequenceError):
        store.append_event(make_event("run-1", sequence, WorkflowEventType.STATE_STARTED))


def test_event_for_unknown_run_is_rejected() -> None:
    store = InMemoryRunStore()

    with pytest.raises(UnknownRunError):
        store.append_event(make_event("missing", 1, WorkflowEventType.WORKFLOW_STARTED))

    assert store.get("missing") is None
    with pytest.raises(UnknownRunError):
        store.events_after("missing", 0)


def test_event_run_id_mismatch_cannot_append_to_another_run() -> None:
    store = InMemoryRunStore()
    store.create_run("run-1")

    with pytest.raises(UnknownRunError):
        store.append_event(make_event("run-2", 1, WorkflowEventType.WORKFLOW_STARTED))


def test_business_terminal_outcome_is_completed_run() -> None:
    store = InMemoryRunStore()
    store.create_run("run-1")
    store.append_event(make_event("run-1", 1, WorkflowEventType.WORKFLOW_STARTED))
    store.append_event(
        make_event(
            "run-1",
            2,
            WorkflowEventType.WORKFLOW_COMPLETED,
            state=WorkflowState.PROPOSAL_FAILED,
            payload={"final_state": WorkflowState.PROPOSAL_FAILED.value},
        )
    )

    record = store.mark_completed("run-1", final_state=WorkflowState.PROPOSAL_FAILED)
    assert record.status == RunStatus.COMPLETED
    assert record.final_state == WorkflowState.PROPOSAL_FAILED


def test_technical_failure_is_failed_run() -> None:
    store = InMemoryRunStore()
    store.create_run("run-1")
    store.append_event(make_event("run-1", 1, WorkflowEventType.WORKFLOW_STARTED))
    store.append_event(
        make_event(
            "run-1",
            2,
            WorkflowEventType.WORKFLOW_FAILED,
            payload={"error": "catalog unavailable"},
        )
    )

    record = store.get("run-1")
    assert record is not None
    assert record.status == RunStatus.FAILED
    assert record.error == "catalog unavailable"
    with pytest.raises(RunStoreError):
        store.mark_completed("run-1", final_state=WorkflowState.COMPLETE)


def test_conflicting_terminal_event_does_not_corrupt_history() -> None:
    store = InMemoryRunStore()
    store.create_run("run-1")
    store.append_event(make_event("run-1", 1, WorkflowEventType.WORKFLOW_STARTED))
    store.append_event(
        make_event("run-1", 2, WorkflowEventType.WORKFLOW_COMPLETED, state=WorkflowState.COMPLETE)
    )

    with pytest.raises(RunStoreError):
        store.append_event(
            make_event(
                "run-1",
                3,
                WorkflowEventType.WORKFLOW_FAILED,
                payload={"error": "late failure"},
            )
        )

    record = store.get("run-1")
    assert record is not None
    assert record.status == RunStatus.COMPLETED
    assert [event.sequence for event in record.events] == [1, 2]


def test_run_record_rejects_failed_state_without_error() -> None:
    from lab3_workflow.runtime.runs.models import RunRecord

    with pytest.raises(ValidationError):
        RunRecord(run_id="run-1", status=RunStatus.FAILED)


def test_workflow_events_can_be_stored_and_completed_with_result() -> None:
    store = InMemoryRunStore()
    store.create_run("run-integration")
    workflow = build_workflow(InMemoryProductRepository([make_compatible_product()]))
    workflow.event_sink = store

    context = workflow.run(complete_requirement(), run_id="run-integration")
    record = store.mark_completed(
        "run-integration", final_state=context.state, result=context
    )

    assert record.status == RunStatus.COMPLETED
    assert record.result is not None
    assert record.result.state == context.state
    assert [event.sequence for event in record.events] == list(
        range(1, len(record.events) + 1)
    )
    assert store.events_after("run-integration", 0) == record.events


def test_concurrent_readers_see_ordered_snapshots() -> None:
    store = InMemoryRunStore()
    store.create_run("run-concurrent")
    events = [
        make_event("run-concurrent", index, WorkflowEventType.STATE_STARTED)
        for index in range(1, 21)
    ]

    def append_events() -> None:
        for event in events:
            store.append_event(event)

    def read_snapshots() -> None:
        for _ in range(50):
            record = store.get("run-concurrent")
            assert record is not None
            sequences = [event.sequence for event in record.events]
            assert sequences == list(range(1, len(sequences) + 1))

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(read_snapshots) for _ in range(3)]
        futures.append(executor.submit(append_events))
        for future in futures:
            future.result()

    assert [event.sequence for event in store.events_after("run-concurrent", 0)] == list(
        range(1, 21)
    )
