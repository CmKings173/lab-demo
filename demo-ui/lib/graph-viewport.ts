export const GRAPH_VIEWPORT_PADDING = 16;
export const MIN_GRAPH_ZOOM = 0.3;
export const MAX_GRAPH_ZOOM = 2;
const ZOOM_STEP = 0.1;

export function fitGraphScale(width: number, height: number,
  viewportWidth: number, viewportHeight: number): number {
  if (width <= 0 || height <= 0 || viewportWidth <= 0 || viewportHeight <= 0) return 1;
  return Math.min(1, Math.max(1, viewportWidth - GRAPH_VIEWPORT_PADDING * 2) / width,
    Math.max(1, viewportHeight - GRAPH_VIEWPORT_PADDING * 2) / height);
}

export function zoomGraphScale(scale: number, direction: -1 | 1, fitScale: number): number {
  // Wide topologies must still fit below the nominal 30% manual zoom floor.
  const minimum = Math.min(MIN_GRAPH_ZOOM, fitScale);
  const next = Math.round((scale + direction * ZOOM_STEP) * 1000) / 1000;
  return Math.max(minimum, Math.min(MAX_GRAPH_ZOOM, next));
}

export function selectedNodeScroll(node: { x: number; y: number; width: number; height: number },
  graph: { width: number; height: number }, viewport: { width: number; height: number },
  scale: number): { left: number; top: number } {
  const center = (position: number, nodeSize: number, graphSize: number, viewportSize: number) =>
    Math.max(0, Math.min(graphSize * scale + GRAPH_VIEWPORT_PADDING * 2 - viewportSize,
      (position + nodeSize / 2) * scale + GRAPH_VIEWPORT_PADDING - viewportSize / 2));
  return { left: center(node.x, node.width, graph.width, viewport.width),
    top: center(node.y, node.height, graph.height, viewport.height) };
}
