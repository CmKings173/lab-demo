# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from lab1_finetune.data.expansion.diversity import DiversityReport, audit_examples
from lab1_finetune.data.expansion.generator import GeneratedExample, build_expanded_examples
from lab1_finetune.data.expansion.review import tool_pattern, write_review_artifacts
from lab1_finetune.data.expansion.spec import (
    EXPANSION_SEED,
    EXPANSION_TARGET,
    NEAR_DUPLICATE_THRESHOLD,
)
from lab1_finetune.data.exporter import export_qwen_jsonl
from lab1_finetune.data.schema import FineTuneExample
from lab1_finetune.data.similarity import near_duplicate_pairs, normalize_for_similarity

DATA_ROOT = Path(__file__).parent


@dataclass(frozen=True)
class ExpansionManifest:
    dataset_version: str
    seed: int
    total_examples: int
    target_examples: int
    split_counts: dict[str, int]
    family_counts: dict[str, int]
    persona_counts: dict[str, int]
    difficulty_counts: dict[str, int]
    turn_counts: dict[str, int]
    tool_pattern_counts: dict[str, int]
    exact_duplicates: int
    near_duplicate_pairs: int
    near_duplicate_rate: float
    near_duplicate_threshold: float
    family_leakage: list[str]
    content_hash: str
    train_family_counts: dict[str, int]
    validation_family_counts: dict[str, int]
    train_persona_counts: dict[str, int]
    validation_persona_counts: dict[str, int]
    train_difficulty_counts: dict[str, int]
    validation_difficulty_counts: dict[str, int]
    train_turn_counts: dict[str, int]
    validation_turn_counts: dict[str, int]
    train_tool_pattern_counts: dict[str, int]
    validation_tool_pattern_counts: dict[str, int]
    semantic_template_counts: dict[str, int]
    semantic_group_count: int
    semantic_group_leakage: list[str]
    train_validation_near_user_pairs: int
    train_validation_near_conversation_pairs: int
    exact_user_duplicates: int
    exact_history_user_duplicates: int
    exact_final_duplicates: int
    near_user_duplicate_pairs: int
    near_user_duplicate_example_ratio: float
    exact_conversation_duplicates: int
    near_history_user_pairs: int
    near_conversation_duplicate_pairs: int
    near_history_user_duplicate_example_ratio: float
    near_conversation_duplicate_example_ratio: float
    label_text_errors: list[str]
    semantic_errors: list[str]
    python_repr_errors: list[str]
    encoding_errors: list[str]
    final_unique_count: int
    final_duplicate_ratio: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _write_examples(path: Path, examples: list[FineTuneExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(example.model_dump_json(exclude_none=False) + "\n" for example in examples),
        encoding="utf-8",
    )


def _current_user(example: FineTuneExample) -> str:
    return next(
        (message.content or "" for message in reversed(example.messages) if message.role == "user"),
        "",
    )


def _history_and_user(example: FineTuneExample) -> str:
    messages = example.messages
    if messages and messages[-1].role == "assistant":
        messages = messages[:-1]
    return "\n".join(
        message.content or "" for message in messages if message.role in {"user", "assistant"}
    )


def _lexical_components(
    group_ids: list[str], pairs: set[tuple[int, int]]
) -> dict[str, str]:
    """Union semantic groups connected by canonical near-user edges."""
    parent = {group_id: group_id for group_id in group_ids}

    def root(group_id: str) -> str:
        while parent[group_id] != group_id:
            parent[group_id] = parent[parent[group_id]]
            group_id = parent[group_id]
        return group_id

    for left, right in sorted(pairs):
        left_root, right_root = root(group_ids[left]), root(group_ids[right])
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)
    return {group_id: root(group_id) for group_id in sorted(parent)}


def _split_overlap_counts(
    generated: list[GeneratedExample], train_ids: set[str], validation_ids: set[str]
) -> dict[str, int]:
    train = [item.example for item in generated if item.example.example_id in train_ids]
    validation = [item.example for item in generated if item.example.example_id in validation_ids]
    return {
        "user": len(near_duplicate_pairs(
            [_current_user(item) for item in train], NEAR_DUPLICATE_THRESHOLD,
            [_current_user(item) for item in validation],
        )),
        "conversation": len(near_duplicate_pairs(
            [_history_and_user(item) for item in train], NEAR_DUPLICATE_THRESHOLD,
            [_history_and_user(item) for item in validation],
        )),
    }


