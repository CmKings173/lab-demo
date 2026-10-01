import type {
  CreateRunResponse,
  RequirementForm,
  RunSnapshot,
  WorkflowEvent,
  WorkflowEventType,
  WorkflowTopology,
} from "@/lib/contracts";
import { isFiniteNumber, isRecord, isString, parseApiResponse } from "@/lib/api/http";
import { isRunSnapshot } from "@/lib/api/lab3";

const eventTypes: WorkflowEventType[] = [
  "workflow.started", "workflow.completed", "workflow.failed", "state.started", "state.completed", "state.failed",
  "tool.started", "tool.completed", "tool.failed", "validation.result", "document.hit", "fact.resolved",
  "fact.rejected", "fact.conflict", "proposal.generated", "proposal.verified",
];

function isRunStatus(value: unknown): value is CreateRunResponse["status"] {
  return value === "pending" || value === "running" || value === "completed" || value === "failed";
}

function isCreateRunResponse(value: unknown): value is CreateRunResponse {
  return isRecord(value) && isString(value.run_id) && isRunStatus(value.status);
}

function isWorkflowTopology(value: unknown): value is WorkflowTopology {
  return isRecord(value) && Array.isArray(value.nodes) && value.nodes.every((node) =>
    isRecord(node) && isString(node.id) && isString(node.label) && node.kind === "state" && typeof node.terminal === "boolean") &&
    Array.isArray(value.edges) && value.edges.every((edge) =>
      isRecord(edge) && isString(edge.source) && isString(edge.target) && typeof edge.conditional === "boolean");
}

function isWorkflowEvent(value: unknown): value is WorkflowEvent {
  return isRecord(value) && isString(value.event_id) && isString(value.run_id) &&
    isFiniteNumber(value.sequence) && eventTypes.some((eventType) => eventType === value.type) &&
    isString(value.timestamp) && (value.state === null || isString(value.state)) &&
    (value.duration_ms === null || isFiniteNumber(value.duration_ms)) && isRecord(value.payload);
}

export function fetchTopology(): Promise<WorkflowTopology> {
  return fetch("/api/backend/workflow/topology")
    .then((response) => parseApiResponse(response, isWorkflowTopology, "Workflow topology request failed"));
}

export function createRun(requirement: RequirementForm): Promise<CreateRunResponse> {
  return fetch("/api/backend/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requirement),
  }).then((response) => parseApiResponse(response, isCreateRunResponse, "Workflow run request failed"));
}

export function fetchRun(runId: string): Promise<RunSnapshot> {
  return fetch(`/api/backend/runs/${encodeURIComponent(runId)}`)
    .then((response) => parseApiResponse(response, isRunSnapshot, "Workflow snapshot request failed"));
}

export function subscribeToRun(
  runId: string,
  afterSequence: number,
  onEvent: (event: WorkflowEvent) => void,
  onError: (message: string) => void,
  onConnected: () => void,
  onTerminal: () => void,
): () => void {
  const source = new EventSource(`/api/backend/runs/${encodeURIComponent(runId)}/events?after_sequence=${afterSequence}`);
  let warningShown = false;
  const markConnected = () => {
    warningShown = false;
    onConnected();
  };
  const listeners = eventTypes.map((eventType) => {
    const listener = (message: Event) => {
      const rawData = "data" in message ? message.data : null;
      if (typeof rawData !== "string") {
        onError("Event stream returned an unreadable message.");
        return;
      }
      let payload: unknown;
      try {
        payload = JSON.parse(rawData);
      } catch {
        onError("Event stream returned invalid JSON.");
        return;
      }
      if (!isWorkflowEvent(payload)) {
        onError("Event stream returned an invalid workflow event.");
        return;
      }
      markConnected();
      onEvent(payload);
      if (payload.type === "workflow.completed" || payload.type === "workflow.failed") {
        onTerminal();
        source.close();
      }
    };
    source.addEventListener(eventType, listener);
    return [eventType, listener] as const;
  });
  source.onopen = markConnected;
  source.onerror = () => {
    if (source.readyState !== EventSource.CLOSED && !warningShown) {
      warningShown = true;
      onError("Realtime connection lost; the browser is attempting to reconnect.");
    }
  };
  return () => {
    for (const [eventType, listener] of listeners) source.removeEventListener(eventType, listener);
    source.close();
  };
}
