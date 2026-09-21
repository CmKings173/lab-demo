import type { CreateRunResponse, RequirementForm, RunSnapshot, WorkflowEvent, WorkflowEventType, WorkflowTopology } from "@/lib/contracts";

const eventTypes: WorkflowEventType[] = [
  "workflow.started", "workflow.completed", "workflow.failed", "state.started", "state.completed", "state.failed",
  "tool.started", "tool.completed", "tool.failed", "validation.result", "document.hit", "fact.resolved",
  "fact.rejected", "fact.conflict", "proposal.generated", "proposal.verified",
];

async function parseResponse<T extends object>(response: Response): Promise<T> {
  const body = (await response.json()) as T | { error?: { message?: string } };
  if (!response.ok) {
    const message = "error" in body ? body.error?.message : undefined;
    throw new Error(message ?? `Request failed with status ${response.status}`);
  }
  return body as T;
}

export async function fetchTopology(): Promise<WorkflowTopology> {
  return parseResponse<WorkflowTopology>(await fetch("/api/backend/workflow/topology"));
}

export async function createRun(requirement: RequirementForm): Promise<CreateRunResponse> {
  return parseResponse<CreateRunResponse>(await fetch("/api/backend/runs", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requirement),
  }));
}

export async function fetchRun(runId: string): Promise<RunSnapshot> {
  return parseResponse<RunSnapshot>(await fetch(`/api/backend/runs/${encodeURIComponent(runId)}`));
}

export function subscribeToRun(
  runId: string, afterSequence: number, onEvent: (event: WorkflowEvent) => void,
  onError: (message: string) => void, onTerminal: () => void,
): () => void {
  const source = new EventSource(`/api/backend/runs/${encodeURIComponent(runId)}/events?after_sequence=${afterSequence}`);
  const listeners = eventTypes.map((eventType) => {
    const listener = (message: Event) => {
      try {
        const event = JSON.parse((message as MessageEvent<string>).data) as WorkflowEvent;
        onEvent(event);
        if (eventType === "workflow.completed" || eventType === "workflow.failed") {
          onTerminal();
          source.close();
        }
      } catch { onError("Event server trả về dữ liệu không đọc được."); }
    };
    source.addEventListener(eventType, listener);
    return [eventType, listener] as const;
  });
  source.onerror = () => {
    if (source.readyState !== EventSource.CLOSED) onError("Mất kết nối realtime; trình duyệt đang thử nối lại.");
  };
  return () => {
    for (const [eventType, listener] of listeners) source.removeEventListener(eventType, listener);
    source.close();
  };
}