def _checked_split_overlap_counts(
    generated: list[GeneratedExample], train_ids: set[str], validation_ids: set[str]
) -> dict[str, int]:
    overlap = _split_overlap_counts(generated, train_ids, validation_ids)
    if overlap["user"]:
        raise ValueError(f"Train/validation near-user leakage: {overlap['user']}")
    return overlap


def _near_user_clusters(generated: list[GeneratedExample]) -> list[dict[str, object]]:
    pairs = near_duplicate_pairs(
        [_current_user(item.example) for item in generated], NEAR_DUPLICATE_THRESHOLD
    )
    parent = list(range(len(generated)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left, right in sorted(pairs):
        parent[root(max(left, right))] = root(min(left, right))
    clusters: dict[int, set[int]] = {}
    for left, right in pairs:
        clusters.setdefault(root(left), set()).update((left, right))
    result = []
    for indexes in clusters.values():
        items = [generated[index] for index in sorted(indexes)]
        result.append({
            "size": len(items),
            "example_ids": [item.example.example_id for item in items],
            "families": sorted({item.family_id for item in items}),
            "semantic_template_ids": sorted({item.semantic_template_id for item in items}),
            "wording_recipe_ids": sorted({item.wording_recipe_id for item in items}),
            "normalized_representative": normalize_for_similarity(
                _current_user(items[0].example)
            ),
        })
    return sorted(result, key=lambda row: (-row["size"], row["example_ids"][0]))


def _validation_groups(generated: list[GeneratedExample]) -> set[str]:
    user_pairs = near_duplicate_pairs(
        [_current_user(item.example) for item in generated], NEAR_DUPLICATE_THRESHOLD
    )
    group_ids = [item.semantic_group_id for item in generated]
    group_components = _lexical_components(group_ids, user_pairs)
    components: dict[str, list[GeneratedExample]] = {}
    for item in generated:
        components.setdefault(group_components[item.semantic_group_id], []).append(item)

    def dimensions(items: list[GeneratedExample]) -> set[tuple[str, str]]:
        result: set[tuple[str, str]] = set()
        for item in items:
            result.update({
                ("family", item.family_id),
                ("persona", item.persona),
                ("difficulty", item.example.difficulty),
                ("turn", "multi_turn" if sum(
                    message.role == "user" for message in item.example.messages
                ) > 1 else "single_turn"),
                ("tool", tool_pattern(item)),
            })
        return result

    component_dimensions = {key: dimensions(items) for key, items in components.items()}
    required = set().union(*component_dimensions.values())
    frequencies = Counter(
        dimension for values in component_dimensions.values() for dimension in values
    )
    family_totals = Counter(item.family_id for item in generated)
    validation_families: Counter[str] = Counter()
    selected: set[str] = set()
    covered: set[tuple[str, str]] = set()
    total = 0
    target = round(len(generated) * 0.2)
    maximum = int(len(generated) * 0.25)
    minimum = int(len(generated) * 0.15)
    component_families = {
        key: Counter(item.family_id for item in items)
        for key, items in components.items()
    }

    def candidates() -> list[str]:
        return [
            key for key in sorted(components)
            if key not in selected
            and total + len(components[key]) <= maximum
            and all(
                validation_families[family] + count < family_totals[family]
                for family, count in component_families[key].items()
            )
        ]

    def select(key: str) -> None:
        nonlocal total
        selected.add(key)
        total += len(components[key])
        covered.update(component_dimensions[key])
        validation_families.update(component_families[key])

    # The failure tool path currently occupies one semantic group. Keep that
    # whole component in validation instead of silently losing failure coverage.
    failure_options = [
        key for key in candidates() if ("tool", "failure") in component_dimensions[key]
    ]
    if failure_options:
        select(min(failure_options, key=lambda key: (len(components[key]), key)))

    for family in sorted(family_totals):
        if validation_families[family]:
            continue
        options = [key for key in candidates() if component_families[key][family]]
        if not options:
            raise ValueError(f"No validation component available for {family}")
        family_target = round(family_totals[family] * 0.2)
        select(min(options, key=lambda key: (
            abs(family_target - validation_families[family] - component_families[key][family]),
            len(components[key]), key,
        )))

    while covered != required:
        options = candidates()
        if not options:
            raise ValueError(f"Cannot cover validation dimensions: {sorted(required - covered)}")
        choice = min(
            options,
            key=lambda key: (
                -sum(1 / frequencies[value] for value in component_dimensions[key] - covered)
                / len(components[key]),
                abs(target - (total + len(components[key]))),
                key,
            ),
        )
        if not component_dimensions[choice] - covered:
            raise ValueError(f"Cannot cover validation dimensions: {sorted(required - covered)}")
        select(choice)

    while total < target and candidates():
        choice = min(
            candidates(),
            key=lambda key: (
                sum(abs(
                    validation_families[family] + component_families[key][family]
                    - round(family_totals[family] * 0.2)
                ) for family in family_totals),
                abs(target - (total + len(components[key]))), key,
            ),
        )
        if total >= minimum and abs(target - (total + len(components[choice]))) > abs(target - total):
            break
        select(choice)

    if total < minimum:
        raise ValueError(f"Validation ratio below 15% after component assignment: {total}")

    return {
        group_id for group_id, component in group_components.items() if component in selected
    }


def _content_hash(examples: list[FineTuneExample]) -> str:
    canonical = "\n".join(
        example.model_dump_json(exclude_none=False)
        for example in sorted(examples, key=lambda item: item.example_id)
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _semantic_group_leakage(
    generated: list[GeneratedExample],
    train_ids: set[str],
    validation_ids: set[str],
) -> list[str]:
    train_groups = {
        item.semantic_group_id
        for item in generated
        if item.example.example_id in train_ids
    }
    validation_groups = {
        item.semantic_group_id
        for item in generated
        if item.example.example_id in validation_ids
    }
    return sorted(train_groups & validation_groups)


def _split_dimension_counts(
    generated: list[GeneratedExample], ids: set[str]
) -> dict[str, dict[str, int]]:
    items = [item for item in generated if item.example.example_id in ids]
    return {
        "persona": dict(Counter(item.persona for item in items)),
        "difficulty": dict(Counter(item.example.difficulty for item in items)),
        "turn": dict(Counter(
            "multi_turn" if sum(message.role == "user" for message in item.example.messages) > 1
            else "single_turn" for item in items
        )),
        "tool_pattern": dict(Counter(tool_pattern(item) for item in items)),
    }


def _manifest(
    report: DiversityReport,
    generated: list[GeneratedExample],
    train: list[FineTuneExample],
    validation: list[FineTuneExample],
    seed: int,
    split_overlap: dict[str, int],
) -> ExpansionManifest:
    # Family overlap is intentional in the group-based split; semantic groups
    # are the leakage boundary now. Keep the legacy field empty for callers.
    leakage: list[str] = []
    train_ids = {item.example_id for item in train}
    validation_ids = {item.example_id for item in validation}
    train_dimensions = _split_dimension_counts(generated, train_ids)
    validation_dimensions = _split_dimension_counts(generated, validation_ids)
    examples = train + validation
    return ExpansionManifest(
        dataset_version="1.0.0-vi-expansion",
        seed=seed,
        total_examples=len(examples),
        target_examples=EXPANSION_TARGET,
        split_counts={"train": len(train), "validation": len(validation)},
        family_counts=report.family_counts,
        persona_counts=report.persona_counts,
        difficulty_counts=report.difficulty_counts,
        turn_counts=report.turn_counts,
        tool_pattern_counts=report.tool_pattern_counts,
        exact_duplicates=report.exact_duplicates,
        near_duplicate_pairs=report.near_duplicate_pairs,
        near_duplicate_rate=report.near_duplicate_rate,
        near_duplicate_threshold=NEAR_DUPLICATE_THRESHOLD,
        family_leakage=leakage,
        content_hash=_content_hash(examples),
        train_family_counts=dict(Counter(item.scenario_family_id for item in train)),
        validation_family_counts=dict(Counter(item.scenario_family_id for item in validation)),
        train_persona_counts=train_dimensions["persona"],
        validation_persona_counts=validation_dimensions["persona"],
        train_difficulty_counts=train_dimensions["difficulty"],
        validation_difficulty_counts=validation_dimensions["difficulty"],
        train_turn_counts=train_dimensions["turn"],
        validation_turn_counts=validation_dimensions["turn"],
        train_tool_pattern_counts=train_dimensions["tool_pattern"],
        validation_tool_pattern_counts=validation_dimensions["tool_pattern"],
        semantic_template_counts=dict(Counter(item.semantic_template_id for item in generated)),
        semantic_group_count=len({item.semantic_group_id for item in generated}),
        semantic_group_leakage=_semantic_group_leakage(generated, train_ids, validation_ids),
        train_validation_near_user_pairs=split_overlap["user"],
        train_validation_near_conversation_pairs=split_overlap["conversation"],
        exact_user_duplicates=report.exact_user_duplicates,
        exact_history_user_duplicates=report.exact_history_user_duplicates,
        exact_final_duplicates=report.exact_final_duplicates,
        near_user_duplicate_pairs=report.near_user_duplicate_pairs,
        near_user_duplicate_example_ratio=report.near_user_duplicate_example_ratio,
        exact_conversation_duplicates=report.exact_conversation_duplicates,
        near_history_user_pairs=report.near_history_user_pairs,
        near_conversation_duplicate_pairs=report.near_conversation_duplicate_pairs,
        near_history_user_duplicate_example_ratio=report.near_history_user_example_ratio,
        near_conversation_duplicate_example_ratio=report.near_conversation_duplicate_example_ratio,
        label_text_errors=report.label_text_errors,
        semantic_errors=report.semantic_errors,
        python_repr_errors=report.python_repr_errors,
        encoding_errors=report.encoding_errors,
        final_unique_count=report.final_unique_count,
        final_duplicate_ratio=report.final_duplicate_ratio,
    )


def build_expanded_artifacts(
    *,
    seed: int = EXPANSION_SEED,
    output_root: Path | None = None,
    exports_root: Path | None = None,
) -> ExpansionManifest:
    output_root = output_root or DATA_ROOT / "generated"
    exports_root = exports_root or output_root / "exports"
    generated = build_expanded_examples(seed=seed)
    if len(generated) != EXPANSION_TARGET:
        raise ValueError(f"Expected {EXPANSION_TARGET} generated examples, got {len(generated)}")
    report = audit_examples(generated)
    if not report.valid:
        raise ValueError(
            "Expanded dataset quality gate failed: "
            f"exact_user_duplicates={report.exact_user_duplicates}, "
            f"exact_conversation_duplicates={report.exact_conversation_duplicates}, "
            f"near_user_duplicate_pairs={report.near_user_duplicate_pairs}, "
            f"near_user_duplicate_example_ratio={report.near_user_duplicate_example_ratio:.4f}; "
            + "; ".join(
                report.validator_errors
                + report.legacy_term_hits
                + report.unsupported_product_claims
                + report.label_text_errors
                + report.semantic_errors
                + report.python_repr_errors
                + report.encoding_errors
            )
        )
    validation_groups = _validation_groups(generated)
    train = [
        item.example for item in generated if item.semantic_group_id not in validation_groups
    ]
    validation = [
        item.example for item in generated if item.semantic_group_id in validation_groups
    ]
    all_families = set(report.family_counts)
    if {item.scenario_family_id for item in train} != all_families:
        raise ValueError("Semantic group split left a family out of train")
    if {item.scenario_family_id for item in validation} != all_families:
        raise ValueError("Semantic group split left a family out of validation")
    leakage = _semantic_group_leakage(
        generated,
        {item.example_id for item in train},
        {item.example_id for item in validation},
    )
    if leakage:
        raise ValueError(f"Semantic group split leakage: {leakage}")
    validation_ratio = len(validation) / len(generated)
    if not 0.15 <= validation_ratio <= 0.25:
        raise ValueError(f"Validation ratio outside 15-25%: {validation_ratio:.4f}")
    train_ids = {item.example_id for item in train}
    validation_ids = {item.example_id for item in validation}
    split_overlap = _checked_split_overlap_counts(generated, train_ids, validation_ids)
    all_dimensions = _split_dimension_counts(
        generated, {item.example.example_id for item in generated}
    )
    validation_dimensions = _split_dimension_counts(generated, validation_ids)
    for name in ("persona", "difficulty", "turn", "tool_pattern"):
        missing = set(all_dimensions[name]) - set(validation_dimensions[name])
        if missing:
            raise ValueError(f"Validation lacks {name}: {sorted(missing)}")
    clusters = _near_user_clusters(generated)
    if clusters and clusters[0]["size"] > len(generated) * 0.1:
        raise ValueError(f"Pathological near-user cluster: {clusters[0]['size']} examples")
    _write_examples(output_root / "train.jsonl", train)
    _write_examples(output_root / "validation.jsonl", validation)
    export_qwen_jsonl(train, exports_root / "train_qwen.jsonl")
    export_qwen_jsonl(validation, exports_root / "validation_qwen.jsonl")
    manifest = _manifest(report, generated, train, validation, seed, split_overlap)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "near_duplicate_report.json").write_text(
        json.dumps({"threshold": NEAR_DUPLICATE_THRESHOLD, "cluster_count": len(clusters),
                    "max_cluster_size": clusters[0]["size"] if clusters else 0,
                    "top_clusters": clusters[:10]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_review_artifacts(
        generated,
        sample_path=output_root / "review_sample.jsonl",
        manifest_path=output_root / "review_manifest.json",
    )
    return manifest


if __name__ == "__main__":
    build_expanded_artifacts()
