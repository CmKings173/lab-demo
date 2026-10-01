from __future__ import annotations

from typing import Annotated, Literal

from pydantic import UUID4, Field, field_validator, model_validator

from shared.contracts import CustomerRequirement, WorkflowState
from shared.contracts.models import ContractModel

from ..advisor import CONVERSATION_MESSAGE_MAX_CHARS
from ..runs.models import RunStatus


class ConversationMessage(ContractModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=CONVERSATION_MESSAGE_MAX_CHARS)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message content must not be blank")
        return value


class ConversationRunRequest(ContractModel):
    messages: list[ConversationMessage] = Field(min_length=1, max_length=20)
    workflow_run_id: UUID4 | None = None

    @model_validator(mode="after")
    def validate_conversation_size(self) -> ConversationRunRequest:
        if not any(message.role == "user" for message in self.messages):
            raise ValueError("at least one user message is required")
        if sum(len(message.content) for message in self.messages) > 20_000:
            raise ValueError("conversation is too long")
        return self


class ConversationContinuedResponse(ContractModel):
    status: Literal["conversation"]
    requirement: CustomerRequirement
    missing_fields: list[str]
    reply: str = Field(min_length=1, max_length=CONVERSATION_MESSAGE_MAX_CHARS)


class ConversationRunSubmittedResponse(ContractModel):
    status: Literal["submitted"]
    reply: str = Field(min_length=1, max_length=CONVERSATION_MESSAGE_MAX_CHARS)
    run_id: str
    run_status: RunStatus
    requirement: CustomerRequirement


ConversationRunResponse = Annotated[
    ConversationContinuedResponse | ConversationRunSubmittedResponse,
    Field(discriminator="status"),
]


class RunExplanationResponse(ContractModel):
    run_id: str
    status: RunStatus
    final_state: WorkflowState | None = None
    explanation: str = Field(min_length=1, max_length=CONVERSATION_MESSAGE_MAX_CHARS)
