import type { WorkflowTopology, WorkflowTopologyEdge, WorkflowTopologyNode } from "@/lib/contracts";

export type GraphTransition = {
  edge: WorkflowTopologyEdge;
  target: WorkflowTopologyNode;
};

export type GraphRow = {
  node: WorkflowTopologyNode;
  outgoing: GraphTransition[];
};

export function graphRows(topology: WorkflowTopology): GraphRow[] {
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  return topology.nodes.map((node) => ({
    node,
    outgoing: topology.edges
      .filter((edge) => edge.source === node.id)
      .map((edge) => ({ edge, target: nodesById.get(edge.target) }))
      .filter((transition): transition is GraphTransition => transition.target !== undefined),
  }));
}
