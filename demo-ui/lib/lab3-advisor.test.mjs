import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks, stripTypeScriptTypes } from "node:module";
import { test } from "node:test";

const httpUrl = new URL("./api/http.ts", import.meta.url).href;
const reactHarness = { cells: [], cursor: 0 };
globalThis.__lab3HookTest = reactHarness;
const reactStub = "data:text/javascript," + encodeURIComponent(`
export function useState(initial) {
  const h = globalThis.__lab3HookTest, i = h.cursor++;
  if (!(i in h.cells)) h.cells[i] = initial;
  return [h.cells[i], value => { h.cells[i] = typeof value === 'function' ? value(h.cells[i]) : value; }];
}
export function useRef(initial) {
  const h = globalThis.__lab3HookTest, i = h.cursor++;
  if (!(i in h.cells)) h.cells[i] = {current: initial};
  return h.cells[i];
}
export function useCallback(fn) { return fn; }
`);
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "react" && context.parentURL?.endsWith("/use-lab3-conversation.ts")) {
      return nextResolve(reactStub, context);
    }
    if (specifier === "@/lib/api/lab3") {
      return nextResolve(new URL("./api/lab3.ts", import.meta.url).href, context);
    }
    if (specifier === "@/lib/lab3-contracts") {
      return nextResolve(new URL("./lab3-contracts.ts", import.meta.url).href, context);
    }
    if (specifier === "./http" && context.parentURL?.endsWith("/api/lab3.ts")) {
      return nextResolve(httpUrl, context);
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === httpUrl) return {
      format: "module", shortCircuit: true,
      source: stripTypeScriptTypes(readFileSync(new URL(url), "utf8"), { mode: "transform" }),
    };
    return nextLoad(url, context);
  },
});
const { submitConversation, fetchRunExplanation } = await import("./api/lab3.ts");
const { useLab3Conversation } = await import("../components/lab3/hooks/use-lab3-conversation.ts");
const requirement = {
  model_size_b: null, usage: null, budget_vnd: null, concurrent_users: null,
  context_length: null, storage_requirement_gb: null, expansion_requirement: null,
  training_method: null,
};
const conversation = [
  { role: "user", content: "14B" },
  { role: "assistant", content: "Inference hay fine-tune?" },
  { role: "user", content: "ý là sao?" },
];
async function withResponse(payload, operation) {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, body: JSON.parse(options.body) });
    return Response.json(payload);
  };
  try { await operation(requests); } finally { globalThis.fetch = original; }
}

test("conversation reply preserves full history and does not invent workflow data", async () => {
  const payload = { status: "conversation", reply: "Inference là dùng model để trả lời.",
    requirement, missing_fields: ["model_size_b", "usage", "budget_vnd"] };
  await withResponse(payload, async (requests) => {
    assert.deepEqual(await submitConversation(conversation), payload);
    assert.deepEqual(requests, [{ url: "/api/backend/conversation/runs",
      body: { messages: conversation, workflow_run_id: null } }]);
  });
});

test("real conversation hook retains submitted run ID, sends it on follow-up and resets on NEW CHAT", async () => {
  reactHarness.cells = [];
  function HookTestHarness() {
    reactHarness.cursor = 0;
    return useLab3Conversation();
  }
  const runId = "d53e1e7c5e84442283982929270c7c8e";
  const submitted = { status: "submitted", reply: "Workflow đang kiểm tra.", requirement,
    run_id: runId, run_status: "pending" };
  const coordinator = { isRunActive: false, beginRunCreation: () => true,
    finishRunCreation: () => {}, attachRun: () => true };
  const event = { preventDefault() {} };
  let hook = HookTestHarness();
  hook.setDraft("14B inference 500 triệu");
  hook = HookTestHarness();
  await withResponse(submitted, async (requests) => {
    await hook.submit(event, coordinator);
    assert.equal(requests[0].body.workflow_run_id, null);
  });
  hook = HookTestHarness();
  assert.equal(hook.workflowRunId, runId);
  hook.setDraft("cảm ơn");
  hook = HookTestHarness();
  await withResponse({ status: "conversation", reply: "Rất vui được giúp bạn.", requirement,
    missing_fields: [] }, async (requests) => {
    await hook.submit(event, coordinator);
    assert.equal(requests[0].body.workflow_run_id, runId);
  });
  hook = HookTestHarness();
  assert.equal(hook.workflowRunId, runId);
  hook.startNewConversation();
  hook = HookTestHarness();
  assert.equal(hook.workflowRunId, null);
  assert.deepEqual(hook.messages, []);
});

test("frontend refuses an explanation beyond the shared message limit, without truncation", async () => {
  const original = globalThis.fetch;
  try {
    for (const length of [4000, 4001]) {
      globalThis.fetch = async () => Response.json({ run_id: "run", status: "completed",
        final_state: "complete", explanation: "x".repeat(length) });
      if (length === 4000) assert.equal((await fetchRunExplanation("run")).explanation.length, 4000);
      else await assert.rejects(fetchRunExplanation("run"), /format was invalid/);
    }
  } finally { globalThis.fetch = original; }
});
test("submitted response must include the actual advisor reply and run identity", async () => {
  const payload = { status: "submitted", reply: "Workflow sẽ kiểm tra dữ liệu thực tế.",
    requirement: { ...requirement, model_size_b: 14, usage: "inference", budget_vnd: 500000000 },
    run_id: "actual-run", run_status: "pending" };
  await withResponse(payload, async () => assert.deepEqual(await submitConversation(conversation), payload));
});
test("old, missing, blank and oversized advisor replies are rejected", async () => {
  for (const payload of [
    { status: "needs_information", question: "old", requirement, missing_fields: ["usage"] },
    { status: "submitted", requirement, run_id: "run", run_status: "pending" },
    { status: "conversation", reply: " ", requirement, missing_fields: ["usage"] },
    { status: "conversation", reply: "x".repeat(4001), requirement, missing_fields: ["usage"] },
  ]) await withResponse(payload, async () => assert.rejects(submitConversation(conversation), /format was invalid/));
});
