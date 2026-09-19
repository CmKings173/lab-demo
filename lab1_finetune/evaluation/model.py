from collections.abc import Sequence

from shared.contracts import ChatMessage, ModelResponse, ToolDefinition


class FakeModelClient:
    """Offline chat client used only by Lab 1 evaluation tests."""

    def __init__(self, response: str = "fake-model-response") -> None:
        self.response = response

    def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] = (),
    ) -> ModelResponse:
        return ModelResponse(
            message=ChatMessage(role="assistant", content=self.response),
            finish_reason="stop",
        )


class VLLMModelClient:
    """Reserved for Lab 1 evaluation; OpenClaw owns the Lab 2/3 model runtime."""

    def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] = (),
    ) -> ModelResponse:
        raise NotImplementedError("vLLM adapter is planned for a later Lab 1 phase")
