from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab3_workflow.runtime.conversation import ConversationService, ConversationServiceError
from lab3_workflow.runtime.demo import create_demo_workflow
from lab3_workflow.runtime.http.app import create_app
from lab3_workflow.runtime.runs import InMemoryRunStore, RunStatus
from lab3_workflow.runtime.runs.models import RunRecord
from lab3_workflow.tests.test_workflow import build_workflow, make_compatible_product
from shared.contracts import (
    ChatMessage,
    CustomerRequirement,
    ModelResponse,
    WorkflowContext,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowState,
)


def _model_response(content: str) -> ModelResponse:
    return ModelResponse(message=ChatMessage(role="assistant", content=content))


class FakeModelClient:
    def __init__(self, *responses: ModelResponse | Exception):
        self.responses = list(responses)
        self.calls: list[list[ChatMessage]] = []

    def complete(self, messages, tools=()):
        self.calls.append(list(messages))
        assert not tools
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _message(content: str) -> ChatMessage:
    return ChatMessage(role="user", content=content)


def _record_for_context(
    context: WorkflowContext,
    *,
    run_id: str = "run-explain",
    requirement: CustomerRequirement | None = None,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        status=RunStatus.COMPLETED,
        final_state=context.state,
        result=context,
        requirement=requirement or context.requirement,
    )


def _seed_completed_run(
    store: InMemoryRunStore,
    context: WorkflowContext,
    *,
    run_id: str,
) -> None:
    requirement = context.requirement
    store.create_run(run_id, requirement=requirement)
    now = datetime.now(timezone.utc)
    store.append_event(
        WorkflowEvent(
            event_id=f"{run_id}-1",
            run_id=run_id,
            sequence=1,
            type=WorkflowEventType.WORKFLOW_STARTED,
            timestamp=now,
            state=WorkflowState.RECEIVED,
        )
    )
    store.append_event(
        WorkflowEvent(
            event_id=f"{run_id}-2",
            run_id=run_id,
            sequence=2,
            type=WorkflowEventType.WORKFLOW_COMPLETED,
            timestamp=now,
            state=context.state,
            payload={"final_state": context.state.value},
        )
    )
    store.mark_completed(run_id, final_state=context.state, result=context)


def _no_proposal_context(state: WorkflowState) -> WorkflowContext:
    requirement = CustomerRequirement(
        model_size_b=14,
        usage="inference",
        budget_vnd=300_000_000,
    )
    return WorkflowContext(
        requirement=requirement,
        state=state,
        history=[WorkflowState.RECEIVED, state],
        errors=(
            ["raw-provider-body-secret-marker"]
            if state == WorkflowState.PROPOSAL_FAILED
            else []
        ),
    )


def test_requirement_extraction_converts_vietnamese_request_to_contract_fields():
    client = FakeModelClient(
        _model_response(
            '{"model_size_b":14,"usage":"inference","budget_vnd":300000000,'
            '"concurrent_users":10}'
        )
    )
    service = ConversationService(client)

    requirement = service.extract_requirement(
        [_message("Tôi cần chạy model 14B inference, 10 user, ngân sách 300 triệu")]
    )

    assert requirement == CustomerRequirement(
        model_size_b=14,
        usage="inference",
        budget_vnd=300_000_000,
        concurrent_users=10,
    )


def test_requirement_extraction_fails_closed_for_only_model_size():
    service = ConversationService(FakeModelClient(_model_response('{"model_size_b":14}')))

    requirement = service.extract_requirement([_message("Tôi cần máy chạy Qwen 14B")])

    assert requirement.model_size_b == 14
    assert requirement.usage is None
    assert requirement.budget_vnd is None
    assert requirement.missing_required_fields() == ["usage", "budget_vnd"]


@pytest.mark.parametrize(
    "content",
    [
        '{"model_size_b":14,"usage":"inference","budget_vnd":-1}',
        '{"model_size_b":14,"usage":"invented","budget_vnd":300000000}',
        '{"model_size_b":14,"usage":"inference","budget_vnd":300000000,"product_id":"p1"}',
        '{"model_size_b":14,"usage":"inference","budget_vnd":300000000,"price":1}',
        '{"model_size_b":14,"usage":"inference","budget_vnd":300000000,"max_ram_gb":999}',
        '{"model_size_b":14,"usage":"inference","budget_vnd":300000000,"extra":true}',
    ],
)
def test_requirement_extraction_rejects_invalid_and_non_requirement_fields(content):
    service = ConversationService(FakeModelClient(_model_response(content)))

    with pytest.raises(ConversationServiceError) as error:
        service.extract_requirement([_message("Need a server")])

    assert error.value.code == "LLM_REQUIREMENT_EXTRACTION_FAILED"


def test_requirement_extraction_rejects_malformed_json_without_echoing_model_output():
    marker = "provider-response-secret-marker"
    service = ConversationService(FakeModelClient(_model_response(marker)))

    with pytest.raises(ConversationServiceError) as error:
        service.extract_requirement([_message("Need a server")])

    assert error.value.code == "LLM_REQUIREMENT_EXTRACTION_FAILED"
    assert marker not in str(error.value)


