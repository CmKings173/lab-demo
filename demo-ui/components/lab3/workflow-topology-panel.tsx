import { useMemo } from "react";

import type { WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { WorkflowGraph } from "@/components/workflow-graph";
import { layoutGraph } from "@/lib/graph-layout";
import { useWorkflowViewport } from "./hooks/use-workflow-viewport";

export function WorkflowTopologyPanel({
  topology,
  events,
  selectedState,
  onSelectState,
}: {
  topology: WorkflowTopology | null;
  events: WorkflowEvent[];
  selectedState: string | null;
  onSelectState: (state: string) => void;
}) {
  const layout = useMemo(() => topology ? layoutGraph(topology) : null, [topology]);
  const viewport = useWorkflowViewport(layout);
  return <section className="lab3-topology" aria-labelledby="lab3-topology-heading">
    <div className="lab3-section-heading"><h2 id="lab3-topology-heading">DAG TOPOLOGY</h2><span>{topology ? `${topology.nodes.length} nodes · ${topology.edges.length} transitions` : "Loading topology"}</span><div className="lab3-legend"><span><i className="pending" />PENDING</span><span><i className="running" />ACTIVE</span><span><i className="completed" />DONE</span><span><i className="failed" />FAILED</span></div>
      <div className="lab3-zoom" role="group" aria-label="Workflow zoom">
        <button type="button" aria-label="Zoom out" disabled={!viewport.canZoomOut} onClick={viewport.zoomOut}>−</button>
        <output aria-label="Current zoom">{Math.round(viewport.scale * 100)}%</output>
        <button type="button" aria-label="Zoom in" disabled={!viewport.canZoomIn} onClick={viewport.zoomIn}>+</button>
        <button type="button" aria-label="Fit workflow" disabled={!layout} onClick={viewport.fit}>FIT</button>
      </div>
    </div>
    <WorkflowGraph layout={layout} scale={viewport.scale} viewportRef={viewport.viewportRef}
      events={events} selectedState={selectedState} onSelectState={onSelectState} />
  </section>;
}
