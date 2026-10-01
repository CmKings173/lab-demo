import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import { test } from "node:test";

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === "@/lib/lab2-contracts") {
      return nextResolve(new URL("./lab2-contracts.ts", import.meta.url).href, context);
    }
    return nextResolve(specifier, context);
  },
});
const { runLab2Chat } = await import("./server/openclaw-lab2.ts");

const origin = "http://192.0.2.55:3000";
const validId = "f4203d3a-ce32-43b9-a1a4-bbb417a07faa";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

test("Next internal request hostname does not reject the real same-origin LAN host", async () => {
  await withGateway(async () => gatewayReply(), async () => {
    const result = await runLab2Chat(new Request("http://localhost:3101/api/lab2/chat", {
      method: "POST", headers: { host: "192.0.2.55:3101", origin: "http://192.0.2.55:3101",
        "sec-fetch-site": "same-origin", "content-type": "application/json" },
      body: JSON.stringify({ message: "xin chào" }),
    }));
    assert.equal(result.ok, true);
    for (const headers of [
      { host: "192.0.2.55:3101", origin: "http://attacker.invalid:3101" },
      { host: "192.0.2.55:3101", origin: "http://attacker.invalid:3101",
        "x-forwarded-host": "attacker.invalid:3101" },
      { host: "attacker.invalid/path", origin: "http://attacker.invalid" },
    ]) {
      const blocked = await runLab2Chat(new Request("http://localhost:3101/api/lab2/chat", {
        method: "POST", headers: { ...headers, "content-type": "application/json" },
        body: JSON.stringify({ message: "hello" }),
      }));
      assert.equal(blocked.failure.status, 403);
    }
  });
});

function request(body, headers = {}) {
  return new Request(`${origin}/api/lab2/chat`, {
    method: "POST",
    headers: { origin, "content-type": "application/json", ...headers },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function gatewayReply(content = "Chào bạn. Bạn muốn tìm hiểu cấu hình nào?") {
  return Response.json({ model: "vllm/Qwen/Qwen3-14B", choices: [{ message: { content } }] });
}

async function withGateway(respond, run) {
  const previousFetch = globalThis.fetch;
  const previousUrl = process.env.LAB2_OPENCLAW_GATEWAY_URL;
  const previousToken = process.env.LAB2_OPENCLAW_GATEWAY_TOKEN;
  process.env.LAB2_OPENCLAW_GATEWAY_URL = "http://127.0.0.1:18789";
  process.env.LAB2_OPENCLAW_GATEWAY_TOKEN = "test-gateway-token";
  globalThis.fetch = respond;
  try {
    await run();
  } finally {
    globalThis.fetch = previousFetch;
    for (const [name, value] of Object.entries({
      LAB2_OPENCLAW_GATEWAY_URL: previousUrl,
      LAB2_OPENCLAW_GATEWAY_TOKEN: previousToken,
    })) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
}

for (const conversationId of [undefined, null]) {
  test(`first HTTP LAN turn with ${conversationId} ID receives a server UUID`, async () => {
    let sent;
    await withGateway(async (url, init) => {
      assert.equal(String(url), "http://127.0.0.1:18789/v1/chat/completions");
      assert.equal(init.headers["x-openclaw-agent-id"], "lab2");
      assert.equal(init.headers["x-openclaw-model"], "vllm/Qwen/Qwen3-14B");
      sent = JSON.parse(init.body);
      return gatewayReply();
    }, async () => {
      const result = await runLab2Chat(request({ message: "xin chào", conversationId }));
      assert.equal(result.ok, true);
      assert.match(result.value.conversationId, uuid);
      assert.equal(sent.user, `conv:${result.value.conversationId}`);
      assert.equal(sent.model, "openclaw/lab2");
      assert.deepEqual(sent.messages, [{ role: "user", content: "xin chào" }]);
    });
  });
}

test("a second turn reuses the authoritative returned UUID", async () => {
  const sessions = [];
  await withGateway(async (_url, init) => {
    sessions.push(JSON.parse(init.body).user);
    return gatewayReply();
  }, async () => {
    const first = await runLab2Chat(request({ message: "xin chào" }));
    assert.equal(first.ok, true);
    const second = await runLab2Chat(request({
      message: "inference là gì?", conversationId: first.value.conversationId,
    }));
    assert.equal(second.ok, true);
    assert.equal(second.value.conversationId, first.value.conversationId);
    assert.equal(sessions[0], sessions[1]);
  });
});

test("invalid supplied UUIDs, unknown fields, and blank messages fail before Gateway", async () => {
  await withGateway(async () => { assert.fail("invalid input reached Gateway"); }, async () => {
    for (const body of [
      { message: "hello", conversationId: "not-a-uuid" },
      { message: "hello", conversationId: 42 },
      { message: "hello", conversationId: "" },
      { message: " ", conversationId: validId },
      { message: "hello", conversationId: validId, tools: ["exec"] },
    ]) {
      const result = await runLab2Chat(request(body));
      assert.equal(result.ok, false);
      assert.equal(result.failure.status, 400);
    }
  });
});

test("cross-origin and cross-site requests remain blocked", async () => {
  await withGateway(async () => { assert.fail("cross-origin request reached Gateway"); }, async () => {
    for (const headers of [
      { origin: "https://attacker.example" },
      { origin: "" },
      { "sec-fetch-site": "cross-site" },
    ]) {
      const result = await runLab2Chat(request({ message: "hello", conversationId: validId }, headers));
      assert.equal(result.ok, false);
      assert.equal(result.failure.status, 403);
    }
  });
});

test("message, request byte limits, and JSON content type remain enforced", async () => {
  await withGateway(async () => { assert.fail("oversized request reached Gateway"); }, async () => {
    for (const input of [
      request({ message: "x".repeat(4001), conversationId: validId }),
      request(" ".repeat(17 * 1024)),
      request({ message: "hello", conversationId: validId }, { "content-length": "20000" }),
      request({ message: "hello", conversationId: validId }, { "content-type": "text/plain" }),
    ]) {
      const result = await runLab2Chat(input);
      assert.equal(result.ok, false);
      assert.equal(result.failure.status, 400);
    }
  });
});

test("Gateway errors never expose token or provider bodies", async () => {
  for (const respond of [
    async () => new Response("provider-password=test-gateway-token", { status: 502 }),
    async () => { throw new Error("provider-password=test-gateway-token"); },
  ]) {
    await withGateway(respond, async () => {
      const result = await runLab2Chat(request({ message: "hello", conversationId: validId }));
      assert.equal(result.ok, false);
      assert.equal(result.failure.status, 502);
      assert.doesNotMatch(JSON.stringify(result), /test-gateway-token|provider-password/);
    });
  }
});

test("oversized Gateway response fails safely and bounded display truncation stays explicit", async () => {
  await withGateway(async () => gatewayReply("x".repeat(129 * 1024)), async () => {
    const result = await runLab2Chat(request({ message: "hello", conversationId: validId }));
    assert.equal(result.ok, false);
    assert.equal(result.failure.status, 502);
  });
  await withGateway(async () => gatewayReply("x".repeat(25_000)), async () => {
    const result = await runLab2Chat(request({ message: "hello", conversationId: validId }));
    assert.equal(result.ok, true);
    assert.equal(result.value.message.length, 24_000);
    assert.equal(result.value.truncated, true);
  });
});

test("Lab2 browser hook does not require secure-context crypto UUIDs", async () => {
  const hook = await readFile(new URL("../components/lab2/hooks/use-lab2-chat.ts", import.meta.url), "utf8");
  assert.doesNotMatch(hook, /crypto\.randomUUID/);
});
