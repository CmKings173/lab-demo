import assert from "node:assert/strict";
import test from "node:test";

import { layoutGraph, NODE_WIDTH } from "./graph-layout.ts";
import { edgeVisualState } from "./graph-runtime.ts";
import { nodeStatusFor } from "./fold-events.ts";

const topology = {
  nodes: [
    { id: "start", label: "Start", kind: "state", terminal: false },
    { id: "choose", label: "Choose", kind: "state", terminal: false },
    { id: "success", label: "Success", kind: "state", terminal: true },
    { id: "failed", label: "Failed", kind: "state", terminal: true },
  ],
  edges: [
    { source: "start", target: "choose", conditional: false },
    { source: "choose", target: "success", conditional: true },
    { source: "choose", target: "failed", conditional: true },
  ],
};

function event(sequence, type, state) {
  return { event_id: String(sequence), run_id: "run-1", sequence, type, state, timestamp: "2026-01-01T00:00:00Z", duration_ms: null, payload: {} };
}

test("layout derives all branches and places targets to the right of their real sources", () => {
  const layout = layoutGraph(topology);
  assert.equal(layout.nodes.length, topology.nodes.length);
  assert.equal(layout.edges.length, topology.edges.length);
  const nodes = new Map(layout.nodes.map((item) => [item.node.id, item]));
  for (const { edge, path } of layout.edges) {
    assert.ok(nodes.get(edge.source).x + NODE_WIDTH < nodes.get(edge.target).x);
    assert.match(path, /^M .* C .*$/);
  }
  assert.equal(nodes.get("success").layer, nodes.get("failed").layer);
  assert.notEqual(nodes.get("success").y, nodes.get("failed").y);
});

test("an edge lights only after its route appears in the state event sequence", () => {
  const start = event(1, "state.started", "start");
  const choose = event(2, "state.started", "choose");
  const success = event(3, "state.started", "success");
  assert.equal(edgeVisualState(topology.edges[0], [start]), "idle");
  assert.equal(edgeVisualState(topology.edges[0], [start, choose]), "active");
  assert.equal(edgeVisualState(topology.edges[1], [start, choose]), "idle");
  assert.equal(edgeVisualState(topology.edges[1], [start, choose, success]), "active");
  assert.equal(edgeVisualState(topology.edges[2], [start, choose, success]), "idle");
  assert.equal(edgeVisualState(topology.edges[1], [start, choose, success, event(4, "state.completed", "success")]), "visited");
});

test("a historical event prefix shows the running node instead of its later completed state", () => {
  const started = event(1, "state.started", "choose");
  const completed = event(2, "state.completed", "choose");
  const node = topology.nodes[1];
  assert.equal(nodeStatusFor(node, [started]), "running");
  assert.equal(nodeStatusFor(node, [started, completed]), "completed");
});
