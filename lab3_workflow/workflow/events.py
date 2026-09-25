from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from shared.contracts import (
    DocumentHit,
    ProposalVerificationResult,
    ResolvedProductFact,
    ValidationResult,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowState,
)
from shared.interfaces import WorkflowEventSink


def _safe_error(error: Exception | str) -> str:
    return str(error)[:500]


class NoOpWorkflowEventSink:
    def emit(self, event: WorkflowEvent) -> None:
        del event


class CompositeWorkflowEventSink:
    def __init__(self, sinks: Iterable[WorkflowEventSink]) -> None:
        self.sinks = tuple(sinks)

    def emit(self, event: WorkflowEvent) -> None:
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception:
                continue


class WorkflowEventEmitter:
    """Create ordered, bounded observability events for one workflow run."""

    def __init__(self, sink: WorkflowEventSink, run_id: str | None = None) -> None:
        self.sink = sink
        self.run_id = run_id or str(uuid4())
        self._sequence = 0
        self._run_started_at = perf_counter()
        self._active_state: WorkflowState | None = None
        self._state_started_at: float | None = None

    @property
    def active_state(self) -> WorkflowState | None:
        return self._active_state

    def _emit(
        self,
        event_type: WorkflowEventType,
        *,
        state: WorkflowState | None = None,
        payload: Mapping[str, object] | None = None,
        duration_ms: int | None = None,
    ) -> WorkflowEvent:
        self._sequence += 1
        event = WorkflowEvent(
            event_id=str(uuid4()),
            run_id=self.run_id,
            sequence=self._sequence,
            type=event_type,
            timestamp=datetime.now(timezone.utc),
            state=state,
            duration_ms=duration_ms,
            payload=dict(payload or {}),
        )
        try:
            self.sink.emit(event)
        except Exception:
            pass
        return event

    @staticmethod
    def _duration_ms(started_at: float | None) -> int:
        if started_at is None:
            return 0
        return max(0, round((perf_counter() - started_at) * 1000))

    def workflow_started(self) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.WORKFLOW_STARTED,
            state=WorkflowState.RECEIVED,
        )

    def workflow_completed(self, final_state: WorkflowState) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.WORKFLOW_COMPLETED,
            state=final_state,
            payload={"final_state": final_state.value},
            duration_ms=self._duration_ms(self._run_started_at),
        )

    def workflow_failed(
        self, state: WorkflowState | None, error: Exception | str
    ) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.WORKFLOW_FAILED,
            state=state,
            payload={"error": _safe_error(error)},
            duration_ms=self._duration_ms(self._run_started_at),
        )

    def state_started(self, state: WorkflowState) -> WorkflowEvent:
        self._active_state = state
        self._state_started_at = perf_counter()
        return self._emit(
            WorkflowEventType.STATE_STARTED,
            state=state,
        )

    def state_completed(self, state: WorkflowState) -> WorkflowEvent | None:
        if self._active_state != state:
            return None
        event = self._emit(
            WorkflowEventType.STATE_COMPLETED,
            state=state,
            duration_ms=self._duration_ms(self._state_started_at),
        )
        self._active_state = None
        self._state_started_at = None
        return event

    def state_failed(
        self, state: WorkflowState, error: Exception | str
    ) -> WorkflowEvent:
        event = self._emit(
            WorkflowEventType.STATE_FAILED,
            state=state,
            payload={"error": _safe_error(error)},
            duration_ms=self._duration_ms(self._state_started_at),
        )
        self._active_state = None
        self._state_started_at = None
        return event

    def tool_started(
        self, name: str, payload: Mapping[str, object] | None = None
    ) -> float:
        started_at = perf_counter()
        self._emit(
            WorkflowEventType.TOOL_STARTED,
            payload={"tool": name, **dict(payload or {})},
        )
        return started_at

    def tool_completed(
        self,
        name: str,
        started_at: float,
        payload: Mapping[str, object] | None = None,
    ) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.TOOL_COMPLETED,
            payload={"tool": name, **dict(payload or {})},
            duration_ms=self._duration_ms(started_at),
        )

    def tool_failed(
        self,
        name: str,
        started_at: float,
        error: Exception | str,
    ) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.TOOL_FAILED,
            payload={"tool": name, "error": _safe_error(error)},
            duration_ms=self._duration_ms(started_at),
        )

    def validation_result(
        self, configuration_id: str, result: ValidationResult, state: WorkflowState
    ) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.VALIDATION_RESULT,
            state=state,
            payload={
                "configuration_id": configuration_id,
                "status": result.status.value,
                "failure_fields": [failure.field for failure in result.failures],
                "unknown_fields": list(result.unknown_fields),
            },
        )

    def document_hit(self, hit: DocumentHit) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.DOCUMENT_HIT,
            payload={
                "document_id": hit.chunk.id,
                "chunk_id": hit.chunk.id,
                "product_id": hit.chunk.product_id,
                "source_url": hit.chunk.source_url,
                "page": hit.chunk.page,
                "retrieval_score": hit.retrieval_score,
                "rerank_score": hit.rerank_score,
            },
        )

    def fact_resolved(self, fact: ResolvedProductFact) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.FACT_RESOLVED,
            payload={
                "product_id": fact.product_id,
                "field_name": fact.field_name,
                "document_id": fact.document_id,
                "source_url": fact.source_url,
                "page": fact.page,
                "confidence": fact.confidence,
                "verified": fact.verified,
            },
        )

    def proposal_generated(
        self, configuration_ids: list[str], evidence_count: int
    ) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.PROPOSAL_GENERATED,
            payload={
                "configuration_ids": configuration_ids,
                "evidence_count": evidence_count,
            },
        )

    def proposal_verified(self, result: ProposalVerificationResult) -> WorkflowEvent:
        return self._emit(
            WorkflowEventType.PROPOSAL_VERIFIED,
            payload={"valid": result.valid, "error_count": len(result.errors)},
        )
