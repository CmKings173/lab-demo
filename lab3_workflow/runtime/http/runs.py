from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
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
        self._lifecycle_lock = Lock()
        self._shutdown = False

    def submit(self, requirement: CustomerRequirement) -> RunRecord:
        if self.workflow_factory is None:
            raise RuntimeError("workflow factory is not configured")
        with self._lifecycle_lock:
            if self._shutdown:
                raise RuntimeError("workflow run service is shut down")
            run_id = uuid4().hex
            record = self.store.create_run(run_id, requirement=requirement)
            self._executor.submit(self._execute, run_id, requirement)
            return record

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop accepting work and close the executor after submitted runs finish."""
        with self._lifecycle_lock:
            if self._shutdown:
                return
            self._shutdown = True
            self._executor.shutdown(wait=wait, cancel_futures=False)

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
        except Exception:
            try:
                self.store.mark_failed(run_id, error="WORKFLOW_EXECUTION_FAILED")
            except RunStoreError:
                # The workflow may already have emitted workflow.failed; preserve
                # the terminal record instead of raising from a background thread.
                return
