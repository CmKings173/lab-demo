from collections.abc import Sequence

from adapters.fake.model import FakeModelClient
from shared.contracts import ChatMessage, ModelResponse, ToolDefinition

__all__ = ["FakeModelClient", "VLLMModelClient"]


class VLLMModelClient:
    """Reserved for Lab 1 evaluation; OpenClaw owns the Lab 2/3 model runtime."""

    def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] = (),
    ) -> ModelResponse:
        raise NotImplementedError("vLLM adapter is planned for a later Lab 1 phase")
