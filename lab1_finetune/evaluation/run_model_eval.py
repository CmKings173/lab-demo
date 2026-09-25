"""Teacher-forced model evaluation over the frozen independent benchmark.

Each gold assistant turn is a separate decision. The model receives only the
prefix before that turn; subsequent tool results come from the benchmark, not
from live Lab 2 services. This deliberately measures decisions under gold
history, not an autonomous end-to-end agent trajectory.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Protocol

from lab1_finetune.data.schema import ExpectedToolCall
from lab1_finetune.evaluation.model import VLLMModelClient
from lab1_finetune.evaluation.schema import EvaluationCase
from shared.contracts import ChatMessage, ModelResponse, ToolCall, ToolDefinition
from shared.contracts.models import ContractModel
from shared.tool_args import TOOL_ARG_MODELS

BENCHMARK_PATH = Path(__file__).with_name("gold_eval.jsonl")
_ABSTENTION_PHRASES = (
    "không đủ bằng chứng",
    "chưa đủ bằng chứng",
    "không thể xác minh",
    "chưa thể xác minh",
    "không thể xác nhận",
    "chưa thể xác nhận",
    "không thuộc phạm vi",
    "không có dữ liệu",
    "không nên khẳng định",
    "chưa thể khẳng định khả thi",
    "quyết định cuối cùng cần đối chiếu thêm",
    "ngoài phạm vi",
)

# Retrieval phrasing and output sizing are operational controls, not business
# requirements. Keep this allowlist limited to values that change the requested
# product, capacity, workload, or configuration identity.
_CRITICAL_ARGUMENT_PATHS = {
    "search_products": (
        "filters.min_ram_gb",
        "filters.min_gpu_count",
        "filters.max_base_price_vnd",
        "filters.product_type",
    ),
    "get_product": ("product_id",),
    "search_product_documents": ("product_id",),
    "compare_products": ("product_ids",),
    "compare_configurations": ("configuration_ids",),
    "estimate_ai_requirements": (
        "model_parameters_b",
        "usage",
        "context_length",
        "concurrent_users",
        "training_method",
    ),
}

_ARGUMENT_METRIC_DEFINITIONS = {
    "tool_argument_accuracy": (
        "Existing metric retained unchanged: Pydantic-validated model dumps compared "
        "in tool-call order."
    ),
    "tool_argument_contract_normalized_accuracy": (
        "Pydantic-validated arguments compared after applying declared defaults and "
        "treating blank optional strings as null; tool-call order is ignored."
    ),
    "tool_argument_critical_field_accuracy": (
        "Case-level exact agreement on all present allowlisted business-critical "
        "argument paths; retrieval query wording, top_k, and limit are excluded."
    ),
}


class ModelClient(Protocol):
    model_name: str

    def complete(
        self, messages: list[ChatMessage], tools: list[ToolDefinition]
    ) -> ModelResponse: ...


def _detect_abstention(content: str) -> bool:
    """A transparent lexical proxy, not a factual or semantic judge."""
    lowered = content.lower()
    return any(phrase in lowered for phrase in _ABSTENTION_PHRASES)


def _normalized_calls(calls: list) -> list[tuple[str, dict]]:
    return [
        (call.name, TOOL_ARG_MODELS[call.name].model_validate(call.arguments).model_dump())
        for call in calls
    ]


def _normalized_contract_model(instance: ContractModel) -> dict:
    """Serialize a validated contract with only contract-sanctioned equivalences."""
    normalized = {}
    for field_name, field in type(instance).model_fields.items():
        value = getattr(instance, field_name)
        if isinstance(value, ContractModel):
            value = _normalized_contract_model(value)
        elif isinstance(value, Enum):
            value = value.value
        elif isinstance(value, str) and value == "" and field.default is None:
            # Blank is equivalent to missing only for fields whose contract says
            # missing defaults to null. Non-empty user values remain untouched.
            value = None
        elif isinstance(value, dict):
            value = {key: _normalized_leaf(item) for key, item in value.items()}
        elif isinstance(value, (list, tuple)):
            value = [_normalized_leaf(item) for item in value]
        elif isinstance(value, set):
            value = sorted((_normalized_leaf(item) for item in value), key=str)
        else:
            value = _normalized_leaf(value)
        normalized[field_name] = value
    return normalized


def _normalized_leaf(value):
    if isinstance(value, ContractModel):
        return _normalized_contract_model(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _normalized_leaf(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalized_leaf(item) for item in value]
    if isinstance(value, set):
        return sorted((_normalized_leaf(item) for item in value), key=str)
    return value


def _contract_normalized_calls(calls: list) -> list[tuple[str, dict]]:
    normalized = []
    for call in calls:
        model = TOOL_ARG_MODELS[call.name]
        parsed = model.model_validate(call.arguments)
        normalized.append((call.name, _normalized_contract_model(parsed)))
    # Sequence correctness has its own metric; compare argument payloads by tool
    # and canonical payload instead of charging an ordering error twice.
    return sorted(
        normalized,
        key=lambda item: (item[0], json.dumps(item[1], sort_keys=True, ensure_ascii=False)),
    )


def _critical_projection(name: str, arguments: dict) -> dict[str, object]:
    model = TOOL_ARG_MODELS.get(name)
    if model is None:
        return {}
    try:
        parsed = model.model_validate(arguments)
        values = _normalized_contract_model(parsed)
    except (TypeError, ValueError):
        # A non-critical invalid field should not erase otherwise inspectable
        # critical values. Those raw values will still be compared exactly.
        values = arguments
    projection = {}
    for path in _CRITICAL_ARGUMENT_PATHS.get(name, ()):
        current = values
        for part in path.split("."):
            current = current.get(part) if isinstance(current, dict) else None
        projection[path] = current
    return projection


def _critical_argument_accuracy(actual: list, expected: list) -> tuple[bool | None, list[str]]:
    actual_by_name: dict[str, list] = {}
    expected_by_name: dict[str, list] = {}
    for call in actual:
        actual_by_name.setdefault(call.name, []).append(call.arguments)
    for call in expected:
        expected_by_name.setdefault(call.name, []).append(call.arguments)

    mismatches: list[str] = []
    has_critical_value = False
    for name in sorted(set(actual_by_name) | set(expected_by_name)):
        paths = _CRITICAL_ARGUMENT_PATHS.get(name, ())
        if not paths:
            continue
        actual_args = actual_by_name.get(name, [])
        expected_args = expected_by_name.get(name, [])
        for index in range(max(len(actual_args), len(expected_args))):
            actual_projection = (
                _critical_projection(name, actual_args[index])
                if index < len(actual_args) else {}
            )
            expected_projection = (
                _critical_projection(name, expected_args[index])
                if index < len(expected_args) else {}
            )
            for path in paths:
                actual_value = actual_projection.get(path)
                expected_value = expected_projection.get(path)
                if actual_value is not None or expected_value is not None:
                    has_critical_value = True
                if actual_value != expected_value:
                    mismatches.append(f"{name}.{path}")
                    has_critical_value = True
    if not has_critical_value:
        return None, []
    return not mismatches, mismatches


def _argument_metrics(actual: list, expected: list) -> tuple[dict[str, bool | None], list[str]]:
    if not expected:
        return {
            "tool_argument_accuracy": None,
            "tool_argument_contract_normalized_accuracy": None,
            "tool_argument_critical_field_accuracy": None,
        }, []
    try:
        # Preserve the established exact metric's behavior and name.
        exact_match = _normalized_calls(actual) == _normalized_calls(expected)
    except (ValueError, KeyError, TypeError):
        exact_match = False
    try:
        contract_match = _contract_normalized_calls(actual) == _contract_normalized_calls(
            expected
        )
    except (ValueError, KeyError, TypeError):
        contract_match = False
    critical_match, categories = _critical_argument_accuracy(actual, expected)
    return {
        "tool_argument_accuracy": exact_match,
        "tool_argument_contract_normalized_accuracy": contract_match,
        "tool_argument_critical_field_accuracy": critical_match,
    }, categories


def _case_metrics(
    case: EvaluationCase, predictions: list[ModelResponse]
) -> tuple[dict[str, bool | None], list[str]]:
    actual = [call for response in predictions for call in response.message.tool_calls]
    expected = case.gold_labels.expected_tool_calls
    actual_names = [call.name for call in actual]
    expected_names = [call.name for call in expected]
    current_user = max(index for index, message in enumerate(case.messages)
                       if message.role == "user")
    gold_turns = [message for message in case.messages[current_user + 1:]
                  if message.role == "assistant"]
    actual_by_turn = [[call.name for call in response.message.tool_calls]
                      for response in predictions]
    expected_by_turn = [[call.name for call in message.tool_calls]
                        for message in gold_turns]
    argument_metrics, critical_mismatches = _argument_metrics(actual, expected)
    abstained = _detect_abstention(predictions[-1].message.content or "")
    return {
        "tool_call_required_accuracy": (
            [bool(names) for names in actual_by_turn]
            == [bool(names) for names in expected_by_turn]
        ),
        "tool_name_accuracy": (
            Counter(actual_names) == Counter(expected_names) if expected else None
        ),
        "tool_call_sequence_accuracy": (
            actual_by_turn == expected_by_turn if len(expected) > 1 else None
        ),
        "abstention_accuracy": abstained == case.gold_labels.should_abstain,
        "unexpected_tool_call_rate": bool(Counter(actual_names) - Counter(expected_names)),
        "missing_tool_call_rate": bool(Counter(expected_names) - Counter(actual_names)),
        **argument_metrics,
    }, critical_mismatches


def evaluate_case(case: EvaluationCase, client: ModelClient) -> dict:
    """Predict each post-user assistant turn without showing its gold continuation."""
    user_indices = [index for index, message in enumerate(case.messages) if message.role == "user"]
    if not user_indices:
        raise ValueError(f"{case.case_id}: no user message")
    current_user = user_indices[-1]
    decision_indices = [
        index for index in range(current_user + 1, len(case.messages))
        if case.messages[index].role == "assistant"
    ]
    if not decision_indices or decision_indices[-1] != len(case.messages) - 1:
        raise ValueError(f"{case.case_id}: no final assistant turn")
    responses: list[ModelResponse] = []
    inputs: list[list[dict]] = []
    for index in decision_indices:
        prefix = case.messages[:index]
        inputs.append([message.model_dump(mode="json") for message in prefix])
        responses.append(client.complete(prefix, case.tools))
    metrics, critical_mismatches = _case_metrics(case, responses)
    return {
        "case_id": case.case_id,
        "model_name": client.model_name,
        "input_messages": inputs[0],
        "decision_inputs": inputs,
        "gold_labels": case.gold_labels.model_dump(mode="json"),
        "predicted_assistant_content": responses[-1].message.content,
        "predicted_tool_calls": [
            call.model_dump(mode="json") for response in responses
            for call in response.message.tool_calls
        ],
        "decision_outputs": [response.model_dump(mode="json") for response in responses],
        "metrics": metrics,
        "critical_argument_mismatches": critical_mismatches,
        "error": None,
    }


def _aggregate(results: list[dict]) -> dict[str, dict[str, float | int]]:
    names = (
        "tool_call_required_accuracy", "tool_name_accuracy", "tool_argument_accuracy",
        "tool_argument_contract_normalized_accuracy",
        "tool_argument_critical_field_accuracy",
        "tool_call_sequence_accuracy", "abstention_accuracy", "unexpected_tool_call_rate",
        "missing_tool_call_rate",
    )
    metrics = {}
    for name in names:
        values = [item.get("metrics", {}).get(name) for item in results
                  if item.get("error") is None
                  and item.get("metrics", {}).get(name) is not None]
        metrics[name] = {"value": sum(values) / len(values) if values else None,
                         "count": len(values)}
    return metrics


def _critical_mismatch_counts(results: list[dict]) -> list[dict[str, str | int]]:
    counts = Counter(
        category
        for item in results if item.get("error") is None
        for category in item.get("critical_argument_mismatches", [])
    )
    return [
        {"category": category, "count": count}
        for category, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def rescore_report(report: dict) -> dict:
    """Recompute argument metrics from a saved report without contacting a model."""
    rescored = copy.deepcopy(report)
    cases = rescored.get("cases")
    if not isinstance(cases, list):
        raise ValueError("saved evaluation report must contain a cases list")
    for item in cases:
        if not isinstance(item, dict):
            raise ValueError("saved evaluation report contains a malformed case")
        if item.get("error") is not None:
            item.setdefault("metrics", {}).update({
                "tool_argument_accuracy": None,
                "tool_argument_contract_normalized_accuracy": None,
                "tool_argument_critical_field_accuracy": None,
            })
            item["critical_argument_mismatches"] = []
            continue
        gold = item.get("gold_labels")
        if not isinstance(gold, dict):
            raise ValueError(f"{item.get('case_id', '<unknown>')}: missing gold_labels")
        actual_calls = [ToolCall.model_validate(call)
                        for call in item.get("predicted_tool_calls", [])]
        expected_calls = [ExpectedToolCall.model_validate(call)
                          for call in gold.get("expected_tool_calls", [])]
        scores, categories = _argument_metrics(actual_calls, expected_calls)
        item.setdefault("metrics", {}).update(scores)
        item["critical_argument_mismatches"] = categories
    rescored["metrics"] = {**rescored.get("metrics", {}), **_aggregate(cases)}
    rescored["critical_argument_mismatch_categories"] = _critical_mismatch_counts(cases)
    rescored["argument_metric_definitions"] = _ARGUMENT_METRIC_DEFINITIONS
    return rescored


def run_evaluation(
    cases: list[EvaluationCase], client: ModelClient, *, output: Path,
    benchmark_hash: str,
) -> dict:
    results = []
    for case in cases:
        try:
            results.append(evaluate_case(case, client))
        except Exception as exc:
            # A malformed response or transport failure affects one case, not the run.
            results.append({
                "case_id": case.case_id,
                "model_name": client.model_name,
                "input_messages": [message.model_dump(mode="json") for message in case.messages
                                   if message.role in {"system", "user"}],
                "gold_labels": case.gold_labels.model_dump(mode="json"),
                "predicted_assistant_content": None,
                "predicted_tool_calls": [],
                "metrics": {},
                "error": f"{type(exc).__name__}: {exc}",
            })
    report = {
        "model_name": client.model_name,
        "benchmark_hash": benchmark_hash,
        "evaluation_config": {
            "temperature": getattr(client, "temperature", None),
            "max_tokens": getattr(client, "max_tokens", None),
            "enable_thinking": getattr(client, "enable_thinking", None),
            "method": "teacher_forced_gold_tool_results",
        },
        "total_cases": len(results),
        "successful_cases": sum(item["error"] is None for item in results),
        "failed_cases": sum(item["error"] is not None for item in results),
        "metric_scope": "successful cases only; see count per metric and failed_cases",
        "abstention_method": "conservative Vietnamese phrase match; not a semantic judge",
        "argument_metric_definitions": _ARGUMENT_METRIC_DEFINITIONS,
        "metrics": _aggregate(results),
        "critical_argument_mismatch_categories": _critical_mismatch_counts(results),
        "cases": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _load_benchmark(path: Path) -> tuple[list[EvaluationCase], str]:
    raw = path.read_bytes()
    cases = [EvaluationCase.model_validate_json(line) for line in raw.splitlines() if line.strip()]
    if not cases:
        raise ValueError("benchmark is empty")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("benchmark has duplicate case IDs")
    return cases, hashlib.sha256(raw).hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_PATH)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--enable-thinking", action="store_true")
    args = parser.parse_args(argv)
    if args.output.resolve() in {
        args.benchmark.resolve(),
        BENCHMARK_PATH.with_name("eval_manifest.json").resolve(),
    }:
        parser.error("--output must not overwrite a frozen benchmark artifact")
    cases, benchmark_hash = _load_benchmark(args.benchmark)
    client = VLLMModelClient(
        base_url=args.base_url, model_name=args.model,
        api_key=os.environ.get("LAB1_EVAL_API_KEY"), timeout=args.timeout,
        max_tokens=args.max_tokens, enable_thinking=args.enable_thinking,
    )
    client.check_ready()
    report = run_evaluation(cases, client, output=args.output, benchmark_hash=benchmark_hash)
    print(json.dumps({key: report[key] for key in (
        "model_name", "benchmark_hash", "total_cases", "successful_cases", "failed_cases",
        "metrics",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
