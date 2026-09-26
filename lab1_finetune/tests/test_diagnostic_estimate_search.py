from __future__ import annotations

import json

from lab1_finetune.data.expansion.generator import build_expanded_examples
from lab1_finetune.data.frozen_contracts import (
    ChatMessage,
    ModelResponse,
    SearchProductsArgs,
    ToolCall,
)
from lab1_finetune.data.similarity import near_duplicate_pairs
from lab1_finetune.evaluation.benchmark import build_independent_eval_records
from lab1_finetune.evaluation.diagnostic_estimate_search import (
    build_diagnostic_cases,
    score_diagnostic_report,
)


def _user_text(case) -> str:
    return " ".join(message.content or "" for message in case.messages if message.role == "user")


def _decision_outputs(case) -> list[dict]:
    outputs = []
    for decision_index, call in enumerate(case.gold_labels.expected_tool_calls, start=1):
        predicted_call = ToolCall(
            id=f"{case.case_id}-prediction-{decision_index}",
            name=call.name,
            arguments=call.arguments,
        )
        outputs.append(
            ModelResponse(
                message=ChatMessage(role="assistant", tool_calls=[predicted_call]),
                finish_reason="tool_calls",
            ).model_dump(mode="json")
        )
    outputs.append(
        ModelResponse(
            message=ChatMessage(role="assistant", content="Đã tìm được cấu hình phù hợp."),
            finish_reason="stop",
        ).model_dump(mode="json")
    )
    return outputs


def _report_for(case) -> dict:
    return {
        "cases": [
            {"case_id": case.case_id, "decision_outputs": _decision_outputs(case)}
        ]
    }


def test_diagnostic_covers_estimate_then_search_and_scores_both_stages() -> None:
    cases = build_diagnostic_cases()
    assert len(cases) == 12

    for case in cases:
        calls = case.gold_labels.expected_tool_calls
        assert [call.name for call in calls] == [
            "estimate_ai_requirements",
            "search_products",
        ]
        search = SearchProductsArgs.model_validate(calls[1].arguments)
        estimate_result = next(
            message
            for message in case.messages
            if message.role == "tool" and message.tool_call_id == f"{case.case_id}-estimate"
        )
        result = json.loads(estimate_result.content or "{}")
        assert search.filters.min_ram_gb == result["data"]["recommended_system_ram_gb"]

    report = {"cases": [
        {"case_id": case.case_id, "decision_outputs": _decision_outputs(case)}
        for case in cases
    ]}
    assert len(report["cases"][0]["decision_outputs"]) == 3
    assert report["cases"][0]["decision_outputs"][2]["message"]["tool_calls"] == []
    scores = score_diagnostic_report(report)
    assert scores["case_count"] == 12
    assert scores["tool_trajectory_accuracy"] == 1.0
    assert scores["step1_argument_accuracy"] == 1.0
    assert scores["step2_derived_min_ram_accuracy"] == 1.0


def test_diagnostic_scores_estimate_args_and_derived_ram_independently() -> None:
    cases = build_diagnostic_cases()
    report = {"cases": [
        {"case_id": case.case_id, "decision_outputs": _decision_outputs(case)}
        for case in cases
    ]}
    report["cases"][0]["decision_outputs"][0]["message"]["tool_calls"][0][
        "arguments"
    ]["context_length"] += 1
    report["cases"][1]["decision_outputs"][1]["message"]["tool_calls"][0][
        "arguments"
    ]["filters"]["min_ram_gb"] += 1

    scores = score_diagnostic_report(report)
    assert scores["step1_argument_matches"] == 11
    assert scores["step2_derived_min_ram_matches"] == 11


def test_diagnostic_rejects_reversed_estimate_search_decisions() -> None:
    case = build_diagnostic_cases()[0]
    report = _report_for(case)
    decisions = report["cases"][0]["decision_outputs"]
    decisions[0], decisions[1] = decisions[1], decisions[0]

    scores = score_diagnostic_report(report)

    assert scores["step1_argument_matches"] == 0
    assert scores["step2_derived_min_ram_matches"] == 0
    assert scores["tool_trajectory_matches"] == 0


