from __future__ import annotations

import hashlib
from collections.abc import Iterable

from lab1.data.schema import DatasetSplit, FineTuneExample


class DatasetPipeline:
    def __init__(self, seed: int = 42, train_ratio: float = 0.8, validation_ratio: float = 0.1) -> None:
        self.seed = seed
        self.train_ratio = train_ratio
        self.validation_ratio = validation_ratio

    def split(self, examples: Iterable[FineTuneExample]) -> DatasetSplit:
        ordered = sorted(
            examples,
            key=lambda item: hashlib.sha256(f"{self.seed}:{item.example_id}".encode()).hexdigest(),
        )
        total = len(ordered)
        train_end = int(total * self.train_ratio)
        validation_end = train_end + int(total * self.validation_ratio)
        return DatasetSplit(
            train=ordered[:train_end],
            validation=ordered[train_end:validation_end],
            test=ordered[validation_end:],
        )
