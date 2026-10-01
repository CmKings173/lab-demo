from __future__ import annotations

import json
import traceback

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from adapters.real.vllm_chat import VLLMChatClient, VLLMChatError
from lab3_workflow.runtime.settings import Lab3RuntimeSettings
from shared.contracts import ChatMessage, ToolDefinition

MODEL = "Qwen/Qwen3-14B"


@pytest.mark.parametrize("json_schema_enabled", [False, True])
def test_vllm_advisor_schema_is_opt_in_and_never_uses_tools(json_schema_enabled):
    seen = []
    schema = {"type": "object", "properties": {"reply": {"type": "string"}},
              "required": ["reply"], "additionalProperties": False}

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"reply":"hello"}'},
        }]})

    http = httpx.Client(transport=httpx.MockTransport(respond))
    client = VLLMChatClient(base_url="http://localhost:8001/v1", model=MODEL, http_client=http,
                            json_schema_enabled=json_schema_enabled)
    try:
        result = client.complete_structured(
            [ChatMessage(role="user", content="xin chào")],
            response_schema=schema, schema_name="lab3_advisor_turn",
        )
        assert result.message.content == '{"reply":"hello"}'
        if json_schema_enabled:
            assert seen[0]["response_format"] == {
                "type": "json_schema",
                "json_schema": {"name": "lab3_advisor_turn", "schema": schema},
            }
        else:
            assert "response_format" not in seen[0]
        assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False}
        assert "tools" not in seen[0]
    finally:
        client.close()
        http.close()


def test_vllm_complete_uses_openai_chat_shape_and_parses_assistant_message():
    seen = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "{\"model_size_b\":14}"},
                    }
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(respond))
    client = VLLMChatClient(
        base_url="http://localhost:8001/v1/",
        model=MODEL,
        api_key=SecretStr("local-test-token"),
        http_client=http,
    )
    try:
        response = client.complete(
            [ChatMessage(role="user", content="Need 14B inference")]
        )

        assert response.message.role == "assistant"
        assert response.message.content == '{"model_size_b":14}'
        assert response.finish_reason == "stop"
        assert len(seen) == 1
        assert str(seen[0].url) == "http://localhost:8001/v1/chat/completions"
        assert seen[0].headers["authorization"] == "Bearer local-test-token"
        body = json.loads(seen[0].content)
        assert body == {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Need 14B inference"}],
            "temperature": 0,
            "max_tokens": 1024,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    finally:
        client.close()
        assert not http.is_closed
        http.close()


def test_vllm_check_ready_reads_models_endpoint():
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "http://localhost:8001/v1/models"
        return httpx.Response(200, json={"data": [{"id": MODEL}]})

    http = httpx.Client(transport=httpx.MockTransport(respond))
    client = VLLMChatClient(base_url="http://localhost:8001/v1", model=MODEL, http_client=http)
    try:
        assert client.check_ready() is True
    finally:
        client.close()
        http.close()


def test_vllm_provider_failure_is_safe_and_suppresses_exception_chain():
    marker = "provider-body-secret-marker"

    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text=marker)

    client = VLLMChatClient(
        base_url="http://localhost:8001/v1",
        model=MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    try:
        with pytest.raises(VLLMChatError) as error:
            client.complete([ChatMessage(role="user", content="hello")])
        rendered = "".join(traceback.format_exception(error.value))
        assert error.value.code == "LLM_UNAVAILABLE"
        assert marker not in rendered
    finally:
        client.close()


def test_vllm_connection_error_maps_to_safe_unavailable_code():
    marker = "connection-secret-marker"

    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(marker, request=request)

    client = VLLMChatClient(
        base_url="http://localhost:8001/v1",
        model=MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    try:
        with pytest.raises(VLLMChatError) as error:
            client.complete([ChatMessage(role="user", content="hello")])
        rendered = "".join(traceback.format_exception(error.value))
        assert error.value.code == "LLM_UNAVAILABLE"
        assert marker not in rendered
    finally:
        client.close()


def test_vllm_invalid_provider_payload_uses_safe_error():
    client = VLLMChatClient(
        base_url="http://localhost:8001/v1",
        model=MODEL,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="not-json"))
        ),
    )
    try:
        with pytest.raises(VLLMChatError) as error:
            client.complete([ChatMessage(role="user", content="hello")])
        assert error.value.code == "LLM_INVALID_RESPONSE"
        assert "not-json" not in str(error.value)
    finally:
        client.close()


