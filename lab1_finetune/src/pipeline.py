from __future__ import annotations

import hashlib
from collections.abc import Iterable

from lab1_finetune.data.schema import DatasetSplit, FineTuneExample


class DatasetPipeline:
    def __init__(
        self,
        seed: int = 42,
        train_ratio: float = 0.8,
        validation_ratio: float = 0.1,
    ) -> None:
        self.seed = seed
        self.train_ratio = train_ratio
        self.validation_ratio = validation_ratio

    def split(self, examples: Iterable[FineTuneExample]) -> DatasetSplit:
        grouped: dict[str, list[FineTuneExample]] = {}
        for example in examples:
            grouped.setdefault(example.scenario_family_id, []).append(example)
        ordered_families = sorted(
            grouped,
            key=lambda family_id: hashlib.sha256(
                f"{self.seed}:{family_id}".encode()
            ).hexdigest(),
        )
        total = len(ordered_families)
        train_end = int(total * self.train_ratio)
        validation_end = train_end + int(total * self.validation_ratio)
        train_families = set(ordered_families[:train_end])
        validation_families = set(ordered_families[train_end:validation_end])
        test_families = set(ordered_families[validation_end:])
        ordered_examples = sorted(
            (example for family in ordered_families for example in grouped[family]),
            key=lambda example: example.example_id,
        )
        return DatasetSplit(
            train=[e for e in ordered_examples if e.scenario_family_id in train_families],
            validation=[
                e for e in ordered_examples if e.scenario_family_id in validation_families
            ],
            test=[e for e in ordered_examples if e.scenario_family_id in test_families],
        )
