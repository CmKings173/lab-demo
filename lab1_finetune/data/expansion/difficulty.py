"""Complexity-based difficulty labels for generated conversations."""

from __future__ import annotations

from lab1_finetune.data.schema import ScenarioType


def infer_difficulty(
    *,
    scenario_type: ScenarioType | str,
    tool_count: int,
    multi_turn: bool,
    should_abstain: bool,
    tool_failure: bool,
    missing_field_count: int,
) -> str:
    """Derive difficulty from observable task complexity, not row position."""
    scenario = getattr(scenario_type, "value", scenario_type)
    if scenario == ScenarioType.CONTRADICTORY_REQUIREMENT.value:
        return "hard"
    score = 0
    if tool_count == 1:
        score += 1
    elif tool_count >= 2:
        score += 2
    if multi_turn:
        score += 1
    if should_abstain:
        score += 1
    if tool_failure:
        score += 2
    if missing_field_count >= 2:
        score += 1
    if scenario in {
        ScenarioType.REQUIREMENT_CHANGED_MID_CONVERSATION.value,
    }:
        score += 2
    if scenario == ScenarioType.TOOL_FAILURE.value:
        return "hard"
    if scenario in {
        ScenarioType.UNKNOWN_PRODUCT_SPEC.value,
        ScenarioType.NO_PRODUCT_FOUND.value,
    }:
        score += 1
    if score <= 1:
        return "easy"
    if score <= 3:
        return "medium"
    return "hard"
