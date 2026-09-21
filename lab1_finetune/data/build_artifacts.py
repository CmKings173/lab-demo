from pathlib import Path

from lab1_finetune.data.schema import FineTuneExample
from lab1_finetune.data.seed import SEED_PATH, build_gold_seed_examples
from lab1_finetune.data.splitter import DatasetSplitter
from lab1_finetune.data.statistics import build_manifest
from lab1_finetune.data.validator import DatasetValidator

DATA_ROOT = Path(__file__).parent


def _write_examples(path: Path, examples: list[FineTuneExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(item.model_dump_json(exclude_none=False) + "\n" for item in examples),
        encoding="utf-8",
    )


def build_artifacts(seed: int = 42) -> None:
    examples = build_gold_seed_examples()
    split = DatasetSplitter(seed=seed).split(examples)
    report = DatasetValidator().validate_split(split)
    if not report.valid:
        raise ValueError("Gold dataset validation failed: " + "; ".join(report.errors))
    _write_examples(SEED_PATH, examples)
    _write_examples(DATA_ROOT / "splits" / "train.jsonl", split.train)
    _write_examples(DATA_ROOT / "splits" / "validation.jsonl", split.validation)
    _write_examples(DATA_ROOT / "splits" / "test.jsonl", split.test)
    manifest = build_manifest(examples, split=split, seed=seed)
    manifest_path = DATA_ROOT / "manifests" / "gold_seed_vi_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


if __name__ == "__main__":
    build_artifacts()
