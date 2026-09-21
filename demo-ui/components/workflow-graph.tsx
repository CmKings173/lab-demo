import type { WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { glyphForStatus, nodeStatusFor } from "@/lib/fold-events";
import { graphRows } from "@/lib/graph-layout";

type WorkflowGraphProps = { topology: WorkflowTopology | null; events: WorkflowEvent[]; selectedEvent: WorkflowEvent | null; onSelectState: (state: string) => void; };

export function WorkflowGraph({ topology, events, selectedEvent, onSelectState }: WorkflowGraphProps) {
  if (!topology) return <div className="empty-state" aria-busy="true">Đang tải canonical topology…</div>;
  return <div className="graph-list" aria-label="Live workflow graph">
    {graphRows(topology).map(({ node, outgoing }) => {
      const status = nodeStatusFor(node, events);
      const selected = selectedEvent?.state === node.id;
      return <div className="graph-node-wrap" key={node.id}>
        <button className={`graph-node ${status} ${selected ? "selected" : ""}`} type="button" onClick={() => onSelectState(node.id)} aria-pressed={selected}>
          <span className="node-glyph" aria-hidden="true">{glyphForStatus(status)}</span><span className="node-copy"><strong>{node.label}</strong><span>{status}</span></span>
        </button>
        {outgoing.length > 0 ? <div className="graph-branches" aria-label={`Transitions from ${node.label}`}>
          {outgoing.map(({ edge, target }) => <button
            className="graph-branch"
            key={`${edge.source}-${edge.target}`}
            type="button"
            onClick={() => onSelectState(target.id)}
            aria-label={`${node.label} to ${target.label}${edge.conditional ? " conditional" : ""}`}
          >
            <span className="branch-glyph" aria-hidden="true">{outgoing.length > 1 ? "├─" : "↓"}</span>
            <span className="branch-copy"><strong>{target.label}</strong><span>{edge.conditional ? "conditional" : "next"}</span></span>
          </button>)}
        </div> : null}
      </div>;
    })}
  </div>;
}
