import hashlib
from collections.abc import Iterable

from lab1_finetune.data.schema import DatasetSplit, FineTuneExample


class DatasetSplitter:
    """Deterministic 20/2/3 family split for the 25-family gold seed."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def split(self, examples: Iterable[FineTuneExample]) -> DatasetSplit:
        grouped: dict[str, list[FineTuneExample]] = {}
        for example in examples:
            grouped.setdefault(example.scenario_family_id, []).append(example)
        families = sorted(
            grouped,
            key=lambda family: hashlib.sha256(f"{self.seed}:{family}".encode()).hexdigest(),
        )
        train_count = round(len(families) * 0.8)
        validation_count = int(len(families) * 0.1)
        train = set(families[:train_count])
        validation = set(families[train_count : train_count + validation_count])
        test = set(families[train_count + validation_count :])
        ordered = sorted(examples, key=lambda item: item.example_id)
        return DatasetSplit(
            train=[item for item in ordered if item.scenario_family_id in train],
            validation=[item for item in ordered if item.scenario_family_id in validation],
            test=[item for item in ordered if item.scenario_family_id in test],
        )
