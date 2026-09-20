from collections.abc import Iterable

from lab1_finetune.evaluation.schema import EvaluationCase


class DeterministicEvaluationSkeleton:
    """Holds evaluation cases; real model invocation remains out of scope."""

    def prepare(self, cases: Iterable[EvaluationCase]) -> list[EvaluationCase]:
        return list(cases)
