from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeAlias
from uuid import uuid4

from shared.contracts import CustomerRequirement

from ...workflow.orchestrator import DeterministicWorkflow
from ..runs.models import RunRecord
from ..runs.store import InMemoryRunStore, RunStoreError

WorkflowFactory: TypeAlias = Callable[[], DeterministicWorkflow]


class WorkflowRunService:
    """Coordinates background workflow execution with the append-only run store."""

    def __init__(
        self,
        *,
        workflow_factory: WorkflowFactory | None,
        store: InMemoryRunStore | None = None,
        max_workers: int = 4,
    ) -> None:
        self.store = store or InMemoryRunStore()
        self.workflow_factory = workflow_factory
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="lab-demo-workflow",
        )

    def submit(self, requirement: CustomerRequirement) -> RunRecord:
        if self.workflow_factory is None:
            raise RuntimeError("workflow factory is not configured")
        run_id = uuid4().hex
        record = self.store.create_run(run_id)
        self._executor.submit(self._execute, run_id, requirement)
        return record

    def _execute(self, run_id: str, requirement: CustomerRequirement) -> None:
        try:
            workflow = self.workflow_factory()
            workflow.event_sink = self.store
            context = workflow.run(requirement, run_id=run_id)
            self.store.mark_completed(
                run_id,
                final_state=context.state,
                result=context,
            )
        except Exception as exc:
            error = str(exc).strip() or exc.__class__.__name__
            try:
                self.store.mark_failed(run_id, error=error)
            except RunStoreError:
                # The workflow may already have emitted workflow.failed; preserve
                # the terminal record instead of raising from a background thread.
                return
