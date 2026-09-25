from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from shared.contracts import WorkflowContext, WorkflowEvent, WorkflowState
from shared.contracts.models import ContractModel


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunRecord(ContractModel):
    run_id: str = Field(min_length=1)
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = Field(default_factory=_utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    final_state: WorkflowState | None = None
    result: WorkflowContext | None = None
    error: str | None = None
    events: list[WorkflowEvent] = Field(default_factory=list)

    @field_validator("run_id")
    @classmethod
    def reject_blank_run_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("run_id must not be blank")
        return value

    @field_validator("created_at", "started_at", "completed_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("run timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_status_fields(self) -> RunRecord:
        if self.status == RunStatus.FAILED:
            if self.error is None or not self.error.strip():
                raise ValueError("failed run requires a nonblank error")
        elif self.error is not None:
            raise ValueError("only failed runs may contain an error")
        return self
