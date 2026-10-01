from lab1_finetune.data.frozen_contracts import ToolCall
from lab1_finetune.data.seed import load_gold_seed
from lab1_finetune.evaluation.metrics import (
    accuracy,
    evaluate_predictions,
    extraction_scores,
    unsupported_product_claim_rate,
)
from lab1_finetune.evaluation.schema import EvaluationCase, EvaluationPrediction


def test_evaluation_metrics_compute_real_values() -> None:
    assert accuracy([True, False, True]) == 2 / 3
    scores = extraction_scores(
        [{"model_size_b": 32, "usage": "inference"}],
        [{"model_size_b": 32, "budget_vnd": 300_000_000}],
    )
    assert scores.precision == 0.5
    assert scores.recall == 0.5
    assert scores.f1 == 0.5
    assert unsupported_product_claim_rate(unsupported=1, total_claims=4) == 0.25


def test_evaluation_report_exposes_all_required_metrics() -> None:
    examples = load_gold_seed()
    selected = [examples[0], examples[2], examples[20]]
    cases = [
        EvaluationCase(
            case_id=example.example_id,
            messages=example.messages,
            tools=example.tools,
            gold_labels=example.labels,
        )
        for example in selected
    ]
    predictions = [
        EvaluationPrediction(
            intent=case.gold_labels.intent.value,
            extracted_requirement=case.gold_labels.extracted_requirement.model_dump(
                exclude_none=True
            ),
            missing_fields=case.gold_labels.missing_fields,
            tool_calls=[ToolCall(id=str(index), name=call.name, arguments=call.arguments)
                        for index, call in enumerate(case.gold_labels.expected_tool_calls)],
            total_product_claims=1,
            abstained=(case.gold_labels.scenario_type.value == "no_product_found"),
        )
        for case in cases
    ]

    report = evaluate_predictions(cases, predictions)

    assert report.intent_accuracy == 1.0
    assert report.field_extraction_f1 == 1.0
    assert report.missing_fields_exact_match == 1.0
    assert report.tool_needed_accuracy == 1.0
    assert report.tool_name_accuracy == 1.0
    assert report.tool_argument_validity == 1.0
    assert report.structured_output_validity == 0.0  # No case requires structured output.
    assert report.unsupported_product_claim_rate == 0.0
    assert report.abstention_accuracy == 1.0


def test_evaluation_rejects_prediction_count_mismatch() -> None:
    try:
        evaluate_predictions([], [EvaluationPrediction()])
    except ValueError as error:
        assert "Số dự đoán" in str(error)
    else:
        raise AssertionError("Expected a prediction count validation error")