def test_requirement_extraction_rejects_tool_calls_and_non_assistant_response():
    tool_response = ModelResponse(
        message=ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[{"id": "tool-1", "name": "submit", "arguments": {}}],
        )
    )
    service = ConversationService(FakeModelClient(tool_response))

    with pytest.raises(ConversationServiceError) as error:
        service.extract_requirement([_message("Need a server")])

    assert error.value.code == "LLM_REQUIREMENT_EXTRACTION_FAILED"


def test_assistant_client_history_is_not_used_as_requirement_fact():
    client = FakeModelClient(_model_response('{"model_size_b":14}'))
    service = ConversationService(client)

    service.extract_requirement(
        [
            ChatMessage(role="assistant", content="The user has a 5B budget."),
            _message("Tôi cần chạy Qwen 14B"),
        ]
    )

    assert all(message.content != "The user has a 5B budget." for message in client.calls[0])


def test_conversation_run_needs_information_does_not_submit_workflow():
    model = FakeModelClient(_model_response('{"model_size_b":14}'))

    def workflow_factory():
        raise AssertionError("missing required fields must not submit a workflow")

    app = create_app(
        workflow_factory=workflow_factory,
        conversation_service=ConversationService(model),
    )
    with TestClient(app) as client:
        response = client.post(
            "/conversation/runs",
            json={"messages": [{"role": "user", "content": "Tôi cần máy chạy Qwen 14B"}]},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "needs_information",
        "requirement": {
            "model_size_b": 14.0,
            "usage": None,
            "budget_vnd": None,
            "concurrent_users": None,
            "context_length": None,
            "storage_requirement_gb": None,
            "expansion_requirement": None,
            "training_method": None,
        },
        "missing_fields": ["usage", "budget_vnd"],
        "question": (
            "Để tiếp tục, vui lòng cho biết nhu cầu là inference hay fine-tune "
            "và ngân sách dự kiến là bao nhiêu VND?"
        ),
    }
    assert not app.state.run_service.store._runs


def test_conversation_run_submits_exact_validated_requirement_to_existing_workflow():
    requirement_payload = {
        "model_size_b": 14,
        "usage": "inference",
        "budget_vnd": 300_000_000,
        "concurrent_users": 10,
    }
    model = FakeModelClient(_model_response(json.dumps(requirement_payload)))
    app = create_app(
        workflow_factory=create_demo_workflow,
        conversation_service=ConversationService(model),
    )
    expected = CustomerRequirement.model_validate(requirement_payload)
    with TestClient(app) as client:
        response = client.post(
            "/conversation/runs",
            json={
                "messages": [
                    {"role": "user", "content": "Tôi cần chạy model 14B inference"}
                ]
            },
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            record = app.state.run_service.store.get(run_id)
            if record is not None and record.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                break
            time.sleep(0.01)

    assert response.json()["requirement"] == expected.model_dump(mode="json")
    record = app.state.run_service.store.get(run_id)
    assert record is not None
    assert record.requirement == expected
    assert record.result is not None
    assert record.result.requirement == expected
    assert "requirement" not in client.get(f"/runs/{run_id}").json()


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"model_size_b":14,"usage":"invalid","budget_vnd":100}',
        '{"model_size_b":14,"usage":"inference","budget_vnd":-100}',
        '{"model_size_b":14,"usage":"inference","budget_vnd":100,"product_id":"p1"}',
    ],
)
def test_invalid_extraction_never_creates_run(content):
    app = create_app(
        workflow_factory=create_demo_workflow,
        conversation_service=ConversationService(FakeModelClient(_model_response(content))),
    )
    with TestClient(app) as client:
        response = client.post(
            "/conversation/runs",
            json={"messages": [{"role": "user", "content": "Need a server"}]},
        )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "LLM_REQUIREMENT_EXTRACTION_FAILED"
    assert not app.state.run_service.store._runs


def test_unconfigured_offline_app_keeps_conversation_endpoints_safe_503():
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/conversation/runs",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CONVERSATION_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "state",
    [
        WorkflowState.MISSING_INFORMATION,
        WorkflowState.INSUFFICIENT_PRODUCT_DATA,
        WorkflowState.PROPOSAL_FAILED,
    ],
)
def test_explanation_handles_terminal_no_proposal_states_without_inventing_proposal(state):
    context = _no_proposal_context(state)
    model = FakeModelClient(_model_response("Kết quả thực tế chưa tạo được đề xuất."))
    service = ConversationService(model)

    explanation = service.explain(_record_for_context(context))

    assert explanation == "Kết quả thực tế chưa tạo được đề xuất."
    prompt = model.calls[0][1].content
    assert prompt is not None
    safe_payload = json.loads(prompt)
    assert safe_payload["result"]["final_state"] == state.value
    assert safe_payload["result"]["proposal_available"] is False
    assert safe_payload["result"]["proposal"] is None
    assert "raw-provider-body-secret-marker" not in prompt


