import type { WorkflowTopology, WorkflowTopologyEdge, WorkflowTopologyNode } from "@/lib/contracts";

export const NODE_WIDTH = 184;
export const NODE_HEIGHT = 72;
const COLUMN_GAP = 108;
const ROW_GAP = 24;
const PADDING = 32;

export type PositionedNode = {
  node: WorkflowTopologyNode;
  x: number;
  y: number;
  layer: number;
};

export type PositionedEdge = {
  edge: WorkflowTopologyEdge;
  path: string;
};

export type GraphLayout = {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  width: number;
  height: number;
};

/** Layout only the graph supplied by the backend. No workflow state is defined here. */
export function layoutGraph(topology: WorkflowTopology): GraphLayout {
  const index = new Map(topology.nodes.map((node, position) => [node.id, position]));
  const indegree = new Map(topology.nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(topology.nodes.map((node) => [node.id, [] as WorkflowTopologyEdge[]]));
  const layer = new Map(topology.nodes.map((node) => [node.id, 0]));

  for (const edge of topology.edges) {
    if (!indegree.has(edge.source) || !indegree.has(edge.target)) continue;
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
    outgoing.get(edge.source)?.push(edge);
  }

  const queue = topology.nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id);
  for (let cursor = 0; cursor < queue.length; cursor += 1) {
    const source = queue[cursor];
    for (const edge of outgoing.get(source) ?? []) {
      layer.set(edge.target, Math.max(layer.get(edge.target) ?? 0, (layer.get(source) ?? 0) + 1));
      const next = (indegree.get(edge.target) ?? 0) - 1;
      indegree.set(edge.target, next);
      if (next === 0) queue.push(edge.target);
    }
  }

  const columns = new Map<number, WorkflowTopologyNode[]>();
  for (const node of topology.nodes) {
    const depth = layer.get(node.id) ?? 0;
    const column = columns.get(depth) ?? [];
    column.push(node);
    columns.set(depth, column);
  }
  const depths = [...columns.keys()].sort((a, b) => a - b);
  const maxRows = Math.max(1, ...[...columns.values()].map((column) => column.length));
  const height = Math.max(340, maxRows * NODE_HEIGHT + (maxRows - 1) * ROW_GAP + PADDING * 2);
  const width = Math.max(640, (Math.max(0, ...depths) + 1) * (NODE_WIDTH + COLUMN_GAP) - COLUMN_GAP + PADDING * 2);
  const positioned: PositionedNode[] = [];

  for (const depth of depths) {
    const column = columns.get(depth) ?? [];
    column.sort((a, b) => Number(a.terminal) - Number(b.terminal) || (index.get(a.id) ?? 0) - (index.get(b.id) ?? 0));
    const columnHeight = column.length * NODE_HEIGHT + Math.max(0, column.length - 1) * ROW_GAP;
    column.forEach((node, row) => positioned.push({
      node,
      x: PADDING + depth * (NODE_WIDTH + COLUMN_GAP),
      y: (height - columnHeight) / 2 + row * (NODE_HEIGHT + ROW_GAP),
      layer: depth,
    }));
  }

  const byId = new Map(positioned.map((item) => [item.node.id, item]));
  const edges = topology.edges.flatMap((edge): PositionedEdge[] => {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) return [];
    const x1 = source.x + NODE_WIDTH;
    const y1 = source.y + NODE_HEIGHT / 2;
    const x2 = target.x;
    const y2 = target.y + NODE_HEIGHT / 2;
    const middle = (x1 + x2) / 2;
    return [{ edge, path: `M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}` }];
  });

  return { nodes: positioned, edges, width, height };
}
