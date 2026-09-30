from __future__ import annotations

import json
import time
from contextlib import ExitStack
from threading import Event

import pytest
from fastapi.testclient import TestClient

from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab3_workflow.runtime.http import app as module_app
from lab3_workflow.runtime.http import create_app
from lab3_workflow.runtime.runs.store import InMemoryRunStore
from lab3_workflow.tests.test_workflow import build_workflow, make_compatible_product
from shared.contracts import CustomerRequirement, WorkflowContext, WorkflowState


@pytest.fixture
def client_factory():
    with ExitStack() as stack:
        yield lambda app: stack.enter_context(TestClient(app))


def workflow_factory():
    return build_workflow(InMemoryProductRepository([make_compatible_product()]))


def failing_workflow_factory():
    class FailingRepository(InMemoryProductRepository):
        def search(self, request):
            raise RuntimeError("catalog unavailable")

    return build_workflow(FailingRepository([make_compatible_product()]))


def secret_failing_workflow_factory():
    class FailingRepository(InMemoryProductRepository):
        def search(self, request):
            raise RuntimeError(
                "database failure: postgresql://user:SUPER_SECRET_PASSWORD@db/internal; "
                "WEKNORA_API_KEY=VERY_SECRET_VALUE"
            )

    return build_workflow(FailingRepository([make_compatible_product()]))


def secret_proposal_failure_factory():
    workflow = workflow_factory()

    class FailingProposalService:
        def create(self, *args, **kwargs):
            raise RuntimeError(
                "provider failure: WEKNORA_API_KEY=PROPOSAL_SECRET_VALUE"
            )

    workflow.proposal_service = FailingProposalService()
    return workflow


class PausingCompletionStore(InMemoryRunStore):
    def __init__(self) -> None:
        super().__init__()
        self.completion_started = Event()
        self.allow_completion = Event()

    def mark_completed(
        self,
        run_id: str,
        *,
        final_state: WorkflowState,
        result: WorkflowContext,
        completed_at=None,
    ):
        self.completion_started.set()
        if not self.allow_completion.wait(timeout=5):
            raise RuntimeError("test completion gate timed out")
        return super().mark_completed(
            run_id,
            final_state=final_state,
            result=result,
            completed_at=completed_at,
        )


def requirement_payload() -> dict[str, object]:
    return {
        "model_size_b": 20,
        "usage": "inference",
        "concurrent_users": 2,
        "budget_vnd": 300_000_000,
        "storage_requirement_gb": 1000,
    }


def wait_for_completion(client: TestClient, run_id: str) -> dict[str, object]:
    for _ in range(100):
        payload = client.get(f"/runs/{run_id}").json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("run did not reach a terminal status")


def parse_sse(response) -> list[dict[str, str]]:
    frames: list[dict[str, str]] = []
    frame: dict[str, str] = {}
    for raw_line in response.iter_lines():
        line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
        if line:
            key, value = line.split(": ", 1)
            frame[key] = value
        elif frame:
            frames.append(frame)
            frame = {}
    if frame:
        frames.append(frame)
    return frames


def test_post_run_returns_id_and_background_workflow_completes(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=workflow_factory))

    response = client.post("/runs", json=requirement_payload())

    assert response.status_code == 202
    created = response.json()
    assert created["run_id"]
    snapshot = wait_for_completion(client, created["run_id"])
    assert snapshot["status"] == "completed"
    assert snapshot["final_state"] == WorkflowState.COMPLETE.value
    assert snapshot["result"]["proposal_available"] is True
    assert snapshot["result"]["proposal"]["evidence_count"] > 0
    assert "technical_reasoning" not in json.dumps(snapshot)


