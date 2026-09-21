import type { NodeStatus, WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { glyphForStatus } from "@/lib/fold-events";

type WorkflowGraphProps = { topology: WorkflowTopology | null; events: WorkflowEvent[]; selectedEvent: WorkflowEvent | null; onSelectState: (state: string) => void; };

function statusForNode(nodeId: string, events: WorkflowEvent[]): NodeStatus {
  const stateEvents = events.filter((event) => event.state === nodeId);
  if (stateEvents.some((event) => event.type === "state.failed")) return "failed";
  if (stateEvents.some((event) => event.type === "state.completed")) return "completed";
  if (stateEvents.some((event) => event.type === "state.started")) return "running";
  return "pending";
}

export function WorkflowGraph({ topology, events, selectedEvent, onSelectState }: WorkflowGraphProps) {
  if (!topology) return <div className="empty-state" aria-busy="true">Đang tải canonical topology…</div>;
  return <div className="graph-list" aria-label="Live workflow graph">
    {topology.nodes.map((node, index) => {
      const status = statusForNode(node.id, events);
      const selected = selectedEvent?.state === node.id;
      const hasOutgoing = topology.edges.some((edge) => edge.source === node.id);
      return <div className="graph-node-wrap" key={node.id}>
        <button className={`graph-node ${status} ${selected ? "selected" : ""}`} type="button" onClick={() => onSelectState(node.id)} aria-pressed={selected}>
          <span className="node-glyph" aria-hidden="true">{glyphForStatus(status)}</span><span className="node-copy"><strong>{node.label}</strong><span>{status}</span></span>
        </button>
        {index < topology.nodes.length - 1 && hasOutgoing ? <div className="graph-edge" aria-hidden="true">↓</div> : null}
      </div>;
    })}
  </div>;
}
