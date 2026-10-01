import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute the actual component/handler; only the DOM form ref is substituted.
const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../components/lab3/conversation-panel.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function render(overrides = {}) {
  let submissions = 0;
  const exports = {};
  runInNewContext(compiled, {
    exports,
    require: (name) => name === "react"
      ? { useRef: () => ({ current: { requestSubmit: () => submissions++ } }) }
      : require(name),
  });
  const onSubmit = () => {};
  const element = exports.ConversationPanel({
    messages: [], draft: "hello", busy: false, runActive: false, creationBusy: false,
    error: null, onDraftChange() {}, onSubmit, onNewConversation() {}, ...overrides,
  });
  function find(node, type) {
    if (!node || typeof node !== "object") return undefined;
    if (typeof type === "function" ? type(node) : node.type === type) return node;
    return [node.props?.children].flat(Infinity).map((child) => find(child, type)).find(Boolean);
  }
  return { alert: find(element, (node) => node.props?.role === "alert"),
    textarea: find(element, "textarea"), form: find(element, "form"),
    button: find(find(element, "form"), "button"), onSubmit, count: () => submissions };
}

for (const [name, shiftKey, isComposing, expected] of [
  ["Enter sends through requestSubmit", false, false, 1],
  ["Shift+Enter keeps the native newline", true, false, 0],
  ["IME Enter never sends", false, true, 0],
]) {
  test(name, () => {
    const panel = render();
    let prevented = 0;
    panel.textarea.props.onKeyDown({ key: "Enter", shiftKey,
      nativeEvent: { isComposing }, preventDefault: () => prevented++ });
    assert.equal(panel.count(), expected);
    assert.equal(prevented, expected);
    assert.equal(panel.form.props.onSubmit, panel.onSubmit);
    assert.equal(panel.textarea.props.maxLength, 4000);
  });
}

test("helper text documents keyboard behavior", () => {
  assert.match(source, /Enter to send \| Shift\+Enter for a new line/);
});

test("Lab3 conversation uses CNTTShop identity and displays the sanitized diagnostic code", () => {
  const safeError = "[LLM_ADVISOR_RESPONSE_INVALID] The model could not produce a valid advisor response.";
  const panel = render({ error: safeError });
  assert.match(source, /CNTTShop Advisor/);
  assert.doesNotMatch(source, /QWEN ADVISOR/);
  assert.equal(panel.alert.props.children, safeError);
});

for (const lockingState of [{ busy: true }, { runActive: true }, { creationBusy: true }]) {
  test(`locked composer remains disabled: ${Object.keys(lockingState)[0]}`, () => {
    const panel = render(lockingState);
    assert.equal(panel.textarea.props.disabled, true);
    assert.equal(panel.button.props.disabled, true);
  });
}

test("repeated evidence URLs preserve references without duplicate React sibling keys", () => {
  const proposalSource = readFileSync(new URL("../components/proposal-panel.tsx", import.meta.url), "utf8");
  const exports = {};
  runInNewContext(ts.transpileModule(proposalSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, require });
  const sources = ["https://example.invalid/doc", "https://example.invalid/doc"];
  const item = { configuration_id: "fixture", product_name: "Fixture", ram_gb: null,
    storage_gb: null, estimated_price_vnd: null, evidence_sources: sources };
  const tree = exports.ProposalPanel({ finalState: "complete", snapshot: { result: { proposal: {
    option_count: 0, evidence_count: 2, selected_configuration_ids: ["fixture"],
    estimated_price_vnd: null, selected_configurations: [item], options: [],
    limitations: [], sources,
  } } } });
  let repeatedLists = 0;
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (typeof node.type === "function") return visit(node.type(node.props));
    const children = [node.props?.children].flat(Infinity).filter(Boolean);
    if (node.type === "ul" && children.length === 2) {
      repeatedLists++;
      assert.equal(new Set(children.map((child) => child.key)).size, 2);
      assert.deepEqual(children.map((child) => child.props.children.props.href), sources);
    }
    children.forEach(visit);
  }
  visit(tree);
  assert.equal(repeatedLists, 2); // configuration evidence and overall proposal sources
});