def test_health_reports_process_health_only() -> None:
    with TestClient(create_app(workflow_factory=workflow_factory)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_technical_exceptions_are_sanitized_in_snapshot_and_sse() -> None:
    secrets = (
        "SUPER_SECRET_PASSWORD",
        "VERY_SECRET_VALUE",
        "postgresql://user:SUPER_SECRET_PASSWORD@db/internal",
        "WEKNORA_API_KEY=VERY_SECRET_VALUE",
    )
    with TestClient(create_app(workflow_factory=secret_failing_workflow_factory)) as client:
        created = client.post("/runs", json=requirement_payload()).json()
        snapshot = wait_for_completion(client, created["run_id"])
        with client.stream("GET", f"/runs/{created['run_id']}/events") as response:
            frames = parse_sse(response)

    public_text = json.dumps(snapshot) + "\n".join(frame["data"] for frame in frames)
    if any(secret in public_text for secret in secrets):
        raise AssertionError("public run data exposed a fake test secret")
    if snapshot["error"] != "WORKFLOW_EXECUTION_FAILED":
        raise AssertionError("failed run did not use the stable public error code")
    events_by_type = {
        json.loads(frame["data"])["type"]: json.loads(frame["data"])
        for frame in frames
        if json.loads(frame["data"])["type"] in {
            "tool.failed",
            "state.failed",
            "workflow.failed",
        }
    }
    if (
        events_by_type.get("tool.failed", {}).get("payload", {}).get("error")
        != "WORKFLOW_TOOL_FAILED"
    ):
        raise AssertionError("tool failure did not use the stable public error code")
    if (
        events_by_type.get("state.failed", {}).get("payload", {}).get("error")
        != "WORKFLOW_STATE_FAILED"
    ):
        raise AssertionError("state failure did not use the stable public error code")
    if (
        events_by_type.get("workflow.failed", {}).get("payload", {}).get("error")
        != "WORKFLOW_EXECUTION_FAILED"
    ):
        raise AssertionError("workflow failure did not use the stable public error code")


def test_result_summary_does_not_expose_proposal_exception_text() -> None:
    secrets = ("PROPOSAL_SECRET_VALUE", "WEKNORA_API_KEY=PROPOSAL_SECRET_VALUE")
    with TestClient(create_app(workflow_factory=secret_proposal_failure_factory)) as client:
        created = client.post("/runs", json=requirement_payload()).json()
        snapshot = wait_for_completion(client, created["run_id"])

    public_text = json.dumps(snapshot)
    if any(secret in public_text for secret in secrets):
        raise AssertionError("public result summary exposed a fake test secret")
    if snapshot["status"] != "completed" or snapshot["final_state"] != "proposal_failed":
        raise AssertionError("business proposal failure did not remain a completed workflow result")
    if snapshot["result"]["errors"] != ["PROPOSAL_GENERATION_FAILED"]:
        raise AssertionError("proposal exception was not replaced by its stable public code")


def test_completion_event_does_not_publish_completed_snapshot_before_result() -> None:
    store = PausingCompletionStore()
    app = create_app(workflow_factory=workflow_factory, store=store)
    try:
        with TestClient(app) as client:
            created = client.post("/runs", json=requirement_payload()).json()
            if not store.completion_started.wait(timeout=5):
                raise AssertionError("workflow did not reach result publication")

            snapshot = client.get(f"/runs/{created['run_id']}").json()
            if snapshot["status"] == "completed" and snapshot["result"] is None:
                raise AssertionError("completed run was exposed without its result")
            if snapshot["status"] != "running":
                raise AssertionError("run should remain running until result publication")

            store.allow_completion.set()
            completed = wait_for_completion(client, created["run_id"])
            if completed["status"] != "completed" or completed["result"] is None:
                raise AssertionError("completed run did not publish its result atomically")
            with client.stream("GET", f"/runs/{created['run_id']}/events") as response:
                frames = parse_sse(response)
            event_types = [json.loads(frame["data"])["type"] for frame in frames]
            if event_types.count("workflow.completed") != 1:
                raise AssertionError(
                    "terminal workflow.completed event was not retained exactly once"
                )
    finally:
        store.allow_completion.set()


def test_fastapi_shutdown_closes_run_service() -> None:
    app = create_app(workflow_factory=workflow_factory)
    service = app.state.run_service
    with TestClient(app):
        pass

    with pytest.raises(RuntimeError, match="shutdown|shut down"):
        service.submit(CustomerRequirement.model_validate(requirement_payload()))


def test_unknown_run_uses_structured_not_found_error(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=workflow_factory))

    response = client.get("/runs/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "RUN_NOT_FOUND", "message": "Run was not found.", "details": None}
    }


def test_unknown_event_stream_uses_structured_not_found_error(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=workflow_factory))

    response = client.get("/runs/missing/events")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_post_without_workflow_factory_is_unavailable(client_factory) -> None:
    client = client_factory(create_app())

    response = client.post("/runs", json=requirement_payload())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "WORKFLOW_NOT_CONFIGURED"


def test_malformed_requirement_uses_structured_validation_error(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=workflow_factory))

    response = client.post(
        "/runs",
        json={**requirement_payload(), "usage": "unsupported"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_module_level_demo_app_runs_end_to_end(client_factory) -> None:
    client = client_factory(module_app)

    response = client.post("/runs", json=requirement_payload())

    assert response.status_code == 202
    snapshot = wait_for_completion(client, response.json()["run_id"])
    assert snapshot["status"] == "completed"


def test_topology_is_derived_from_canonical_workflow(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=workflow_factory))

    topology = client.get("/workflow/topology")

    assert topology.status_code == 200
    payload = topology.json()
    assert {node["id"] for node in payload["nodes"]} == {
        state.value for state in WorkflowState
    }
    assert len(payload["edges"]) == len(
        {(edge["source"], edge["target"]) for edge in payload["edges"]}
    )


def test_sse_replays_ordered_events_and_supports_reconnect_cursor(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=workflow_factory))
    created = client.post("/runs", json=requirement_payload()).json()
    wait_for_completion(client, created["run_id"])

    with client.stream("GET", f"/runs/{created['run_id']}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        frames = parse_sse(response)

    sequences = [int(frame["id"]) for frame in frames]
    assert sequences == list(range(1, len(sequences) + 1))
    assert all(
        json.loads(frame["data"])["sequence"] == sequence
        for frame, sequence in zip(frames, sequences)
    )

    with client.stream(
        "GET", f"/runs/{created['run_id']}/events?after_sequence=1"
    ) as response:
        replay = parse_sse(response)
    assert [int(frame["id"]) for frame in replay] == sequences[1:]

    with client.stream(
        "GET",
        f"/runs/{created['run_id']}/events",
        headers={"Last-Event-ID": "1"},
    ) as response:
        header_replay = parse_sse(response)
    assert [int(frame["id"]) for frame in header_replay] == sequences[1:]


def test_sse_invalid_last_event_id_is_structured_bad_request(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=workflow_factory))
    created = client.post("/runs", json=requirement_payload()).json()

    response = client.get(
        f"/runs/{created['run_id']}/events",
        headers={"Last-Event-ID": "not-a-sequence"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_failed_run_replays_terminal_failure_without_canceling_server_work(client_factory) -> None:
    client = client_factory(create_app(workflow_factory=failing_workflow_factory))
    created = client.post("/runs", json=requirement_payload()).json()

    snapshot = wait_for_completion(client, created["run_id"])
    assert snapshot["status"] == "failed"
    assert snapshot["error"]

    with client.stream("GET", f"/runs/{created['run_id']}/events") as response:
        frames = parse_sse(response)

    assert frames
    assert json.loads(frames[-1]["data"])["type"] == "workflow.failed"
    assert [int(frame["id"]) for frame in frames] == list(range(1, len(frames) + 1))
