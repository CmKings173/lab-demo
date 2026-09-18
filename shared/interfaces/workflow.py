from typing import Protocol

from shared.contracts import CustomerRequirement, WorkflowContext


class WorkflowRunner(Protocol):
    def run(self, requirement: CustomerRequirement) -> WorkflowContext: ...
