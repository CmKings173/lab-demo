import type { WorkflowEvent, WorkflowTopologyEdge } from "@/lib/contracts";

export type EdgeVisualState = "idle" | "visited" | "active";

/** Only consecutive state.started events can prove a route was traversed. */
export function traversedEdges(events: WorkflowEvent[]): Set<string> {
  const states = events.filter((event) => event.type === "state.started" && event.state).map((event) => event.state as string);
  const traversed = new Set<string>();
  for (let index = 1; index < states.length; index += 1) {
    traversed.add(`${states[index - 1]}→${states[index]}`);
  }
  return traversed;
}

export function edgeVisualState(edge: WorkflowTopologyEdge, events: WorkflowEvent[]): EdgeVisualState {
  const route = `${edge.source}→${edge.target}`;
  const traversed = traversedEdges(events);
  if (!traversed.has(route)) return "idle";
  const lastStarted = events.findLast((event) => event.type === "state.started" && event.state);
  const lastEvent = events.at(-1);
  if (lastStarted?.state === edge.target && lastEvent && !["workflow.completed", "workflow.failed"].includes(lastEvent.type)) {
    const settled = events.some((event) => event.sequence > lastStarted.sequence && event.state === edge.target && (event.type === "state.completed" || event.type === "state.failed"));
    if (!settled) return "active";
  }
  return "visited";
}

export function stateDuration(state: string, events: WorkflowEvent[]): number | null {
  return events.findLast((event) => event.state === state && (event.type === "state.completed" || event.type === "state.failed"))?.duration_ms ?? null;
}
