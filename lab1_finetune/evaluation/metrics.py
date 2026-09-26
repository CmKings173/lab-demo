import json

from pydantic import BaseModel

from lab1_finetune.data.frozen_contracts import TOOL_ARG_MODELS, CustomerRequirement
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


def _normalized(calls):
    return [(call.name, TOOL_ARG_MODELS[call.name].model_validate(call.arguments).model_dump())
            for call in calls]


def _structured_valid(value) -> bool:
    try:
        CustomerRequirement.model_validate(json.loads(value) if isinstance(value, str) else value)
        return True
    except (ValueError, TypeError):
        return False


def evaluate_predictions(
    cases: list[EvaluationCase], predictions: list[EvaluationPrediction]
) -> EvaluationMetrics:
    if len(cases) != len(predictions):
        raise ValueError("Số dự đoán phải bằng số ca đánh giá.")
    pairs = list(zip(cases, predictions, strict=True))
    extraction = extraction_scores(
        [case.gold_labels.extracted_requirement.model_dump(exclude_none=True) for case in cases],
        [prediction.extracted_requirement for prediction in predictions],
    )
    tool_pairs = [(case, pred) for case, pred in pairs if case.gold_labels.should_call_tool]
    schema, exact, semantic, names = [], [], [], []
    for case, pred in tool_pairs:
        expected = case.gold_labels.expected_tool_calls
        names.append([call.name for call in pred.tool_calls] == [call.name for call in expected])
        exact.append([(call.name, call.arguments) for call in pred.tool_calls] ==
                     [(call.name, call.arguments) for call in expected])
        try:
            actual = _normalized(pred.tool_calls)
            schema.append(bool(pred.tool_calls))
            semantic.append(actual == _normalized(expected))
        except (ValueError, KeyError):
            schema.append(False)
            semantic.append(False)
    return EvaluationMetrics(
        intent_accuracy=accuracy(
            [pred.intent == case.gold_labels.intent.value for case, pred in pairs]
        ),
        field_extraction_precision=extraction.precision,
        field_extraction_recall=extraction.recall,
        field_extraction_f1=extraction.f1,
        missing_fields_exact_match=accuracy([
            set(pred.missing_fields) == set(case.gold_labels.missing_fields)
            for case, pred in pairs if case.gold_labels.intent.value == "solution_design"]),
        tool_needed_accuracy=accuracy([
            bool(pred.tool_calls) == case.gold_labels.should_call_tool for case, pred in pairs]),
        tool_name_accuracy=accuracy(names),
        tool_sequence_accuracy=accuracy(names),
        tool_argument_validity=accuracy(schema),
        tool_argument_schema_validity=accuracy(schema),
        tool_argument_exact_match=accuracy(exact),
        tool_argument_semantic_match=accuracy(semantic),
        structured_output_validity=accuracy([
            _structured_valid(pred.structured_output)
            for case, pred in pairs if case.gold_labels.expects_structured_output]),
        unsupported_product_claim_rate=unsupported_product_claim_rate(
            unsupported=sum(pred.unsupported_product_claims for pred in predictions),
            total_claims=sum(pred.total_product_claims for pred in predictions)),
        abstention_accuracy=accuracy([
            pred.abstained == case.gold_labels.should_abstain for case, pred in pairs]),
    )
