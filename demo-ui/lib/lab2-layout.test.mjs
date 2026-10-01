import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const react = { ...require("react"), useEffect() {}, useRef: () => ({ current: null }) };
const styles = { default: new Proxy({}, { get: (_, key) => String(key) }), __esModule: true };

function panel(state = "idle") {
  const cache = new Map();
  function load(url) {
    if (cache.has(url.href)) return cache.get(url.href);
    const exports = {};
    cache.set(url.href, exports);
    const source = readFileSync(url, "utf8");
    const compiled = ts.transpileModule(source, { compilerOptions: {
      module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
    } }).outputText;
    runInNewContext(compiled, { exports, require: name => {
      if (name === "react") return react;
      if (name.endsWith(".module.css")) return styles;
      if (name === "./hooks/use-lab2-chat") return { useLab2Chat: () => ({
        messages: [], draft: "", requestState: state, error: null,
        traceReason: "Not exposed by current chat endpoint", setDraft() {}, submit() {},
        startNewConversation() {},
      }) };
      if (name === "@/lib/lab2-config") return load(new URL("./lab2-config.ts", import.meta.url));
      if (name === "./lab2-contracts") return load(new URL("./lab2-contracts.ts", import.meta.url));
      if (name.startsWith("./")) return load(new URL(`${name}.tsx`, url));
      return require(name);
    } });
    return exports;
  }
  return renderToStaticMarkup(load(new URL("../components/lab2/lab2-panel.tsx", import.meta.url)).Lab2Panel());
}

test("Lab2 primary layout leads with CNTTShop chat and truthful compact runtime", () => {
  const html = panel();
  assert.match(html, /CNTTShop Advisor/);
  assert.ok(html.indexOf('id="chat-title"') < html.indexOf('aria-label="Lab2 runtime"'));
  assert.match(html, /Configured data sources/);
  assert.match(html, /PostgreSQL/);
  assert.match(html, /WeKnora/);
  assert.match(html, /Qwen\/Qwen3-14B/);
  assert.match(html, /Not exposed by current chat endpoint/);
  assert.doesNotMatch(html, /Tool execution trace|NOT AVAILABLE|Healthy data sources|LAB2 AGENT/);
  assert.doesNotMatch(html, /current tool|\d+ products found|database healthy/i);
});

test("one initially collapsed architecture view retains exactly the existing six tools", () => {
  const html = panel();
  const details = html.match(/<details\b[^>]*>[\s\S]*?<\/details>/g);
  assert.equal(details?.length, 1);
  assert.doesNotMatch(details[0], /^<details[^>]*\bopen\b/);
  assert.match(details[0], /Architecture &amp; tools/);
  assert.match(details[0], /not a live execution trace/);
  const names = [...details[0].matchAll(/<strong>(search_products|get_product|search_product_documents|compare_products|compare_configurations|estimate_ai_requirements)<\/strong>/g)].map(match => match[1]);
  assert.deepEqual(names, ["search_products", "get_product", "search_product_documents",
    "compare_products", "compare_configurations", "estimate_ai_requirements"]);
  assert.doesNotMatch(details[0], /ingestion/);
});

test("runtime request status follows the real chat state", () => {
  for (const state of ["idle", "sending", "received", "failed"]) {
    assert.match(panel(state), new RegExp(`Request state<\\/dt><dd[^>]*>${state}<\\/dd>`));
  }
});