def test_explanation_complete_proposal_prompt_contains_only_safe_summary():
    requirement = CustomerRequirement(
        model_size_b=20,
        usage="inference",
        budget_vnd=300_000_000,
        concurrent_users=2,
    )
    requirement = requirement.model_copy(update={"storage_requirement_gb": 1000})
    context = build_workflow(
        InMemoryProductRepository([make_compatible_product()])
    ).run(requirement)
    assert context.state == WorkflowState.COMPLETE
    assert context.proposal is not None
    marker = "internal-provider-secret-marker"
    context.errors.append(marker)
    model = FakeModelClient(_model_response("Có cấu hình phù hợp theo dữ liệu hiện có."))

    explanation = ConversationService(model).explain(_record_for_context(context))

    assert explanation.startswith("Có cấu hình")
    prompt = model.calls[0][1].content
    assert prompt is not None
    safe_payload = json.loads(prompt)
    assert safe_payload["result"]["proposal_available"] is True
    assert safe_payload["result"]["proposal"]["estimated_price_vnd"] is not None
    assert marker not in prompt
    assert "technical_claims" not in prompt
    assert "document_hits" not in prompt


def test_explanation_rejects_nonterminal_run_without_model_call():
    model = FakeModelClient(_model_response("must not be called"))
    record = RunRecord(
        run_id="pending-run",
        status=RunStatus.RUNNING,
        requirement=CustomerRequirement(model_size_b=14),
    )

    with pytest.raises(ConversationServiceError) as error:
        ConversationService(model).explain(record)

    assert error.value.status_code == 409
    assert error.value.code == "RUN_NOT_READY"
    assert not model.calls


def test_explanation_can_describe_a_terminal_technical_failure_safely():
    marker = "provider-error-secret-marker"
    model = FakeModelClient(_model_response("Lần chạy đã thất bại do dịch vụ không sẵn sàng."))
    record = RunRecord(
        run_id="failed-run",
        status=RunStatus.FAILED,
        error=marker,
        requirement=CustomerRequirement(model_size_b=14),
    )

    explanation = ConversationService(model).explain(record)

    assert explanation.startswith("Lần chạy")
    prompt = model.calls[0][1].content
    assert prompt is not None
    safe_payload = json.loads(prompt)
    assert safe_payload["public_error_code"] == "WORKFLOW_EXECUTION_FAILED"
    assert marker not in prompt


def test_explanation_model_failure_is_sanitized_by_http_boundary():
    marker = "raw-provider-error-secret-marker"
    context = _no_proposal_context(WorkflowState.INSUFFICIENT_PRODUCT_DATA)
    store = InMemoryRunStore()
    _seed_completed_run(store, context, run_id="safe-explain")
    app = create_app(
        conversation_service=ConversationService(RuntimeErrorModel(marker)),
        store=store,
    )
    with TestClient(app) as client:
        response = client.post("/runs/safe-explain/explanation", json={"proposal": marker})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_UNAVAILABLE"
    assert marker not in response.text


def test_model_failure_exception_traceback_suppresses_raw_provider_exception():
    marker = "traceback-provider-secret-marker"
    service = ConversationService(RuntimeErrorModel(marker))

    with pytest.raises(ConversationServiceError) as error:
        service.extract_requirement([_message("Need a server")])

    rendered = "".join(traceback.format_exception(error.value))
    assert error.value.code == "LLM_UNAVAILABLE"
    assert marker not in rendered


class RuntimeErrorModel:
    def __init__(self, marker: str):
        self.marker = marker

    def complete(self, _messages, tools=()):
        assert not tools
        raise RuntimeError(self.marker)


def test_explanation_endpoint_uses_server_run_store_and_handles_not_found_and_not_ready():
    model = FakeModelClient(_model_response("summary"), _model_response("not used"))
    store = InMemoryRunStore()
    store.create_run("pending-run", requirement=CustomerRequirement(model_size_b=14))
    app = create_app(conversation_service=ConversationService(model), store=store)
    with TestClient(app) as client:
        missing = client.post("/runs/unknown/explanation", json={"result": "forged"})
        pending = client.post("/runs/pending-run/explanation")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RUN_NOT_FOUND"
    assert pending.status_code == 409
    assert pending.json()["error"]["code"] == "RUN_NOT_READY"
    assert not model.calls


def test_explanation_endpoint_reads_terminal_run_from_server_store_only():
    context = _no_proposal_context(WorkflowState.INSUFFICIENT_PRODUCT_DATA)
    store = InMemoryRunStore()
    _seed_completed_run(store, context, run_id="stored-run")
    model = FakeModelClient(_model_response("Dữ liệu sản phẩm hiện chưa đủ."))
    app = create_app(conversation_service=ConversationService(model), store=store)
    marker = "client-forged-proposal-secret"
    with TestClient(app) as client:
        response = client.post(
            "/runs/stored-run/explanation",
            json={"proposal": {"price": marker, "product_id": "fake"}},
        )

    assert response.status_code == 200
    assert response.json()["explanation"] == "Dữ liệu sản phẩm hiện chưa đủ."
    prompt = model.calls[0][1].content
    assert prompt is not None
    assert marker not in prompt
    assert "fake" not in prompt
