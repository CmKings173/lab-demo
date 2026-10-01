import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as viewportMath from "./graph-viewport.ts";

// Run the actual hook with deterministic resize notifications and React state.
function harness() {
  const cells = [];
  let cursor = 0, pending, resize, cleanup;
  const react = {
    useRef(initial) {
      const index = cursor++;
      cells[index] ??= { current: initial };
      return cells[index];
    },
    useState(initial) {
      const index = cursor++;
      if (!(index in cells)) cells[index] = initial;
      return [cells[index], value => { cells[index] = typeof value === "function" ? value(cells[index]) : value; }];
    },
    useEffect(effect, dependencies) {
      const index = cursor++;
      if (!cells[index] || dependencies.some((value, i) => value !== cells[index][i])) {
        cells[index] = dependencies;
        pending = effect;
      }
    },
  };
  const exports = {};
  const source = readFileSync(new URL("../components/lab3/hooks/use-workflow-viewport.ts", import.meta.url), "utf8");
  runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
    exports, require: name => name === "react" ? react : viewportMath,
    ResizeObserver: class {
      constructor(callback) { resize = callback; }
      observe() {}
      disconnect() {}
    },
  });
  const element = { clientWidth: 800, clientHeight: 360, scrolls: [],
    scrollTo(value) { this.scrolls.push(value); } };
  function render(layout) {
    cursor = 0;
    const hook = exports.useWorkflowViewport(layout);
    hook.viewportRef.current = element;
    if (pending) {
      cleanup?.();
      cleanup = pending();
      pending = null;
    }
    return hook;
  }
  return { render, element, resize: () => resize() };
}

test("FIT reacts to viewport size; manual zoom survives resize and FIT restores current fit", () => {
  const fixture = harness();
  const layout = { width: 5000, height: 600, nodes: [], edges: [] };
  const before = JSON.stringify(layout);
  fixture.render(layout);
  fixture.resize();
  let hook = fixture.render(layout);
  assert.equal(hook.scale, viewportMath.fitGraphScale(5000, 600, 800, 360));
  fixture.element.clientWidth = 600;
  fixture.resize();
  hook = fixture.render(layout);
  assert.equal(hook.scale, viewportMath.fitGraphScale(5000, 600, 600, 360));
  hook.zoomIn();
  hook = fixture.render(layout);
  const manual = hook.scale;
  fixture.element.clientWidth = 900;
  fixture.resize();
  hook = fixture.render(layout);
  assert.equal(hook.scale, manual);
  hook.fit();
  hook = fixture.render(layout);
  assert.equal(hook.scale, viewportMath.fitGraphScale(5000, 600, 900, 360));
  assert.equal(fixture.element.scrolls.at(-1).left, 0);
  assert.equal(fixture.element.scrolls.at(-1).top, 0);
  assert.equal(JSON.stringify(layout), before);
});

test("ordinary rerenders preserve manual zoom; a changed topology resets to FIT", () => {
  const fixture = harness();
  const layout = { width: 5000, height: 600, nodes: [], edges: [] };
  fixture.render(layout);
  fixture.resize();
  let hook = fixture.render(layout);
  hook.zoomIn();
  hook = fixture.render(layout);
  assert.equal(fixture.render(layout).scale, hook.scale);
  const changed = { ...layout, width: 3000 };
  hook = fixture.render(changed);
  assert.equal(hook.scale, viewportMath.fitGraphScale(3000, 600, 800, 360));
});