def test_vllm_rejects_tool_call_inputs_and_provider_tool_calls():
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{"id": "t1", "type": "function"}],
                        }
                    }
                ]
            },
        )

    client = VLLMChatClient(
        base_url="http://localhost:8001/v1",
        model=MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    try:
        with pytest.raises(VLLMChatError) as error:
            client.complete([ChatMessage(role="user", content="hello")])
        assert error.value.code == "LLM_INVALID_RESPONSE"
        with pytest.raises(VLLMChatError) as tools_error:
            client.complete(
                [ChatMessage(role="user", content="hello")],
                tools=[ToolDefinition(name="test", description="test", parameters={})],
            )
        assert tools_error.value.code == "LLM_INVALID_RESPONSE"
    finally:
        client.close()


def test_settings_load_required_qwen_endpoint_and_secret_key(monkeypatch):
    monkeypatch.setenv("LAB3_POSTGRES_DSN", "postgresql://operator:pw@db/catalog")
    monkeypatch.setenv("WEKNORA_BASE_URL", "https://weknora.example.invalid")
    monkeypatch.setenv("WEKNORA_API_KEY", "weknora-test-secret")
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "configured-kb")
    monkeypatch.setenv("LAB3_LLM_BASE_URL", "http://127.0.0.1:8001/v1/")
    monkeypatch.setenv("LAB3_LLM_MODEL", MODEL)
    monkeypatch.setenv("LAB3_LLM_API_KEY", "llm-test-secret")
    monkeypatch.delenv("LAB3_LLM_JSON_SCHEMA_ENABLED", raising=False)

    settings = Lab3RuntimeSettings.from_env(load_dotenv=False)

    assert settings.llm_base_url == "http://127.0.0.1:8001/v1"
    assert settings.llm_model == MODEL
    assert isinstance(settings.llm_api_key, SecretStr)
    assert "llm-test-secret" not in repr(settings)
    assert settings.llm_json_schema_enabled is False
    monkeypatch.setenv("LAB3_LLM_JSON_SCHEMA_ENABLED", "true")
    assert Lab3RuntimeSettings.from_env(load_dotenv=False).llm_json_schema_enabled is True
    monkeypatch.setenv("LAB3_LLM_JSON_SCHEMA_ENABLED", "invalid-secret-flag")
    with pytest.raises(ValueError) as error:
        Lab3RuntimeSettings.from_env(load_dotenv=False)
    assert "invalid-secret-flag" not in "".join(traceback.format_exception(error.value))


@pytest.mark.parametrize("failure", ["oversized", "length", "invalid_json"])
def test_vllm_bounds_response_and_rejects_truncated_completion(failure):
    def respond(_request):
        if failure == "invalid_json":
            return httpx.Response(200, content="private-provider-marker")
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "length" if failure == "length" else "stop",
            "message": {"role": "assistant", "content": (
                "x" * (129 * 1024) if failure == "oversized" else "partial"
            )},
        }]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = VLLMChatClient(base_url="http://localhost:8001/v1", model=MODEL, http_client=http)
        with pytest.raises(VLLMChatError) as error:
            client.complete([ChatMessage(role="user", content="hello")])
    assert error.value.code == "LLM_INVALID_RESPONSE"
    assert "private-provider-marker" not in "".join(traceback.format_exception(error.value))


def test_settings_require_safe_llm_url_and_suppress_bad_environment_input(monkeypatch):
    marker = "invalid-llm-url-secret"
    monkeypatch.setenv("LAB3_POSTGRES_DSN", "postgresql://operator:pw@db/catalog")
    monkeypatch.setenv("WEKNORA_BASE_URL", "https://weknora.example.invalid")
    monkeypatch.setenv("WEKNORA_API_KEY", "weknora-test-secret")
    monkeypatch.setenv("WEKNORA_KNOWLEDGE_BASE_ID", "configured-kb")
    monkeypatch.setenv("LAB3_LLM_BASE_URL", f"http://user:{marker}@localhost:8001/v1")
    monkeypatch.setenv("LAB3_LLM_MODEL", MODEL)

    with pytest.raises(ValueError) as error:
        Lab3RuntimeSettings.from_env(load_dotenv=False)

    rendered = "".join(traceback.format_exception(error.value))
    assert "Invalid Lab 3 runtime environment configuration" in rendered
    assert marker not in rendered


def test_settings_model_validation_rejects_blank_model_name():
    with pytest.raises(ValidationError):
        Lab3RuntimeSettings(
            postgres_dsn="postgresql://operator:pw@db/catalog",
            weknora_base_url="https://weknora.example.invalid",
            weknora_api_key="weknora-test-secret",
            weknora_knowledge_base_id="configured-kb",
            llm_base_url="http://127.0.0.1:8001/v1",
            llm_model=" ",
        )
