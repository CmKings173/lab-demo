"""OpenAI-compatible HTTP boundary for offline Lab 1 model evaluation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from adapters.fake.model import FakeModelClient
from lab1_finetune.data.frozen_contracts import (
    ChatMessage,
    ModelResponse,
    ToolCall,
    ToolDefinition,
)

__all__ = ["FakeModelClient", "ModelEvaluationError", "VLLMModelClient"]


class ModelEvaluationError(RuntimeError):
    """A transport error or invalid OpenAI-compatible model response."""


def _openai_message(message: ChatMessage) -> dict[str, object]:
    result: dict[str, object] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        result["tool_call_id"] = message.tool_call_id
    return result


def _parse_response(payload: object) -> ModelResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("response must be an object")
        choices = payload["choices"]
        if not isinstance(choices, list) or not choices:
            raise ValueError("choices must be a nonempty list")
        choice = choices[0]
        message = choice["message"]
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ValueError("choice.message must be an assistant message")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("assistant content must be a string or null")
        raw_calls = message.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            raise ValueError("tool_calls must be a list")
        calls = []
        for raw_call in raw_calls:
            function = raw_call["function"]
            name = function["name"]
            raw_arguments = function["arguments"]
            if not isinstance(name, str) or not name:
                raise ValueError("tool name is missing")
            if not isinstance(raw_arguments, str):
                raise ValueError("tool arguments must be a JSON string")
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise ValueError("tool arguments are not valid JSON") from exc
            if not isinstance(arguments, dict):
                raise ValueError("tool arguments must decode to an object")
            calls.append(ToolCall(id=raw_call["id"], name=name, arguments=arguments))
        if content is None and not calls:
            raise ValueError("assistant response has neither content nor tool calls")
        return ModelResponse(
            message=ChatMessage(role="assistant", content=content, tool_calls=calls),
            finish_reason=choice.get("finish_reason"),
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ModelEvaluationError(f"Malformed model response: {exc}") from exc


class VLLMModelClient:
    """Call a separately served vLLM chat-completions endpoint.

    HTTP shape: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html
    """

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str | None = None,
        timeout: float = 60,
        temperature: float = 0,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be an HTTP(S) URL")
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if timeout <= 0 or max_tokens <= 0 or temperature < 0:
            raise ValueError("timeout and max_tokens must be positive; temperature nonnegative")
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking

    def check_ready(self) -> None:
        """Fail fast if the server is unavailable or the requested model is absent."""
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        request = Request(f"{self.base_url}/models", headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            raise ModelEvaluationError(f"Model preflight returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise ModelEvaluationError("Model endpoint unavailable during preflight") from exc
        except (ValueError, UnicodeError) as exc:
            raise ModelEvaluationError("Model preflight returned invalid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ModelEvaluationError("Model preflight returned a malformed model list")
        served = {item["id"] for item in payload["data"]
                  if isinstance(item, dict) and isinstance(item.get("id"), str)}
        if self.model_name not in served:
            raise ModelEvaluationError(f"Configured model {self.model_name!r} is not served")

    def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] = (),
    ) -> ModelResponse:
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": [_openai_message(message) for message in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            # Qwen3 vLLM switch: https://qwen.readthedocs.io/en/v3.0/deployment/vllm.html
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }}
                for tool in tools
            ]
            payload["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except HTTPError as exc:
            raise ModelEvaluationError(f"Model endpoint returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise ModelEvaluationError(
                f"Model endpoint unavailable or timed out: {type(exc).__name__}"
            ) from exc
        except (ValueError, UnicodeError) as exc:
            raise ModelEvaluationError("Model endpoint returned invalid JSON") from exc
        return _parse_response(data)
