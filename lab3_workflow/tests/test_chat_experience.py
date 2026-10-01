"""One-call boundary tests, not evidence of live Qwen semantic accuracy."""

import pytest

from lab3_workflow.runtime.advisor import ADVISOR_SYSTEM_PROMPT
from lab3_workflow.runtime.conversation import ConversationService, ConversationServiceError
from lab3_workflow.tests.test_advisor import advisor_json
from lab3_workflow.tests.test_conversation import FakeModelClient, _model_response
from shared.contracts import ChatMessage, CustomerRequirement


@pytest.mark.parametrize("message", [
    "xin chào", "bạn là ai?", "bạn làm ở đâu?", "bạn có phải Qwen không?",
])
def test_normal_turn_uses_one_completion_and_no_tools(message):
    reply = "Mình là nhân viên tư vấn của CNTTShop. Mình có thể giúp bạn xác định nhu cầu AI."
    model = FakeModelClient(_model_response(advisor_json(reply)))
    history = [ChatMessage(role="user", content=message)]

    turn = ConversationService(model).advise(history)

    assert len(model.calls) == 1
    assert model.calls[0][1:] == history
    assert turn.reply == reply
    assert turn.requirement == CustomerRequirement()
    assert "Mình là nhân viên tư vấn của CNTTShop." in ADVISOR_SYSTEM_PROMPT
    assert "Identity questions establish NO" in ADVISOR_SYSTEM_PROMPT


def test_identity_follow_up_preserves_prior_user_facts():
    model = FakeModelClient(_model_response(advisor_json(
        "Mình là nhân viên tư vấn của CNTTShop.", model_size_b=14,
    )))
    turn = ConversationService(model).advise([
        ChatMessage(role="user", content="Tôi cần Qwen 14B"),
        ChatMessage(role="assistant", content="Inference hay fine-tune?"),
        ChatMessage(role="user", content="ai đang tư vấn cho tôi?"),
    ])
    assert len(model.calls) == 1
    assert turn.requirement == CustomerRequirement(model_size_b=14)


def test_no_user_message_is_rejected_before_model_call():
    model = FakeModelClient()
    with pytest.raises(ConversationServiceError) as error:
        ConversationService(model).advise([ChatMessage(role="assistant", content="14B")])
    assert error.value.code == "INVALID_CONVERSATION"
    assert not model.calls
