from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from lab2_rag_agent.catalog.repository import InMemoryProductRepository
from lab3_workflow.runtime.http import create_app
from lab3_workflow.tests.test_workflow import build_workflow, make_compatible_product
from shared.contracts import WorkflowState


def workflow_factory():
    return build_workflow(InMemoryProductRepository([make_compatible_product()]))


def failing_workflow_factory():
    class FailingRepository(InMemoryProductRepository):
        def search(self, request):
            raise RuntimeError("catalog unavailable")

    return build_workflow(FailingRepository([make_compatible_product()]))


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


def test_post_run_returns_id_and_background_workflow_completes() -> None:
    client = TestClient(create_app(workflow_factory=workflow_factory))

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


def test_unknown_run_uses_structured_not_found_error() -> None:
    client = TestClient(create_app(workflow_factory=workflow_factory))

    response = client.get("/runs/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "RUN_NOT_FOUND", "message": "Run was not found.", "details": None}
    }


def test_post_without_workflow_factory_is_unavailable() -> None:
    client = TestClient(create_app())

    response = client.post("/runs", json=requirement_payload())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "WORKFLOW_NOT_CONFIGURED"


def test_topology_is_derived_from_canonical_workflow() -> None:
    client = TestClient(create_app(workflow_factory=workflow_factory))

    topology = client.get("/workflow/topology")

    assert topology.status_code == 200
    payload = topology.json()
    assert {node["id"] for node in payload["nodes"]} == {
        state.value for state in WorkflowState
    }
    assert len(payload["edges"]) == len(
        {(edge["source"], edge["target"]) for edge in payload["edges"]}
    )


def test_sse_replays_ordered_events_and_supports_reconnect_cursor() -> None:
    client = TestClient(create_app(workflow_factory=workflow_factory))
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


def test_sse_invalid_last_event_id_is_structured_bad_request() -> None:
    client = TestClient(create_app(workflow_factory=workflow_factory))
    created = client.post("/runs", json=requirement_payload()).json()

    response = client.get(
        f"/runs/{created['run_id']}/events",
        headers={"Last-Event-ID": "not-a-sequence"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_failed_run_replays_terminal_failure_without_canceling_server_work() -> None:
    client = TestClient(create_app(workflow_factory=failing_workflow_factory))
    created = client.post("/runs", json=requirement_payload()).json()

    snapshot = wait_for_completion(client, created["run_id"])
    assert snapshot["status"] == "failed"
    assert snapshot["error"]

    with client.stream("GET", f"/runs/{created['run_id']}/events") as response:
        frames = parse_sse(response)

    assert frames
    assert json.loads(frames[-1]["data"])["type"] == "workflow.failed"
    assert [int(frame["id"]) for frame in frames] == list(range(1, len(frames) + 1))
