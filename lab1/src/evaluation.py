from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import Field

from shared.contracts.models import ContractModel


class EvaluationCase(ContractModel):
    case_id: str
    prompt: str
    expected: dict[str, Any]


class EvaluationResult(ContractModel):
    total: int
    passed: int
    failed: int
    skipped: int
    details: list[str] = Field(default_factory=list)


class EvaluationRunner:
    """Offline runner skeleton; model invocation is intentionally injected later."""

    def run(self, cases: Iterable[EvaluationCase]) -> EvaluationResult:
        total = len(list(cases))
        return EvaluationResult(total=total, passed=0, failed=0, skipped=total)
