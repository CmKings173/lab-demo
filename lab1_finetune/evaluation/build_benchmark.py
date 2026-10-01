"""Build the frozen independent Lab 1 evaluation benchmark."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from lab1_finetune.data.expansion.generator import build_expanded_examples
from lab1_finetune.data.expansion.semantic_validation import validate_generated_semantics
from lab1_finetune.evaluation.benchmark import (
    EVAL_SEED,
    audit_eval_isolation,
    benchmark_content_hash,
    build_independent_eval_records,
)


@dataclass(frozen=True)
class EvalManifest:
    dataset_version: str
    seed: int
    total_examples: int
    scenario_counts: dict[str, int]
    persona_robustness_assessed: bool
    difficulty_counts: dict[str, int]
    tool_pattern_counts: dict[str, int]
    failure_cases: int
    abstention_cases: int
    exact_overlap_with_training: int
    near_duplicate_pairs_with_training: int
    internal_exact_user_duplicates: int
    internal_near_user_pairs: int
    internal_near_user_example_ratio: float
    semantic_template_overlap_with_training: int
    semantic_errors: list[str]
    near_duplicate_threshold: float
    content_hash: str


def _counts(records: list) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    scenario: dict[str, int] = {}
    difficulty: dict[str, int] = {}
    tools: dict[str, int] = {}
    for record in records:
        scenario[record.scenario_family_id] = scenario.get(record.scenario_family_id, 0) + 1
        difficulty[record.difficulty] = difficulty.get(record.difficulty, 0) + 1
        count = len(record.case.gold_labels.expected_tool_calls)
        pattern = "no_tool" if count == 0 else "single_tool" if count == 1 else "multi_tool"
        tools[pattern] = tools.get(pattern, 0) + 1
    return scenario, difficulty, tools


def build_eval_artifacts(
    *,
    seed: int = EVAL_SEED,
    output_root: Path | None = None,
) -> EvalManifest:
    output_root = output_root or Path(__file__).parent
    output_root.mkdir(parents=True, exist_ok=True)
    records = build_independent_eval_records(seed)
    training = build_expanded_examples()
    report = audit_eval_isolation([record.case for record in records], training)
    training_templates = {item.semantic_template_id for item in training}
    template_overlap = len(
        {record.template_id for record in records} & training_templates
    )
    report = replace(report, template_overlap_with_training=template_overlap)
    semantic_errors = validate_generated_semantics([record.case for record in records])
    if semantic_errors:
        raise ValueError(
            "Independent evaluation semantic validation failed: "
            + "; ".join(semantic_errors)
        )
    if not report.valid:
        raise ValueError(
            "Independent evaluation quality gate failed: "
            f"train_exact={report.exact_overlap}, "
            f"train_near={report.near_duplicate_pairs}, "
            f"internal_exact={report.internal_exact_user_duplicates}, "
            f"internal_near_pairs={report.internal_near_user_pairs}, "
            f"internal_near_ratio={report.internal_near_user_example_ratio:.4f}, "
            f"template_overlap={report.template_overlap_with_training}"
        )
    scenario_counts, difficulty_counts, tool_pattern_counts = _counts(records)
    failure_cases = sum(record.scenario_family_id == "eval_failure" for record in records)
    abstention_cases = sum(record.case.gold_labels.should_abstain for record in records)
    tool_pattern_counts["failure"] = failure_cases
    gold_eval_path = output_root / "gold_eval.jsonl"
    gold_eval_path.write_text(
        "".join(record.case.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )
    manifest = EvalManifest(
        dataset_version="lab1-evaluation-v1",
        seed=seed,
        total_examples=len(records),
        scenario_counts=scenario_counts,
        persona_robustness_assessed=False,
        difficulty_counts=difficulty_counts,
        tool_pattern_counts=tool_pattern_counts,
        failure_cases=failure_cases,
        abstention_cases=abstention_cases,
        exact_overlap_with_training=report.exact_overlap,
        near_duplicate_pairs_with_training=report.near_duplicate_pairs,
        internal_exact_user_duplicates=report.internal_exact_user_duplicates,
        internal_near_user_pairs=report.internal_near_user_pairs,
        internal_near_user_example_ratio=report.internal_near_user_example_ratio,
        semantic_template_overlap_with_training=report.template_overlap_with_training,
        semantic_errors=semantic_errors,
        near_duplicate_threshold=0.92,
        content_hash=benchmark_content_hash(records),
    )
    (output_root / "eval_manifest.json").write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    result = build_eval_artifacts()
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
