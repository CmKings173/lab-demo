from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Protocol

from shared.contracts import WorkflowContext, WorkflowEvent, WorkflowEventType, WorkflowState

from .models import RunRecord, RunStatus


class RunStoreError(ValueError):
    """Base error for invalid run-store operations."""


class UnknownRunError(RunStoreError):
    """Raised when an operation targets a run that has not been created."""


class RunAlreadyExistsError(RunStoreError):
    """Raised when a run ID is created more than once."""


class EventSequenceError(RunStoreError):
    """Raised when an event is not the next append-only sequence."""


class RunStore(Protocol):
    def create_run(self, run_id: str, *, created_at: datetime | None = None) -> RunRecord: ...

    def get(self, run_id: str) -> RunRecord | None: ...

    def emit(self, event: WorkflowEvent) -> None: ...

    def append_event(self, event: WorkflowEvent) -> None: ...

    def events_after(self, run_id: str, sequence: int) -> list[WorkflowEvent]: ...

    def mark_completed(
        self,
        run_id: str,
        *,
        final_state: WorkflowState,
        result: WorkflowContext | None = None,
        completed_at: datetime | None = None,
    ) -> RunRecord: ...

    def mark_failed(
        self, run_id: str, *, error: str, completed_at: datetime | None = None
    ) -> RunRecord: ...


class InMemoryRunStore:
    """Thread-safe append-only run history for local runtime and replay."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = RLock()

    def create_run(self, run_id: str, *, created_at: datetime | None = None) -> RunRecord:
        record = RunRecord(run_id=run_id, created_at=created_at or datetime.now(timezone.utc))
        with self._lock:
            if run_id in self._runs:
                raise RunAlreadyExistsError(f"run already exists: {run_id}")
            self._runs[run_id] = record
            return self._copy_record(record)

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            record = self._runs.get(run_id)
            return self._copy_record(record) if record is not None else None

    def emit(self, event: WorkflowEvent) -> None:
        with self._lock:
            record = self._require_run(event.run_id)
            if record.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                raise RunStoreError("terminal run cannot receive additional events")
            expected_sequence = record.events[-1].sequence + 1 if record.events else 1
            if event.sequence != expected_sequence:
                raise EventSequenceError(
                    f"expected event sequence {expected_sequence}, got {event.sequence}"
                )
            self._apply_lifecycle_event(record, event)
            record.events.append(event.model_copy(deep=True))

    def append_event(self, event: WorkflowEvent) -> None:
        self.emit(event)

    def events_after(self, run_id: str, sequence: int) -> list[WorkflowEvent]:
        if sequence < 0:
            raise ValueError("sequence must be nonnegative")
        with self._lock:
            record = self._require_run(run_id)
            return [
                event.model_copy(deep=True)
                for event in record.events
                if event.sequence > sequence
            ]

    def mark_completed(
        self,
        run_id: str,
        *,
        final_state: WorkflowState,
        result: WorkflowContext | None = None,
        completed_at: datetime | None = None,
    ) -> RunRecord:
        with self._lock:
            record = self._require_run(run_id)
            if record.status == RunStatus.FAILED:
                raise RunStoreError("failed run cannot be marked completed")
            if record.final_state is not None and record.final_state != final_state:
                raise RunStoreError("completed run final state cannot be changed")
            record.status = RunStatus.COMPLETED
            record.final_state = final_state
            record.result = result.model_copy(deep=True) if result is not None else None
            record.completed_at = completed_at or record.completed_at or datetime.now(timezone.utc)
            return self._copy_record(record)

    def mark_failed(
        self, run_id: str, *, error: str, completed_at: datetime | None = None
    ) -> RunRecord:
        if not error.strip():
            raise ValueError("failed run requires a nonblank error")
        with self._lock:
            record = self._require_run(run_id)
            if record.status == RunStatus.COMPLETED:
                raise RunStoreError("completed run cannot be marked failed")
            record.status = RunStatus.FAILED
            record.error = error
            record.completed_at = completed_at or record.completed_at or datetime.now(timezone.utc)
            return self._copy_record(record)

    @staticmethod
    def _copy_record(record: RunRecord | None) -> RunRecord:
        if record is None:
            raise UnknownRunError("run does not exist")
        return record.model_copy(deep=True)

    def _require_run(self, run_id: str) -> RunRecord:
        record = self._runs.get(run_id)
        if record is None:
            raise UnknownRunError(f"run does not exist: {run_id}")
        return record

    @staticmethod
    def _apply_lifecycle_event(record: RunRecord, event: WorkflowEvent) -> None:
        if event.type == WorkflowEventType.WORKFLOW_STARTED:
            if record.status == RunStatus.PENDING:
                record.status = RunStatus.RUNNING
                record.started_at = event.timestamp
        elif event.type == WorkflowEventType.WORKFLOW_COMPLETED:
            if record.status == RunStatus.FAILED:
                raise RunStoreError("failed run cannot receive workflow.completed")
            record.status = RunStatus.COMPLETED
            record.final_state = event.state
            record.completed_at = event.timestamp
        elif event.type == WorkflowEventType.WORKFLOW_FAILED:
            if record.status == RunStatus.COMPLETED:
                raise RunStoreError("completed run cannot receive workflow.failed")
            record.status = RunStatus.FAILED
            record.completed_at = event.timestamp
            error = event.payload.get("error")
            record.error = str(error) if error is not None else "workflow failed"
