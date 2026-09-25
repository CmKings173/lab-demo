import type { NodeStatus, WorkflowEvent, WorkflowTopologyNode } from "@/lib/contracts";

export function nodeStatusFor(node: WorkflowTopologyNode, events: WorkflowEvent[]): NodeStatus {
  const stateEvents = events.filter((event) => event.state === node.id);
  if (stateEvents.some((event) => event.type === "state.failed")) return "failed";
  if (stateEvents.some((event) => event.type === "state.completed")) return "completed";
  if (stateEvents.some((event) => event.type === "state.started")) return "running";
  return "pending";
}

export function glyphForStatus(status: NodeStatus): string {
  if (status === "running") return "◉";
  if (status === "completed") return "✓";
  if (status === "failed") return "!";
  return "○";
}

export function labelForStatus(status: NodeStatus): string {
  if (status === "running") return "Đang chạy";
  if (status === "completed") return "Hoàn tất";
  if (status === "failed") return "Lỗi";
  return "Chờ";
}
