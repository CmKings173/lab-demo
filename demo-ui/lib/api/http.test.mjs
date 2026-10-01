import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks, stripTypeScriptTypes } from "node:module";
import { test } from "node:test";

const httpUrl = new URL("./http.ts", import.meta.url).href;
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "../lab3-errors") {
      return nextResolve(new URL("../lab3-errors.ts", import.meta.url).href, context);
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === httpUrl) return { format: "module", shortCircuit: true,
      source: stripTypeScriptTypes(readFileSync(new URL(url), "utf8"), { mode: "transform" }) };
    return nextLoad(url, context);
  },
});
const { ApiClientError, parseApiResponse } = await import("./http.ts");
const { proxyLab3Conversation } = await import("../server/lab3-conversation.ts");
const validPayload = value => value?.ok === true;

test("sanitized FastAPI code survives the actual Next proxy and API client boundary", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ error: {
    code: "LLM_ADVISOR_RESPONSE_INVALID", message: "https://user:secret-marker@provider/traceback",
    details: { token: "secret-marker" },
  } }, { status: 503 });
  try {
    const response = await proxyLab3Conversation(new Request("http://localhost/conversation/runs", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content: "hello" }] }),
    }), { backendUrl: "http://127.0.0.1:8000" });
    await assert.rejects(parseApiResponse(response, validPayload, "Request failed"), error => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.status, 503);
      assert.equal(error.code, "LLM_ADVISOR_RESPONSE_INVALID");
      assert.equal(error.message, "The model could not produce a valid advisor response.");
      assert.doesNotMatch(error.stack + JSON.stringify(error), /secret-marker|provider|traceback|details/);
      return true;
    });
  } finally { globalThis.fetch = original; }
});

test("generic message-only API errors remain supported with a null code", async () => {
  await assert.rejects(parseApiResponse(Response.json({ error: { message: "Not found." } },
    { status: 404 }), validPayload, "Request failed"), error => {
    assert.equal(error.message, "Not found.");
    assert.equal(error.code, null);
    return true;
  });
});

test("valid API validation errors preserve public fields and completely discard details", async () => {
  await assert.rejects(parseApiResponse(Response.json({ error: {
    code: "VALIDATION_ERROR", message: "Request validation failed.",
    details: { secret: "must-not-survive" },
  } }, { status: 422 }), validPayload, "Request failed"), error => {
    assert.ok(error instanceof ApiClientError);
    assert.equal(error.status, 422);
    assert.equal(error.code, "VALIDATION_ERROR");
    assert.equal(error.message, "Request validation failed.");
    assert.equal("details" in error, false);
    assert.equal("cause" in error, false);
    assert.deepEqual(Object.keys(error).sort(), ["code", "name", "status"]);
    assert.doesNotMatch(JSON.stringify(error) + error.stack +
      JSON.stringify(Object.getOwnPropertyDescriptors(error)), /details|secret|must-not-survive/);
    return true;
  });
});

test("optional details is ignored without even accessing its value", async () => {
  const publicError = { code: null, message: "Request validation failed." };
  Object.defineProperty(publicError, "details", {
    enumerable: true, get() { throw new Error("must-not-survive"); },
  });
  await assert.rejects(parseApiResponse({ ok: false, status: 422,
    json: async () => ({ error: publicError }),
  }, validPayload, "Request failed"), error => {
    assert.ok(error instanceof ApiClientError);
    assert.equal(error.code, null);
    assert.equal(error.status, 422);
    assert.equal(error.message, "Request validation failed.");
    assert.doesNotMatch(JSON.stringify(Object.getOwnPropertyDescriptors(error)),
      /details|must-not-survive/);
    return true;
  });
});

test("unknown error keys still fail closed even alongside legitimate details", async () => {
  await assert.rejects(parseApiResponse(Response.json({ error: {
    code: "VALIDATION_ERROR", message: "Request validation failed.",
    details: { secret: "must-not-survive" }, provider: "must-not-survive",
  } }, { status: 422 }), validPayload, "Request failed"), error => {
    assert.equal(error.status, 422);
    assert.equal(error.code, null);
    assert.equal(error.message, "Request failed (422)");
    assert.doesNotMatch(JSON.stringify(Object.getOwnPropertyDescriptors(error)),
      /details|provider|must-not-survive/);
    return true;
  });
});

test("unknown root keys still fail closed even with a valid public error", async () => {
  await assert.rejects(parseApiResponse(Response.json({ error: {
    code: "VALIDATION_ERROR", message: "Request validation failed.",
    details: { secret: "must-not-survive" },
  }, provider: "must-not-survive" }, { status: 422 }), validPayload, "Request failed"), error => {
    assert.equal(error.status, 422);
    assert.equal(error.code, null);
    assert.equal(error.message, "Request failed (422)");
    assert.doesNotMatch(JSON.stringify(Object.getOwnPropertyDescriptors(error)),
      /details|provider|must-not-survive/);
    return true;
  });
});

test("malformed and nested error data falls back without retaining private fields", async () => {
  for (const payload of [
    { error: { code: "https://secret-marker", message: "secret-marker" } },
    { error: { code: "X".repeat(65), message: "secret-marker" } },
    { error: { code: 42, message: "secret-marker" } },
    { error: { code: "invalid_code", message: "secret-marker", details: { token: "secret-marker" } } },
    { error: { message: "secret-marker".repeat(2000) } },
    { error: { message: { token: "secret-marker" } } },
    { error: { message: " " } },
    { error: { message: "secret-marker" }, provider: "secret-marker" },
  ]) {
    await assert.rejects(parseApiResponse(Response.json(payload, { status: 502 }),
      validPayload, "Request failed"), error => {
      assert.equal(error.message, "Request failed (502)");
      assert.equal(error.code, null);
      assert.doesNotMatch(error.stack + JSON.stringify(error), /secret-marker|details/);
      return true;
    });
  }
});
