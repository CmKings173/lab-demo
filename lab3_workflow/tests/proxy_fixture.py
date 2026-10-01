"""Local-only Next/FastAPI regression fixture; no production providers or .env loading."""

import json
import time
from typing import Literal
from uuid import uuid4

from lab3_workflow.runtime.conversation import ConversationService
from lab3_workflow.runtime.demo import create_demo_workflow
from lab3_workflow.runtime.http.app import create_app
from shared.contracts import ChatMessage, CustomerRequirement, ModelResponse


class DelayedFixtureModel:
    def __init__(self):
        self.explanation_delay_seconds = 0

    def complete(self, messages, tools=()):
        assert not tools
        users = [m.content for m in messages if m.role == "user"]
        if "slow" in users:
            time.sleep(16)  # two genuine service calls: 32s, beyond Next's old 30s
        if "timeout" in users:
            time.sleep(0.6)
        facts = CustomerRequirement()
        if any("14B inference 500 triệu" in text for text in users):
            facts = CustomerRequirement(model_size_b=14, usage="inference", budget_vnd=500_000_000)
        if messages[0].content.startswith("You are Qwen Advisor"):
            text = json.dumps(
                {
                    "reply": "Fixture: mình đã hiểu; bạn có thể hỏi thêm.",
                    "requirement": facts.model_dump(mode="json"),
                },
                ensure_ascii=False,
            )
        elif messages[0].content.startswith("Explain this actual"):
            delay = self.explanation_delay_seconds
            time.sleep(delay)  # one real ConversationService.explain model call
            text = (
                "provider-secret-marker https://internal.example/password"
                if delay == 0.6
                else "Fixture: kết quả từ run đã lưu, không phải dữ liệu live."
            )
        else:
            text = facts.model_dump_json()
        return ModelResponse(
            message=ChatMessage(role="assistant", content=text), finish_reason="stop"
        )


model = DelayedFixtureModel()
app = create_app(
    workflow_factory=create_demo_workflow,
    conversation_service=ConversationService(model),
)


@app.get("/test/run-count")
def run_count():
    return {"run_count": len(app.state.run_service.store._runs)}


@app.post("/test/explanation-mode/{mode}")
def explanation_mode(mode: Literal["normal", "slow", "timeout"]):
    model.explanation_delay_seconds = {"normal": 0, "slow": 32, "timeout": 0.6}[mode]
    return {"mode": mode}


@app.post("/test/pending-run")
def pending_run():
    record = app.state.run_service.store.create_run(uuid4().hex)
    return {"run_id": record.run_id}
