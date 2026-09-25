"""Teacher-forced evaluation never exposes future gold assistant turns."""

import json

from lab1_finetune.data.schema import DatasetLabels, ExpectedToolCall, Intent, ScenarioType
from lab1_finetune.evaluation.compare_results import compare_reports
from lab1_finetune.evaluation.run_model_eval import (
    BENCHMARK_PATH,
    _detect_abstention,
    _load_benchmark,
    evaluate_case,
    run_evaluation,
)
from lab1_finetune.evaluation.schema import EvaluationCase
from shared.contracts import ChatMessage, CustomerRequirement, ModelResponse, ToolCall


class _FakeClient:
    model_name = "test-model"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.inputs = []

    def complete(self, messages, tools=()):
        self.inputs.append(list(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def _case(case_id="case-1"):
    return EvaluationCase(
        case_id=case_id,
        messages=[
            ChatMessage(role="system", content="Follow evidence."),
            ChatMessage(role="user", content="Find P1"),
            ChatMessage(role="assistant", tool_calls=[ToolCall(
                id="gold-call", name="get_product", arguments={"product_id": "P1"})]),
            ChatMessage(role="tool", tool_call_id="gold-call", content='{"ok":true}'),
            ChatMessage(role="assistant", content="Gold final answer"),
        ],
        gold_labels=DatasetLabels(
            intent=Intent.PRODUCT_SEARCH,
            scenario_type=ScenarioType.SEARCH_PRODUCT_BY_BUDGET,
            extracted_requirement=CustomerRequirement(),
            should_call_tool=True,
            expected_tool_calls=[ExpectedToolCall(
                name="get_product", arguments={"product_id": "P1"})],
        ),
    )


def _response(content=None, calls=None):
    return ModelResponse(message=ChatMessage(role="assistant", content=content,
                                              tool_calls=calls or []))


def test_evaluation_teacher_forces_fixture_without_leaking_gold_answer() -> None:
    client = _FakeClient([
        _response(calls=[ToolCall(id="prediction", name="get_product",
                                  arguments={"product_id": "P1"})]),
        _response(content="Predicted final answer"),
    ])
    result = evaluate_case(_case(), client)

    assert len(client.inputs) == 2
    assert [message.role for message in client.inputs[0]] == ["system", "user"]
    assert [message.role for message in client.inputs[1]] == [
        "system", "user", "assistant", "tool"]
    assert result["predicted_assistant_content"] == "Predicted final answer"
    assert result["predicted_tool_calls"][0]["arguments"] == {"product_id": "P1"}
    assert result["metrics"]["tool_call_required_accuracy"] is True
    assert result["metrics"]["tool_argument_accuracy"] is True
    assert result["metrics"]["tool_call_sequence_accuracy"] is None  # single-tool case
    assert "Gold final answer" not in json.dumps(result["input_messages"])


def test_evaluation_records_case_failure_and_continues(tmp_path) -> None:
    client = _FakeClient([RuntimeError("bad response"), _response(content="Safe answer")])
    output = tmp_path / "result.json"
    second = _case("case-2")
    second.messages = [ChatMessage(role="user", content="Explain"),
                       ChatMessage(role="assistant", content="Gold")]
    second.gold_labels.expected_tool_calls = []
    second.gold_labels.should_call_tool = False
    report = run_evaluation([_case(), second], client, output=output,
                            benchmark_hash="frozen-hash")

    assert report["failed_cases"] == 1
    assert report["successful_cases"] == 1
    assert report["cases"][0]["error"] == "RuntimeError: bad response"
    assert report["cases"][1]["predicted_assistant_content"] == "Safe answer"
    assert json.loads(output.read_text(encoding="utf-8"))["benchmark_hash"] == "frozen-hash"


def test_comparison_requires_same_benchmark_and_reports_deltas() -> None:
    base = {"benchmark_hash": "same", "total_cases": 2,
            "metrics": {"tool_name_accuracy": {"value": 0.5, "count": 2}}}
    candidate = {"benchmark_hash": "same", "total_cases": 2,
                 "metrics": {"tool_name_accuracy": {"value": 1.0, "count": 2}}}
    result = compare_reports(base, candidate)
    assert result["metrics"]["tool_name_accuracy"] == {
        "base": 0.5, "candidate": 1.0, "delta": 0.5,
        "base_count": 2, "candidate_count": 2}


def test_comparison_rejects_different_benchmark() -> None:
    try:
        compare_reports({"benchmark_hash": "a", "total_cases": 1, "metrics": {}},
                        {"benchmark_hash": "b", "total_cases": 1, "metrics": {}})
    except ValueError as exc:
        assert "benchmark" in str(exc)
    else:
        raise AssertionError("different benchmark must be rejected")


def test_multi_tool_sequence_is_scored_separately_from_tool_name_set() -> None:
    cases, _ = _load_benchmark(BENCHMARK_PATH)
    case = cases[50]  # Frozen eval_multi_tool fixture: search → get → document.
    expected = case.gold_labels.expected_tool_calls
    assert len(expected) == 3
    responses = [
        _response(calls=[ToolCall(
            id=f"pred-{index}", name=call.name, arguments=call.arguments)])
        for index, call in enumerate(reversed(expected))
    ] + [_response(content="Answer")]
    result = evaluate_case(case, _FakeClient(responses))
    assert result["metrics"]["tool_name_accuracy"] is True
    assert result["metrics"]["tool_call_sequence_accuracy"] is False
    assert result["metrics"]["tool_argument_accuracy"] is False


def test_tool_call_on_wrong_assistant_turn_does_not_count_as_correct() -> None:
    client = _FakeClient([
        _response(content="I will not call a tool yet"),
        _response(calls=[ToolCall(id="late", name="get_product",
                                  arguments={"product_id": "P1"})]),
    ])
    result = evaluate_case(_case(), client)
    assert result["metrics"]["tool_name_accuracy"] is True
    assert result["metrics"]["tool_argument_accuracy"] is True
    assert result["metrics"]["tool_call_required_accuracy"] is False


def test_comparison_rejects_different_decoding_configuration() -> None:
    base = {"benchmark_hash": "same", "total_cases": 1, "metrics": {},
            "evaluation_config": {"temperature": 0}}
    candidate = {**base, "evaluation_config": {"temperature": 0.7}}
    try:
        compare_reports(base, candidate)
    except ValueError as exc:
        assert "configurations" in str(exc)
    else:
        raise AssertionError("unequal decoding settings must be rejected")


def test_abstention_proxy_agrees_with_all_frozen_gold_finals() -> None:
    cases, _ = _load_benchmark(BENCHMARK_PATH)
    assert len(cases) == 120
    assert all(_detect_abstention(case.messages[-1].content or "")
               == case.gold_labels.should_abstain for case in cases)
