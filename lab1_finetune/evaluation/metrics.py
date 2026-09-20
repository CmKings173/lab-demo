from pydantic import BaseModel

from lab1_finetune.data.schema import ScenarioType
from lab1_finetune.evaluation.schema import (
    EvaluationCase,
    EvaluationMetrics,
    EvaluationPrediction,
)


class ExtractionScores(BaseModel):
    precision: float
    recall: float
    f1: float


def accuracy(matches: list[bool]) -> float:
    return sum(matches) / len(matches) if matches else 0.0


def extraction_scores(
    gold: list[dict[str, object]], predicted: list[dict[str, object]]
) -> ExtractionScores:
    true_positive = false_positive = false_negative = 0
    for expected, actual in zip(gold, predicted, strict=True):
        expected_items = set(expected.items())
        actual_items = set(actual.items())
        true_positive += len(expected_items & actual_items)
        false_positive += len(actual_items - expected_items)
        false_negative += len(expected_items - actual_items)
    precision = true_positive / (true_positive + false_positive) if true_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return ExtractionScores(precision=precision, recall=recall, f1=f1)


def unsupported_product_claim_rate(*, unsupported: int, total_claims: int) -> float:
    return unsupported / total_claims if total_claims else 0.0


ABSTENTION_SCENARIOS = {
    ScenarioType.CONTRADICTORY_REQUIREMENT,
    ScenarioType.NO_PRODUCT_FOUND,
    ScenarioType.UNKNOWN_PRODUCT_SPEC,
    ScenarioType.TOOL_FAILURE,
    ScenarioType.OUT_SCOPE_LAPTOP,
    ScenarioType.OUT_SCOPE_NETWORK_SWITCH,
}


def evaluate_predictions(
    cases: list[EvaluationCase], predictions: list[EvaluationPrediction]
) -> EvaluationMetrics:
    if len(cases) != len(predictions):
        raise ValueError("Số dự đoán phải bằng số ca đánh giá.")

    extraction = extraction_scores(
        [
            case.gold_labels.extracted_requirement.model_dump(exclude_none=True)
            for case in cases
        ],
        [prediction.extracted_requirement for prediction in predictions],
    )
    expected_tool_cases = [
        (case, prediction)
        for case, prediction in zip(cases, predictions, strict=True)
        if case.gold_labels.should_call_tool
    ]
    unsupported = sum(prediction.unsupported_product_claims for prediction in predictions)
    total_claims = sum(prediction.total_product_claims for prediction in predictions)

    return EvaluationMetrics(
        intent_accuracy=accuracy(
            [
                prediction.intent == case.gold_labels.intent.value
                for case, prediction in zip(cases, predictions, strict=True)
            ]
        ),
        field_extraction_precision=extraction.precision,
        field_extraction_recall=extraction.recall,
        field_extraction_f1=extraction.f1,
        missing_fields_exact_match=accuracy(
            [
                set(prediction.missing_fields) == set(case.gold_labels.missing_fields)
                for case, prediction in zip(cases, predictions, strict=True)
            ]
        ),
        tool_needed_accuracy=accuracy(
            [
                (prediction.tool_name is not None) == case.gold_labels.should_call_tool
                for case, prediction in zip(cases, predictions, strict=True)
            ]
        ),
        tool_name_accuracy=accuracy(
            [
                prediction.tool_name == case.gold_labels.expected_tool
                for case, prediction in expected_tool_cases
            ]
        ),
        tool_argument_validity=accuracy(
            [prediction.tool_arguments_valid for _, prediction in expected_tool_cases]
        ),
        structured_output_validity=accuracy(
            [prediction.structured_output_valid for prediction in predictions]
        ),
        unsupported_product_claim_rate=unsupported_product_claim_rate(
            unsupported=unsupported, total_claims=total_claims
        ),
        abstention_accuracy=accuracy(
            [
                prediction.abstained
                == (case.gold_labels.scenario_type in ABSTENTION_SCENARIOS)
                for case, prediction in zip(cases, predictions, strict=True)
            ]
        ),
    )
