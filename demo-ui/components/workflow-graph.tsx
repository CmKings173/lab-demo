import { useEffect, useMemo, useRef } from "react";

import type { WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { glyphForStatus, labelForStatus, nodeStatusFor } from "@/lib/fold-events";
import { NODE_HEIGHT, NODE_WIDTH, layoutGraph } from "@/lib/graph-layout";
import { edgeVisualState, stateDuration } from "@/lib/graph-runtime";

type WorkflowGraphProps = {
  topology: WorkflowTopology | null;
  events: WorkflowEvent[];
  selectedState: string | null;
  onSelectState: (state: string) => void;
};

export function WorkflowGraph({ topology, events, selectedState, onSelectState }: WorkflowGraphProps) {
  const layout = useMemo(() => topology ? layoutGraph(topology) : null, [topology]);
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const viewport = scrollRef.current;
    const selected = layout?.nodes.find((item) => item.node.id === selectedState);
    if (!viewport || !selected) return;
    viewport.scrollTo({ left: Math.max(0, selected.x - (viewport.clientWidth - NODE_WIDTH) / 2), behavior: "smooth" });
  }, [layout, selectedState]);
  if (!layout) return <div className="empty-state graph-empty" aria-busy="true">Đang tải workflow topology từ server…</div>;

  return <div ref={scrollRef} className="graph-scroll" tabIndex={0} aria-label="Sơ đồ workflow; cuộn ngang để xem các bước tiếp theo">
    <svg className="workflow-canvas" viewBox={`0 0 ${layout.width} ${layout.height}`} width={layout.width} height={layout.height} role="group" aria-label="Workflow topology từ backend">
      <defs>
        <marker id="workflow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" className="arrow-head" />
        </marker>
      </defs>
      <g aria-hidden="true">
        {layout.edges.map(({ edge, path }) => {
          const activity = edgeVisualState(edge, events);
          return <path key={`${edge.source}-${edge.target}`} d={path} markerEnd="url(#workflow-arrow)" className={`flow-edge ${activity} ${edge.conditional ? "conditional" : ""}`} />;
        })}
      </g>
      {layout.nodes.map(({ node, x, y }) => {
        const status = nodeStatusFor(node, events);
        const duration = stateDuration(node.id, events);
        const selected = selectedState === node.id;
        return <foreignObject key={node.id} x={x} y={y} width={NODE_WIDTH} height={NODE_HEIGHT}>
          <button
            type="button"
            className={`canvas-node ${status} ${selected ? "selected" : ""} ${node.terminal ? "terminal" : ""}`}
            onClick={() => onSelectState(node.id)}
            aria-pressed={selected}
            aria-label={`${node.label}, ${labelForStatus(status)}${duration === null ? "" : `, ${duration} ms`}`}
          >
            <span className="canvas-node-top"><span className="canvas-node-label">{node.label}</span><span className="canvas-node-glyph" aria-hidden="true">{glyphForStatus(status)}</span></span>
            <span className="canvas-node-bottom"><span>{node.terminal ? "Terminal" : labelForStatus(status)}</span><span className="mono">{duration === null ? "—" : `${duration} ms`}</span></span>
          </button>
        </foreignObject>;
      })}
    </svg>
  </div>;
}
