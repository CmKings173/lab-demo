"""Stratified review sample and manifest generation."""

# ruff: noqa: E501

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from lab1_finetune.data.expansion.generator import GeneratedExample


@dataclass(frozen=True)
class ReviewManifest:
    total: int
    family_counts: dict[str, int]
    persona_counts: dict[str, int]
    difficulty_counts: dict[str, int]
    turn_counts: dict[str, int]
    tool_pattern_counts: dict[str, int]
    abstention_count: int
    failure_count: int


def tool_pattern(item: GeneratedExample) -> str:
    calls = item.example.labels.expected_tool_calls
    if not calls:
        return "no_tool"
    if any(
        message.role == "tool" and '"ok":false' in (message.content or "").replace(" ", "")
        for message in item.example.messages
    ):
        return "failure"
    return "single_tool" if len(calls) == 1 else "multi_tool"


def _turn_type(item: GeneratedExample) -> str:
    return (
        "multi_turn"
        if sum(message.role == "user" for message in item.example.messages) > 1
        else "single_turn"
    )


def _review_dimensions(item: GeneratedExample) -> frozenset[tuple[str, str]]:
    return frozenset({
        ("difficulty", item.example.difficulty),
        ("turn", _turn_type(item)),
        ("tool", tool_pattern(item)),
        ("abstention", str(item.example.labels.should_abstain)),
    })


def build_review_sample(
    generated: Sequence[GeneratedExample],
    target: int = 84,
) -> list[GeneratedExample]:
    """Cover family/persona pairs while preferring underrepresented review dimensions."""
    ordered = sorted(generated, key=lambda item: item.example.example_id)
    dimension_counts = Counter(
        dimension for item in ordered for dimension in _review_dimensions(item)
    )
    selected: list[GeneratedExample] = []
    selected_ids: set[str] = set()
    covered: set[tuple[str, str]] = set()
    for family in sorted({item.family_id for item in ordered}):
        for persona in sorted({item.persona for item in ordered}):
            candidates = [
                item for item in ordered
                if item.family_id == family and item.persona == persona
            ]
            match = min(
                candidates,
                key=lambda item: (
                    -sum(
                        1 / dimension_counts[dimension]
                        for dimension in _review_dimensions(item) - covered
                    ),
                    item.example.example_id,
                ),
                default=None,
            )
            if match is not None and match.example.example_id not in selected_ids:
                selected.append(match)
                selected_ids.add(match.example.example_id)
                covered.update(_review_dimensions(match))
    for item in ordered:
        if len(selected) >= target:
            break
        if item.example.example_id not in selected_ids:
            selected.append(item)
            selected_ids.add(item.example.example_id)
            covered.update(_review_dimensions(item))
    return selected[:target]


def review_manifest(sample: Sequence[GeneratedExample]) -> ReviewManifest:
    return ReviewManifest(
        total=len(sample),
        family_counts=dict(Counter(item.family_id for item in sample)),
        persona_counts=dict(Counter(item.persona for item in sample)),
        difficulty_counts=dict(Counter(item.example.difficulty for item in sample)),
        turn_counts=dict(Counter(_turn_type(item) for item in sample)),
        tool_pattern_counts=dict(Counter(tool_pattern(item) for item in sample)),
        abstention_count=sum(item.example.labels.should_abstain for item in sample),
        failure_count=sum(tool_pattern(item) == "failure" for item in sample),
    )


def write_review_artifacts(
    generated: Sequence[GeneratedExample],
    *,
    sample_path: Path,
    manifest_path: Path,
    target: int = 84,
) -> ReviewManifest:
    sample = build_review_sample(generated, target=target)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(
        "".join(
            json.dumps(
                {
                    "example_id": item.example.example_id,
                    "family_id": item.family_id,
                    "persona": item.persona,
                    "difficulty": item.example.difficulty,
                    "scenario_type": item.example.labels.scenario_type,
                    "semantic_template_id": item.semantic_template_id,
                    "wording_recipe_id": item.wording_recipe_id,
                    "semantic_group_id": item.semantic_group_id,
                    "turn_type": _turn_type(item),
                    "tool_pattern": tool_pattern(item),
                    "should_abstain": item.example.labels.should_abstain,
                    "example": item.example.model_dump(mode="json"),
                },
                ensure_ascii=False,
            )
            + "\n"
            for item in sample
        ),
        encoding="utf-8",
    )
    manifest = review_manifest(sample)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
