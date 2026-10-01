import assert from "node:assert/strict";
import { test } from "node:test";
import { fitGraphScale, zoomGraphScale, selectedNodeScroll } from "./graph-viewport.ts";

test("FIT contains both dimensions, including wide graphs on narrow viewports", () => {
  for (const [width, height] of [[1440, 360], [768, 360], [320, 360]]) {
    const scale = fitGraphScale(5000, 600, width, height);
    assert.ok(scale > 0 && scale <= 1);
    assert.ok(5000 * scale <= width - 32);
    assert.ok(600 * scale <= height - 32);
  }
  assert.equal(fitGraphScale(200, 100, 1440, 360), 1);
  assert.equal(fitGraphScale(5000, 600, 0, 0), 1); // not measured yet
});

test("zoom steps increase/decrease scale, clamp at fit-aware minimum and 200%", () => {
  assert.equal(zoomGraphScale(0.7, 1, 0.5), 0.8);
  assert.equal(zoomGraphScale(0.7, -1, 0.5), 0.6);
  assert.equal(zoomGraphScale(0.3, -1, 0.5), 0.3);
  assert.equal(zoomGraphScale(1.95, 1, 0.5), 2);
  const fit = fitGraphScale(5000, 600, 800, 360);
  assert.equal(zoomGraphScale(fit, -1, fit), fit);
  assert.ok(zoomGraphScale(fit, 1, fit) > fit);
});

test("selected-node centering scales coordinates and clamps to the rendered canvas", () => {
  const graph = { width: 5000, height: 600 };
  const viewport = { width: 800, height: 360 };
  const node = (x, y) => ({ x, y, width: 184, height: 72 });
  assert.deepEqual(selectedNodeScroll(node(1000, 300), graph, viewport, 0.5),
    { left: 162, top: 0 });
  assert.deepEqual(selectedNodeScroll(node(0, 0), graph, viewport, 0.5),
    { left: 0, top: 0 });
  assert.deepEqual(selectedNodeScroll(node(4800, 500), graph, viewport, 2),
    { left: 9232, top: 872 });
  assert.deepEqual(selectedNodeScroll(node(4800, 500), graph, viewport,
    fitGraphScale(graph.width, graph.height, viewport.width, viewport.height)),
    { left: 0, top: 0 });
});
