from collections.abc import Sequence
from typing import Protocol

from shared.contracts import ChatMessage, ModelResponse, ToolDefinition


class ModelClient(Protocol):
    def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] = (),
    ) -> ModelResponse: ...
