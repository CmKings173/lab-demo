import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from lab3_workflow.workflow.orchestrator import DeterministicWorkflow
from shared.contracts import (
    WorkflowEvent,
    WorkflowEventType,
    WorkflowState,
    WorkflowTopology,
    WorkflowTopologyEdge,
    WorkflowTopologyNode,
)


def _event_data() -> dict[str, object]:
    return {
        "event_id": "event-1",
        "run_id": "run-1",
        "sequence": 1,
        "type": WorkflowEventType.WORKFLOW_STARTED,
        "timestamp": datetime.now(timezone.utc),
        "state": WorkflowState.RECEIVED,
        "duration_ms": 0,
        "payload": {"request": "demo"},
    }


def test_topology_nodes_match_workflow_states() -> None:
    topology = DeterministicWorkflow.describe_topology()

    assert {node.id for node in topology.nodes} == {
        state.value for state in WorkflowState
    }


def test_topology_edges_match_canonical_transitions() -> None:
    topology = DeterministicWorkflow.describe_topology()
    actual_edges = {(edge.source, edge.target) for edge in topology.edges}
    expected_edges = {
        (source.value, target.value)
        for source, targets in DeterministicWorkflow._ALLOWED_TRANSITIONS.items()
        for target in targets
    }

    assert actual_edges == expected_edges


def test_topology_has_no_duplicate_edges() -> None:
    topology = DeterministicWorkflow.describe_topology()
    edges = [(edge.source, edge.target) for edge in topology.edges]

    assert len(edges) == len(set(edges))


def test_terminal_states_have_no_outgoing_edges() -> None:
    topology = DeterministicWorkflow.describe_topology()
    outgoing = {edge.source for edge in topology.edges}

    for state, targets in DeterministicWorkflow._ALLOWED_TRANSITIONS.items():
        if not targets:
            assert state.value not in outgoing


def test_workflow_event_is_json_serializable() -> None:
    event = WorkflowEvent.model_validate(_event_data())

    encoded = event.model_dump_json()

    assert json.loads(encoded)["event_id"] == "event-1"


@pytest.mark.parametrize("sequence", [0, -1])
def test_workflow_event_rejects_invalid_sequence(sequence: int) -> None:
    data = _event_data()
    data["sequence"] = sequence

    with pytest.raises(ValidationError):
        WorkflowEvent.model_validate(data)


def test_workflow_event_rejects_negative_duration() -> None:
    data = _event_data()
    data["duration_ms"] = -1

    with pytest.raises(ValidationError):
        WorkflowEvent.model_validate(data)


@pytest.mark.parametrize("field", ["event_id", "run_id"])
def test_workflow_event_rejects_blank_identifiers(field: str) -> None:
    data = _event_data()
    data[field] = "   "

    with pytest.raises(ValidationError):
        WorkflowEvent.model_validate(data)


def test_workflow_event_rejects_non_json_payload() -> None:
    data = _event_data()
    data["payload"] = {"unsafe": object()}

    with pytest.raises(ValidationError):
        WorkflowEvent.model_validate(data)


def test_workflow_event_rejects_unknown_extra_fields() -> None:
    data = _event_data()
    data["unexpected"] = True

    with pytest.raises(ValidationError):
        WorkflowEvent.model_validate(data)


def test_workflow_topology_rejects_duplicate_node_ids() -> None:
    node = WorkflowTopologyNode(id="analyze", label="Analyze", terminal=True)

    with pytest.raises(ValidationError):
        WorkflowTopology(nodes=[node, node], edges=[])


def test_workflow_topology_rejects_dangling_edges() -> None:
    nodes = [WorkflowTopologyNode(id="analyze", label="Analyze", terminal=True)]
    edges = [WorkflowTopologyEdge(source="analyze", target="missing")]

    with pytest.raises(ValidationError):
        WorkflowTopology(nodes=nodes, edges=edges)


def test_workflow_topology_rejects_terminal_node_with_outgoing_edge() -> None:
    nodes = [
        WorkflowTopologyNode(id="analyze", label="Analyze", terminal=True),
        WorkflowTopologyNode(id="size", label="Size", terminal=True),
    ]
    edges = [WorkflowTopologyEdge(source="analyze", target="size")]

    with pytest.raises(ValidationError):
        WorkflowTopology(nodes=nodes, edges=edges)
