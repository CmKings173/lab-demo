import hashlib
from collections import Counter
from datetime import datetime, timezone

from lab1_finetune.data.schema import DatasetManifest, DatasetSplit, FineTuneExample


def build_manifest(
    examples: list[FineTuneExample],
    *,
    split: DatasetSplit | None = None,
    seed: int = 42,
    dataset_version: str = "3.0.0-vi-gold",
) -> DatasetManifest:
    canonical = "\n".join(
        item.model_dump_json(exclude_none=False)
        for item in sorted(examples, key=lambda example: example.example_id)
    )
    return DatasetManifest(
        dataset_version=dataset_version,
        created_at=datetime.now(timezone.utc),
        example_count=len(examples),
        family_count=len({item.scenario_family_id for item in examples}),
        language_counts=dict(Counter(item.language for item in examples)),
        intent_counts=dict(Counter(item.labels.intent.value for item in examples)),
        scenario_type_counts=dict(
            Counter(item.labels.scenario_type.value for item in examples)
        ),
        task_type_counts=dict(Counter(item.task_type for item in examples)),
        split_counts=(
            {
                "train": len(split.train),
                "validation": len(split.validation),
                "test": len(split.test),
            }
            if split
            else {}
        ),
        seed=seed,
        content_hash=hashlib.sha256(canonical.encode()).hexdigest(),
    )
