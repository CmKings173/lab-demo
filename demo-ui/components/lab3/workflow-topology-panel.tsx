import type { WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { WorkflowGraph } from "@/components/workflow-graph";

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
  return <section className="lab3-topology" aria-labelledby="lab3-topology-heading">
    <div className="lab3-section-heading"><h2 id="lab3-topology-heading">DAG TOPOLOGY</h2><span>{topology ? `${topology.nodes.length} nodes · ${topology.edges.length} transitions` : "Loading topology"}</span><div className="lab3-legend"><span><i className="pending" />PENDING</span><span><i className="running" />ACTIVE</span><span><i className="completed" />DONE</span><span><i className="failed" />FAILED</span></div></div>
    <WorkflowGraph topology={topology} events={events} selectedState={selectedState} onSelectState={onSelectState} />
  </section>;
}
