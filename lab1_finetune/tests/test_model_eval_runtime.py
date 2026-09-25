"""Contract tests for the offline vLLM-backed evaluation path."""

import json
from urllib.error import HTTPError, URLError

import pytest

from lab1_finetune.evaluation.model import ModelEvaluationError, VLLMModelClient
from shared.contracts import ChatMessage, ToolDefinition


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _client(monkeypatch, response: dict):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _Response(response)

    monkeypatch.setattr("lab1_finetune.evaluation.model.urlopen", fake_urlopen)
    return VLLMModelClient(
        base_url="http://127.0.0.1:8000/v1/",
        model_name="base",
        api_key="private-test-key",
        timeout=12,
    ), captured


def test_vllm_client_sends_openai_messages_tools_and_parses_text(monkeypatch) -> None:
    client, captured = _client(
        monkeypatch,
        {"choices": [{"message": {"role": "assistant", "content": "Xin chào"},
                      "finish_reason": "stop"}]},
    )
    tools = [ToolDefinition(name="get_product", description="Get product",
                            parameters={"type": "object", "properties": {}})]
    result = client.complete([ChatMessage(role="user", content="Hi")], tools)

    assert captured["url"] == "http://127.0.0.1:8000/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer private-test-key"
    assert captured["timeout"] == 12
    assert captured["body"]["messages"] == [{"role": "user", "content": "Hi"}]
    assert captured["body"]["tools"] == [{"type": "function", "function": {
        "name": "get_product", "description": "Get product",
        "parameters": {"type": "object", "properties": {}}}}]
    assert captured["body"]["tool_choice"] == "auto"
    assert captured["body"]["temperature"] == 0
    assert result.message.content == "Xin chào"
    assert result.message.tool_calls == []


def test_vllm_client_parses_multiple_tool_calls_and_history(monkeypatch) -> None:
    client, captured = _client(monkeypatch, {"choices": [{"message": {
        "role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "get_product", "arguments": '{"product_id":"P1"}'}},
            {"id": "c2", "type": "function", "function": {
                "name": "get_product", "arguments": '{"product_id":"P2"}'}},
        ]}, "finish_reason": "tool_calls"}]})
    result = client.complete([
        ChatMessage(role="assistant", tool_calls=[
            {"id": "old", "name": "get_product", "arguments": {"product_id": "P0"}}]),
        ChatMessage(role="tool", tool_call_id="old", content='{"ok":true}'),
    ])

    assert [call.name for call in result.message.tool_calls] == ["get_product"] * 2
    assert [call.arguments for call in result.message.tool_calls] == [
        {"product_id": "P1"}, {"product_id": "P2"}]
    assert captured["body"]["messages"][0]["tool_calls"][0]["function"]["arguments"] == (
        '{"product_id": "P0"}'
    )
    assert captured["body"]["messages"][1]["tool_call_id"] == "old"


@pytest.mark.parametrize("arguments", ["{bad", "[]", "null"])
def test_vllm_client_rejects_invalid_tool_arguments(monkeypatch, arguments) -> None:
    client, _ = _client(monkeypatch, {"choices": [{"message": {
        "role": "assistant", "tool_calls": [{"id": "c1", "function": {
            "name": "get_product", "arguments": arguments}}]}}]})
    with pytest.raises(ModelEvaluationError, match="arguments"):
        client.complete([ChatMessage(role="user", content="Get P1")])


@pytest.mark.parametrize("failure", [HTTPError("url", 500, "boom", {}, None),
                                      URLError("connection refused"), TimeoutError()])
def test_vllm_client_reports_http_and_timeout_errors(monkeypatch, failure) -> None:
    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr("lab1_finetune.evaluation.model.urlopen", fail)
    client = VLLMModelClient(base_url="http://127.0.0.1:8000/v1", model_name="base")
    with pytest.raises(ModelEvaluationError):
        client.complete([ChatMessage(role="user", content="Hi")])


def test_vllm_client_rejects_malformed_response(monkeypatch) -> None:
    client, _ = _client(monkeypatch, {"choices": [{"message": {"role": "assistant",
                                                       "tool_calls": [{"id": "c1", "function": {
                                                           "arguments": "{}"}}]}}]})
    with pytest.raises(ModelEvaluationError, match="name"):
        client.complete([ChatMessage(role="user", content="Hi")])


def test_vllm_client_preflight_confirms_configured_model(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _Response({"data": [{"id": "base"}, {"id": "lora"}]})

    monkeypatch.setattr("lab1_finetune.evaluation.model.urlopen", fake_urlopen)
    client = VLLMModelClient(base_url="http://127.0.0.1:8000/v1", model_name="lora")
    client.check_ready()
    assert requests[0].full_url == "http://127.0.0.1:8000/v1/models"
    assert requests[0].get_method() == "GET"


def test_vllm_client_preflight_rejects_missing_model(monkeypatch) -> None:
    monkeypatch.setattr("lab1_finetune.evaluation.model.urlopen",
                        lambda request, timeout: _Response({"data": [{"id": "base"}]}))
    client = VLLMModelClient(base_url="http://127.0.0.1:8000/v1", model_name="lora")
    with pytest.raises(ModelEvaluationError, match="not served"):
        client.check_ready()
