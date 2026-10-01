import assert from "node:assert/strict";
import { test } from "node:test";

const { proxyLab3Explanation, LAB3_EXPLANATION_TIMEOUT_MS } =
  await import("./server/lab3-explanation.ts");
const runId = "0123456789abcdef0123456789abcdef";
const request = () => new Request(`http://localhost:3000/api/backend/runs/${runId}/explanation`, {
  method: "POST",
});
const options = { backendUrl: "http://127.0.0.1:8000", timeoutMs: 75_000 };
const payload = (overrides = {}) => ({
  run_id: runId, status: "completed", final_state: "proposal_completed",
  explanation: "Kết quả từ run đã lưu.", ...overrides,
});
const secret = "provider-secret-marker https://internal.example/password";

test("explanation has its own finite 75-second budget", () => {
  assert.equal(LAB3_EXPLANATION_TIMEOUT_MS, 75_000);
});

test("only the fixed explanation path is sent, without browser credentials or body", async t => {
  let forwarded;
  t.mock.method(globalThis, "fetch", async (url, init) => {
    forwarded = { url: String(url), ...init };
    return Response.json(payload());
  });
  const browserRequest = new Request(`http://localhost/api/backend/runs/${runId}/explanation?path=/other`, {
    method: "POST", headers: { cookie: secret, authorization: secret }, body: secret,
  });
  const response = await proxyLab3Explanation(browserRequest, runId, {
    ...options, backendUrl: "https://internal.example/backend",
  });
  assert.equal(response.status, 200);
  assert.equal(forwarded.url, `https://internal.example/backend/runs/${runId}/explanation`);
  assert.equal(forwarded.method, "POST");
  assert.deepEqual(forwarded.headers, { Accept: "application/json" });
  assert.equal(forwarded.body, undefined);
  assert.equal(forwarded.credentials, "omit");
  assert.equal(forwarded.redirect, "error");
  assert.equal(forwarded.cache, "no-store");
});

test("terminal explanations preserve the 4000-character contract and discard extra fields", async t => {
  let upstream;
  t.mock.method(globalThis, "fetch", async () => Response.json(upstream));
  for (const status of ["completed", "failed"]) {
    upstream = payload({ status, final_state: null, explanation: "x".repeat(4000), provider_debug: secret });
    const response = await proxyLab3Explanation(request(), runId, options);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.deepEqual(await response.json(), payload({ status, final_state: null, explanation: "x".repeat(4000) }));
  }
});

test("a deadline during response body reading returns a sanitized HTTP 504", async t => {
  t.mock.method(globalThis, "fetch", async () => new Response(new ReadableStream({ start() {} }), {
    headers: { "content-type": "application/json" },
  }));
  const response = await proxyLab3Explanation(request(), runId, { ...options, timeoutMs: 25 });
  assert.equal(response.status, 504);
  assert.equal((await response.clone().json()).error.code, "LAB3_EXPLANATION_TIMEOUT");
  assert.doesNotMatch(await response.text(), /provider-secret|https?:\/\/|password/);
});

test("missing/not-ready and other upstream errors retain safe statuses without their bodies", async t => {
  let upstream;
  t.mock.method(globalThis, "fetch", async () => upstream);
  for (const status of [400, 404, 409, 422, 503, 504, 500, 302]) {
    upstream = new Response(secret, { status });
    const response = await proxyLab3Explanation(request(), runId, options);
    assert.equal(response.status, [500, 302].includes(status) ? 502 : status);
    assert.equal((await response.clone().json()).error.code, "LAB3_BACKEND_ERROR");
    assert.doesNotMatch(await response.text(), /provider-secret|https?:\/\/|password/);
  }
});

test("invalid or oversized responses fail without exposing backend content", async t => {
  let upstream;
  t.mock.method(globalThis, "fetch", async () => upstream);
  const invalid = [
    new Response(secret, { headers: { "content-type": "text/plain" } }),
    new Response(secret, { headers: { "content-type": "application/json" } }),
    Response.json([]),
    Response.json({ ...payload(), debug: secret + "x".repeat(33 * 1024) }),
    Response.json(payload({ explanation: secret + "x".repeat(4001) })),
    Response.json(payload({ explanation: "  " })),
    Response.json(payload({ run_id: "another-run" })),
    Response.json(payload({ status: "running" })),
    Response.json(payload({ status: ["completed"] })),
    Response.json(payload({ final_state: 123 })),
  ];
  for (upstream of invalid) {
    const response = await proxyLab3Explanation(request(), runId, options);
    assert.equal(response.status, 502);
    assert.doesNotMatch(await response.text(), /provider-secret|https?:\/\/|password/);
  }
});

test("transport failures are sanitized", async t => {
  t.mock.method(globalThis, "fetch", async () => { throw new Error(secret); });
  const response = await proxyLab3Explanation(request(), runId, options);
  assert.equal(response.status, 502);
  assert.equal((await response.clone().json()).error.code, "LAB3_BACKEND_UNAVAILABLE");
  assert.doesNotMatch(await response.text(), /provider-secret|https?:\/\/|password/);
});

test("invalid backend URLs and unbounded deadlines fail before contacting a backend", async t => {
  t.mock.method(globalThis, "fetch", async () => { assert.fail("backend must not be contacted"); });
  const invalid = [
    { backendUrl: "ftp://internal.example" },
    { backendUrl: "http://user:secret@internal.example" },
    { backendUrl: "http://internal.example?secret=value" },
    { backendUrl: "http://internal.example#secret" },
    ...[0, -1, Infinity, NaN, 75_001, 1.5].map(timeoutMs => ({ timeoutMs })),
  ];
  for (const override of invalid) {
    const response = await proxyLab3Explanation(request(), runId, { ...options, ...override });
    assert.equal(response.status, 503);
    assert.equal((await response.clone().json()).error.code, "LAB3_PROXY_NOT_CONFIGURED");
    assert.doesNotMatch(await response.text(), /internal\.example|secret=value|secret@/);
  }
});

test("run IDs cannot inject path segments, queries or fragments", async t => {
  t.mock.method(globalThis, "fetch", async () => { assert.fail("backend must not be contacted"); });
  for (const id of ["", "..", "../other", "abc/def", "abc?x", "abc#x", "%2f", "x".repeat(129)]) {
    const response = await proxyLab3Explanation(request(), id, options);
    assert.equal(response.status, 400);
    assert.equal((await response.json()).error.code, "INVALID_RUN_ID");
  }
});
