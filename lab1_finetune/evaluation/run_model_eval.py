"""Teacher-forced model evaluation over the frozen independent benchmark.

Each gold assistant turn is a separate decision. The model receives only the
prefix before that turn; subsequent tool results come from the benchmark, not
from live Lab 2 services. This deliberately measures decisions under gold
history, not an autonomous end-to-end agent trajectory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Protocol

from lab1_finetune.data.frozen_contracts import TOOL_ARG_MODELS
from lab1_finetune.evaluation.model import VLLMModelClient
from lab1_finetune.evaluation.schema import EvaluationCase
from shared.contracts import ChatMessage, ModelResponse, ToolDefinition

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


def _case_metrics(case: EvaluationCase, predictions: list[ModelResponse]) -> dict[str, bool | None]:
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
    try:
        arguments_match = _normalized_calls(actual) == _normalized_calls(expected)
    except (ValueError, KeyError):
        arguments_match = False
    abstained = _detect_abstention(predictions[-1].message.content or "")
    return {
        "tool_call_required_accuracy": (
            [bool(names) for names in actual_by_turn]
            == [bool(names) for names in expected_by_turn]
        ),
        "tool_name_accuracy": (
            Counter(actual_names) == Counter(expected_names) if expected else None
        ),
        "tool_argument_accuracy": arguments_match if expected else None,
        "tool_call_sequence_accuracy": (
            actual_by_turn == expected_by_turn if len(expected) > 1 else None
        ),
        "abstention_accuracy": abstained == case.gold_labels.should_abstain,
        "unexpected_tool_call_rate": bool(Counter(actual_names) - Counter(expected_names)),
        "missing_tool_call_rate": bool(Counter(expected_names) - Counter(actual_names)),
    }


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
        "metrics": _case_metrics(case, responses),
        "error": None,
    }


def _aggregate(results: list[dict]) -> dict[str, dict[str, float | int]]:
    names = (
        "tool_call_required_accuracy", "tool_name_accuracy", "tool_argument_accuracy",
        "tool_call_sequence_accuracy", "abstention_accuracy", "unexpected_tool_call_rate",
        "missing_tool_call_rate",
    )
    metrics = {}
    for name in names:
        values = [item["metrics"][name] for item in results if item["error"] is None
                  and item["metrics"][name] is not None]
        metrics[name] = {"value": sum(values) / len(values) if values else None,
                         "count": len(values)}
    return metrics


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
        "metrics": _aggregate(results),
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
