"""Stable error codes safe to include in Lab 3 public responses and events."""

from __future__ import annotations

from shared.contracts import WorkflowContext, WorkflowEvent, WorkflowEventType, WorkflowState

WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"
WORKFLOW_STATE_FAILED = "WORKFLOW_STATE_FAILED"
WORKFLOW_TOOL_FAILED = "WORKFLOW_TOOL_FAILED"
SIZING_FAILED = "SIZING_FAILED"
PROPOSAL_GENERATION_FAILED = "PROPOSAL_GENERATION_FAILED"
PROPOSAL_VERIFICATION_FAILED = "PROPOSAL_VERIFICATION_FAILED"

_KNOWN_PUBLIC_CODES = frozenset(
    {
        WORKFLOW_EXECUTION_FAILED,
        WORKFLOW_STATE_FAILED,
        WORKFLOW_TOOL_FAILED,
        SIZING_FAILED,
        PROPOSAL_GENERATION_FAILED,
        PROPOSAL_VERIFICATION_FAILED,
    }
)


def state_failure_code(state: WorkflowState) -> str:
    if state == WorkflowState.SIZE:
        return SIZING_FAILED
    if state == WorkflowState.GENERATE_PROPOSAL:
        return PROPOSAL_GENERATION_FAILED
    return WORKFLOW_STATE_FAILED


def normalize_public_error(value: object, *, default: str = WORKFLOW_EXECUTION_FAILED) -> str:
    if isinstance(value, str) and value in _KNOWN_PUBLIC_CODES:
        return value
    return default


def sanitize_failure_event(event: WorkflowEvent) -> WorkflowEvent:
    error_codes = {
        WorkflowEventType.WORKFLOW_FAILED: WORKFLOW_EXECUTION_FAILED,
        WorkflowEventType.STATE_FAILED: state_failure_code(
            event.state or WorkflowState.RECEIVED
        ),
        WorkflowEventType.TOOL_FAILED: WORKFLOW_TOOL_FAILED,
    }
    code = error_codes.get(event.type)
    if code is None:
        return event
    payload = dict(event.payload)
    payload["error"] = code
    return event.model_copy(update={"payload": payload})


def result_error_codes(context: WorkflowContext) -> list[str]:
    if not context.errors:
        return []
    if context.state == WorkflowState.SIZING_FAILED:
        return [SIZING_FAILED]
    if context.state == WorkflowState.PROPOSAL_FAILED:
        if PROPOSAL_GENERATION_FAILED in context.errors:
            return [PROPOSAL_GENERATION_FAILED]
        return [PROPOSAL_VERIFICATION_FAILED]
    return [WORKFLOW_EXECUTION_FAILED]
