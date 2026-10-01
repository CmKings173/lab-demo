from typing import Protocol

from shared.contracts import CustomerRequirement, WorkflowContext, WorkflowEvent


class WorkflowRunner(Protocol):
    def run(self, requirement: CustomerRequirement) -> WorkflowContext: ...


class WorkflowEventSink(Protocol):
    def emit(self, event: WorkflowEvent) -> None: ...
