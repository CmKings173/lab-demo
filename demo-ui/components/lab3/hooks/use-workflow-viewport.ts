import { useEffect, useRef, useState } from "react";

import type { GraphLayout } from "@/lib/graph-layout";
import { fitGraphScale, zoomGraphScale, MIN_GRAPH_ZOOM, MAX_GRAPH_ZOOM } from "@/lib/graph-viewport";

export function useWorkflowViewport(layout: GraphLayout | null) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState({ width: 0, height: 0 });
  const [manualZoom, setManualZoom] = useState<{ layout: GraphLayout; scale: number } | null>(null);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      const next = { width: element.clientWidth, height: element.clientHeight };
      setViewport((previous) => Math.abs(previous.width - next.width) >= 1 ||
        Math.abs(previous.height - next.height) >= 1 ? next : previous);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [layout]);

  const fitScale = layout ? fitGraphScale(layout.width, layout.height, viewport.width, viewport.height) : 1;
  const scale = manualZoom?.layout === layout ? manualZoom.scale : fitScale;
  function zoom(direction: -1 | 1) {
    if (layout) setManualZoom({ layout, scale: zoomGraphScale(scale, direction, fitScale) });
  }
  function fit() {
    setManualZoom(null);
    viewportRef.current?.scrollTo({ left: 0, top: 0 });
  }

  return { viewportRef, scale, fit, zoomIn: () => zoom(1), zoomOut: () => zoom(-1),
    canZoomOut: !!layout && scale > Math.min(MIN_GRAPH_ZOOM, fitScale),
    canZoomIn: !!layout && scale < MAX_GRAPH_ZOOM };
}
