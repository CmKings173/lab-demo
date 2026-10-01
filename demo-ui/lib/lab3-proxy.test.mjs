import assert from "node:assert/strict";
import { test } from "node:test";

// The same handler called by the real Next route; the separate integration gate
// also exercises Next's router and a real localhost FastAPI conversation endpoint.
const { proxyLab3Conversation, LAB3_CONVERSATION_TIMEOUT_MS } =
  await import("./server/lab3-conversation.ts");
const request = () => new Request("http://localhost:3000/api/backend/conversation/runs", {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ messages: [{ role: "user", content: "hello" }] }),
});

test("route has a finite 135s deadline, not the old global rewrite deadline", () => {
  assert.equal(LAB3_CONVERSATION_TIMEOUT_MS, 135_000);
});

test("genuine timeout returns a sanitized 504, including during response body reading", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(new ReadableStream({ start() {} }), {
      headers: { "content-type": "application/json" },
    });
    const result = await proxyLab3Conversation(request(), { timeoutMs: 25 });
    assert.equal(result.status, 504);
    assert.equal((await result.json()).error.code, "LAB3_CONVERSATION_TIMEOUT");
  } finally { globalThis.fetch = original; }
});

test("upstream errors, redirects, oversized bodies and invalid config are not exposed", async () => {
  const original = globalThis.fetch;
  try {
    for (const response of [
      new Response("provider-secret-marker", { status: 500 }),
      new Response("provider-secret-marker", { status: 302 }),
      Response.json({ reply: "provider-secret-marker" + "x".repeat(129 * 1024) }),
    ]) {
      globalThis.fetch = async () => response;
      const result = await proxyLab3Conversation(request());
      assert.equal(result.ok, false);
      assert.doesNotMatch(await result.text(), /provider-secret-marker/);
    }
    const result = await proxyLab3Conversation(request(), { backendUrl: "http://user:secret@localhost" });
    assert.equal(result.status, 503);
    assert.doesNotMatch(await result.text(), /secret@/);
  } finally { globalThis.fetch = original; }
});
