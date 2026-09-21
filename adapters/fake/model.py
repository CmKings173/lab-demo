from collections.abc import Sequence

from shared.contracts import ChatMessage, ModelResponse, ToolDefinition


class FakeModelClient:
    """Deterministic model boundary shared by offline tests across labs."""

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
