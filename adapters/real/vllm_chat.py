"""Small OpenAI-compatible vLLM adapter for the Lab 3 conversation boundary."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import SecretStr

from shared.contracts import ChatMessage, ModelResponse, ToolDefinition


class VLLMChatError(RuntimeError):
    """Provider failure exposing only a stable public-safe code."""

    def __init__(self, code: str) -> None:
        messages = {
            "LLM_UNAVAILABLE": "The language model service is unavailable.",
            "LLM_INVALID_RESPONSE": "The language model returned an invalid response.",
        }
        self.code = code if code in messages else "LLM_UNAVAILABLE"
        super().__init__(messages[self.code])


class VLLMChatClient:
    """Implements the shared ModelClient contract over vLLM's chat API."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: SecretStr | str | None = None,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 60.0,
        max_tokens: int = 1024,
        json_schema_enabled: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        self._max_tokens = max_tokens
        self._json_schema_enabled = json_schema_enabled

    def check_ready(self) -> bool:
        """Check the OpenAI-compatible models endpoint without running inference."""
        try:
            response = self._http_client.get(f"{self.base_url}/models")
        except Exception:
            raise VLLMChatError("LLM_UNAVAILABLE") from None
        if not 200 <= response.status_code < 300:
            raise VLLMChatError("LLM_UNAVAILABLE")
        try:
            payload = response.json()
            data = payload["data"]
            if not isinstance(data, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("id"), str)
                for item in data
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise VLLMChatError("LLM_INVALID_RESPONSE") from None
        return True

    def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] = (),
    ) -> ModelResponse:
        return self._complete(messages, tools=tools)

    def complete_structured(
        self, messages: Sequence[ChatMessage], *, response_schema: dict, schema_name: str
    ) -> ModelResponse:
        """Opt into documented vLLM JSON schema only after deployment support is verified."""
        if not self._json_schema_enabled:
            return self._complete(messages)
        return self._complete(messages, response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": response_schema},
        })

    def _complete(
        self, messages: Sequence[ChatMessage], *, tools: Sequence[ToolDefinition] = (),
        response_format: dict | None = None,
    ) -> ModelResponse:
        if tools or not messages:
            raise VLLMChatError("LLM_INVALID_RESPONSE")
        wire_messages: list[dict[str, str]] = []
        for message in messages:
            if (
                message.role not in {"system", "user", "assistant"}
                or message.content is None
                or message.tool_calls
            ):
                raise VLLMChatError("LLM_INVALID_RESPONSE")
            wire_messages.append({"role": message.role, "content": message.content})

        headers: dict[str, str] = {}
        if self.api_key is not None:
            key = (
                self.api_key.get_secret_value()
                if isinstance(self.api_key, SecretStr)
                else self.api_key
            )
            if key:
                headers["Authorization"] = f"Bearer {key}"
        body = {
            "model": self.model,
            "messages": wire_messages,
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if response_format is not None:
            body["response_format"] = response_format
        try:
            with self._http_client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=body,
            ) as response:
                if not 200 <= response.status_code < 300:
                    raise VLLMChatError("LLM_UNAVAILABLE")
                chunks = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    if len(chunks) + len(chunk) > 128 * 1024:
                        raise VLLMChatError("LLM_INVALID_RESPONSE")
                    chunks.extend(chunk)
        except VLLMChatError:
            raise
        except Exception:
            raise VLLMChatError("LLM_UNAVAILABLE") from None
        try:
            payload: Any = json.loads(chunks)
            choice = payload["choices"][0]
            message = choice["message"]
            content = message["content"]
            finish_reason = choice.get("finish_reason")
            if (
                message.get("role") != "assistant"
                or not isinstance(content, str)
                or message.get("tool_calls")
                or (finish_reason is not None and not isinstance(finish_reason, str))
                or finish_reason in {"length", "tool_calls", "content_filter"}
            ):
                raise ValueError
        except (IndexError, KeyError, TypeError, ValueError, RecursionError):
            raise VLLMChatError("LLM_INVALID_RESPONSE") from None
        return ModelResponse(
            message=ChatMessage(role="assistant", content=content),
            finish_reason=finish_reason,
        )

    def close(self) -> None:
        """Close only the HTTP client constructed by this adapter."""
        if self._owns_http_client:
            self._http_client.close()
