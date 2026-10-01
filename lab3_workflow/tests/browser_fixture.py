"""Explicit local browser-test fixture, never the production runtime.

Run: python -m uvicorn lab3_workflow.tests.browser_fixture:app --port 3180
Next dev: BACKEND_URL=http://127.0.0.1:3180 and Gateway URL at that origin,
with the non-secret fixture token. Test doubles are isolated here, not UI data.
"""

import json

from fastapi import Request
from fastapi.responses import JSONResponse

from adapters.real.vllm_chat import VLLMChatClient
from lab3_workflow.runtime.conversation import ConversationService
from lab3_workflow.runtime.demo import create_demo_workflow
from lab3_workflow.runtime.http.app import create_app
from shared.contracts import CustomerRequirement

app = create_app(
    workflow_factory=create_demo_workflow,
    conversation_service=ConversationService(VLLMChatClient(
        base_url="http://127.0.0.1:3180/v1", model="Qwen/Qwen3-14B",
    )),
)
observations: list[dict] = []


@app.post("/v1/chat/completions")
async def fixture_completion(request: Request):
    body = await request.json()
    messages = body["messages"]
    last_user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    if body["model"] == "openclaw/lab2":
        observations.append({
            "kind": "lab2", "user": body["user"],
            "model_header": request.headers.get("x-openclaw-model"),
            "agent": request.headers.get("x-openclaw-agent-id"),
        })
        if last_user == "simulate failure":
            return JSONResponse({"error": "fixture-private-marker"}, status_code=502)
        text = "Lab2 fixture: Chào bạn. Bạn muốn tìm hiểu bài toán AI nào?"
    elif messages[0]["content"].startswith("You are Qwen Advisor"):
        # Only fixed smoke inputs are recognized. This is NOT production extraction.
        users = " ".join(m["content"] for m in messages if m["role"] == "user")
        facts = CustomerRequirement(
            model_size_b=14 if "14B" in users else None,
            usage="inference" if "inference," in users else None,
            budget_vnd=500_000_000 if "500 triệu" in users else None,
        ).model_dump(mode="json")
        assert "tools" not in body
        if last_user == "simulate invalid advisor":
            return {"choices": [{"finish_reason": "stop", "message": {
                "role": "assistant",
                "content": "provider-secret-marker https://private.invalid/traceback",
            }}]}
        observations.append({"kind": "advisor", "roles": [m["role"] for m in messages],
                             "requirement": facts,
                             "format": body.get("response_format", {}).get("type", "plain_json")})
        if last_user in {"bạn là ai?", "bạn làm ở đâu?", "bạn có phải Qwen không?"}:
            text = "Mình là nhân viên tư vấn của CNTTShop."
        elif CustomerRequirement(**facts).missing_required_fields():
            text = ("Chào bạn. Bạn đang muốn triển khai bài toán nào?" if last_user == "xin chào"
                    else "Inference là dùng model để trả lời; fine-tune là huấn luyện thêm. "
                         "Bạn định theo hướng nào và ngân sách khoảng bao nhiêu?")
        else:
            text = "Mình ghi nhận 14B, inference, 500 triệu. Workflow sẽ kiểm tra dữ liệu."
        text = json.dumps({"reply": text, "requirement": facts}, ensure_ascii=False)
    elif messages[0]["content"].startswith("Explain this actual"):
        facts = json.loads(last_user)
        observations.append({"kind": "explanation", "run_id": facts["run_id"],
                             "status": facts["status"]})
        text = f"Fixture explanation từ run lưu thực tế: {facts['status']} ({facts['run_id']})."
    else:
        return JSONResponse({"error": "unexpected fixture prompt"}, status_code=400)
    return {"choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": text,
    }}]}


@app.get("/test/observations")
def fixture_observations():
    return {"requests": observations, "run_count": len(app.state.run_service.store._runs)}
