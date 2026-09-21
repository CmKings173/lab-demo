from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .enums import WorkflowState
from .models import ContractModel


class WorkflowEventType(StrEnum):
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    STATE_STARTED = "state.started"
    STATE_COMPLETED = "state.completed"
    STATE_FAILED = "state.failed"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    VALIDATION_RESULT = "validation.result"
    DOCUMENT_HIT = "document.hit"
    FACT_RESOLVED = "fact.resolved"
    FACT_REJECTED = "fact.rejected"
    FACT_CONFLICT = "fact.conflict"
    PROPOSAL_GENERATED = "proposal.generated"
    PROPOSAL_VERIFIED = "proposal.verified"


class WorkflowEvent(ContractModel):
    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    type: WorkflowEventType
    timestamp: datetime
    state: WorkflowState | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    payload: dict[str, object] = Field(default_factory=dict)

    @field_validator("event_id", "run_id")
    @classmethod
    def reject_blank_identifiers(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier must not be blank")
        return value

    @model_validator(mode="after")
    def validate_event_boundary(self) -> WorkflowEvent:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        try:
            json.dumps(self.payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("payload must be JSON-serializable") from exc
        return self


class WorkflowTopologyNode(ContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: Literal["state"] = "state"
    terminal: bool

    @field_validator("id", "label")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("topology text must not be blank")
        return value


class WorkflowTopologyEdge(ContractModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    conditional: bool = False

    @field_validator("source", "target")
    @classmethod
    def reject_blank_endpoints(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("topology endpoint must not be blank")
        return value


class WorkflowTopology(ContractModel):
    nodes: list[WorkflowTopologyNode] = Field(default_factory=list)
    edges: list[WorkflowTopologyEdge] = Field(default_factory=list)

    @classmethod
    def from_transitions(
        cls,
        transitions: Mapping[WorkflowState, Iterable[WorkflowState]],
    ) -> WorkflowTopology:
        normalized = {
            source: set(targets)
            for source, targets in transitions.items()
        }
        nodes = [
            WorkflowTopologyNode(
                id=state.value,
                label=state.value.replace("_", " ").title(),
                terminal=not normalized.get(state, set()),
            )
            for state in WorkflowState
        ]
        edges = [
            WorkflowTopologyEdge(
                source=source.value,
                target=target.value,
                conditional=len(normalized[source]) > 1,
            )
            for source in sorted(normalized, key=lambda item: item.value)
            for target in sorted(normalized[source], key=lambda item: item.value)
        ]
        return cls(nodes=nodes, edges=edges)

    @model_validator(mode="after")
    def validate_graph_invariants(self) -> WorkflowTopology:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("topology node ids must be unique")

        edge_pairs = [(edge.source, edge.target) for edge in self.edges]
        if len(edge_pairs) != len(set(edge_pairs)):
            raise ValueError("topology edges must be unique")

        known_node_ids = set(node_ids)
        outgoing_sources = {edge.source for edge in self.edges}
        for edge in self.edges:
            if edge.source not in known_node_ids or edge.target not in known_node_ids:
                raise ValueError("topology edges must reference known nodes")

        for node in self.nodes:
            has_outgoing_edge = node.id in outgoing_sources
            if node.terminal != (not has_outgoing_edge):
                raise ValueError("terminal flag must match outgoing edges")
        return self
