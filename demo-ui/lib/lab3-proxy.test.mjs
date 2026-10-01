import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";

registerHooks({ resolve(specifier, context, nextResolve) {
  if (specifier === "../lab3-errors") {
    return nextResolve(new URL("./lab3-errors.ts", import.meta.url).href, context);
  }
  return nextResolve(specifier, context);
} });

// The same handler called by the real Next route; the separate integration gate
// also exercises Next's router and a real localhost FastAPI conversation endpoint.
const { proxyLab3Conversation, LAB3_CONVERSATION_TIMEOUT_MS } =
  await import("./server/lab3-conversation.ts");
const request = () => new Request("http://localhost:3000/api/backend/conversation/runs", {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ messages: [{ role: "user", content: "hello" }] }),
});

test("known safe FastAPI error retains code, drops details and never echoes upstream text", async () => {
  const original = globalThis.fetch;
  try {
    for (const code of ["LLM_ADVISOR_RESPONSE_INVALID", "LLM_INVALID_RESPONSE", "LLM_UNAVAILABLE"]) {
      globalThis.fetch = async () => Response.json({ error: {
        code, message: "https://user:provider-secret-marker@provider/ traceback",
        details: { token: "provider-secret-marker" },
      } }, { status: 503 });
      const result = await proxyLab3Conversation(request());
      const payload = await result.json();
      assert.equal(result.status, 503);
      assert.equal(payload.error.code, code);
      assert.deepEqual(Object.keys(payload.error).sort(), ["code", "message"]);
      assert.doesNotMatch(JSON.stringify(payload), /provider-secret-marker|https:|traceback/);
    }
  } finally { globalThis.fetch = original; }
});

test("unknown or malformed error envelopes fail closed", async () => {
  const original = globalThis.fetch;
  const safe = { code: "LLM_UNAVAILABLE", message: "The language model service is unavailable." };
  try {
    for (const payload of [
      { error: { ...safe, code: "UNKNOWN_PROVIDER_ERROR" } },
      { error: { ...safe, code: "toString" } },
      { error: { ...safe, message: " " } },
      { error: { ...safe, message: 123 } },
      { error: { ...safe, message: "x".repeat(301) } },
      { error: { ...safe, secret: "provider-secret-marker" } },
      { error: safe, trace: "provider-secret-marker" },
      { error: [] },
      { error: { ...safe, details: "x".repeat(17 * 1024) } },
    ]) {
      globalThis.fetch = async () => Response.json(payload, { status: 422 });
      const result = await proxyLab3Conversation(request());
      assert.equal(result.status, 422);
      const body = await result.text();
      assert.equal(JSON.parse(body).error.code, "LAB3_BACKEND_ERROR");
      assert.doesNotMatch(body, /provider-secret-marker/);
    }
    for (const headers of [{ "content-type": "text/plain" }, { "content-type": "application/json-invalid" }]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ error: safe }), { status: 503, headers });
      const result = await proxyLab3Conversation(request());
      assert.equal((await result.json()).error.code, "LAB3_BACKEND_ERROR");
    }
    globalThis.fetch = async () => new Response("not-json-provider-secret-marker", {
      status: 503, headers: { "content-type": "application/json" },
    });
    const result = await proxyLab3Conversation(request());
    assert.equal((await result.json()).error.code, "LAB3_BACKEND_ERROR");
  } finally { globalThis.fetch = original; }
});

test("error body reading is also bounded by the request deadline", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(new ReadableStream({ start() {} }), {
      status: 503, headers: { "content-type": "application/json" },
    });
    const result = await proxyLab3Conversation(request(), { timeoutMs: 25 });
    assert.equal(result.status, 504);
    assert.equal((await result.json()).error.code, "LAB3_CONVERSATION_TIMEOUT");
  } finally { globalThis.fetch = original; }
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