def test_diagnostic_rejects_both_tools_in_one_decision() -> None:
    case = build_diagnostic_cases()[0]
    report = _report_for(case)
    decisions = report["cases"][0]["decision_outputs"]
    decisions[0]["message"]["tool_calls"].extend(
        decisions[1]["message"]["tool_calls"]
    )
    decisions[1]["message"]["tool_calls"] = []

    scores = score_diagnostic_report(report)

    assert scores["step1_argument_matches"] == 0
    assert scores["step2_derived_min_ram_matches"] == 0
    assert scores["tool_trajectory_matches"] == 0


def test_diagnostic_rejects_extra_tool_call() -> None:
    case = build_diagnostic_cases()[0]
    report = _report_for(case)
    report["cases"][0]["decision_outputs"][1]["message"]["tool_calls"].append(
        {"id": "extra-call", "name": "get_product", "arguments": {"product_id": "x"}}
    )

    scores = score_diagnostic_report(report)

    assert scores["step1_argument_matches"] == 1
    assert scores["step2_derived_min_ram_matches"] == 0
    assert scores["tool_trajectory_matches"] == 0


def test_diagnostic_rejects_tool_call_after_search_decision() -> None:
    case = build_diagnostic_cases()[0]
    report = _report_for(case)
    report["cases"][0]["decision_outputs"][2]["message"]["tool_calls"].append(
        {"id": "extra-call", "name": "get_product", "arguments": {"product_id": "x"}}
    )

    scores = score_diagnostic_report(report)

    assert scores["step1_argument_matches"] == 1
    assert scores["step2_derived_min_ram_matches"] == 1
    assert scores["tool_trajectory_matches"] == 0


def test_diagnostic_rejects_correct_ram_with_wrong_budget() -> None:
    case = build_diagnostic_cases()[0]
    report = _report_for(case)
    filters = report["cases"][0]["decision_outputs"][1]["message"]["tool_calls"][0][
        "arguments"
    ]["filters"]
    filters["max_base_price_vnd"] += 1

    scores = score_diagnostic_report(report)

    assert scores["step1_argument_matches"] == 1
    assert scores["step2_derived_min_ram_matches"] == 0
    assert scores["tool_trajectory_matches"] == 1


def test_diagnostic_rejects_correct_ram_with_wrong_product_type() -> None:
    case = build_diagnostic_cases()[0]
    report = _report_for(case)
    filters = report["cases"][0]["decision_outputs"][1]["message"]["tool_calls"][0][
        "arguments"
    ]["filters"]
    filters["product_type"] = (
        "ai_server" if filters["product_type"] != "ai_server" else "ai_workstation"
    )

    scores = score_diagnostic_report(report)

    assert scores["step1_argument_matches"] == 1
    assert scores["step2_derived_min_ram_matches"] == 0
    assert scores["tool_trajectory_matches"] == 1


def test_diagnostic_wording_and_critical_values_are_held_out() -> None:
    diagnostic = build_diagnostic_cases()
    training = build_expanded_examples(seed=20260922)
    benchmark = build_independent_eval_records(seed=20260923)

    training_texts = [
        message.content or ""
        for item in training
        for message in item.example.messages
        if message.role == "user"
    ]
    benchmark_texts = [
        message.content or ""
        for item in benchmark
        for message in item.case.messages
        if message.role == "user"
    ]
    diagnostic_texts = [_user_text(case) for case in diagnostic]
    assert near_duplicate_pairs(diagnostic_texts, 0.92) == set()
    assert near_duplicate_pairs(training_texts, 0.92, diagnostic_texts) == set()
    assert near_duplicate_pairs(benchmark_texts, 0.92, diagnostic_texts) == set()

    def values(cases, field: str) -> set[object]:
        return {
            getattr(
                getattr(case, "gold_labels", getattr(case, "labels", None)).extracted_requirement,
                field,
            )
            for case in cases
            if getattr(
                getattr(case, "gold_labels", getattr(case, "labels", None)).extracted_requirement,
                field,
            )
            is not None
        }

    for field in ("model_size_b", "context_length", "concurrent_users", "budget_vnd"):
        training_values = values([item.example for item in training], field)
        assert values(diagnostic, field).isdisjoint(training_values)
        assert values(diagnostic, field).isdisjoint(
            values([item.case for item in benchmark], field)
        )
