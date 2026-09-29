import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { executeToolApi, TOOL_NAMES, toolApiConfigSchema } from "../dist/index.js";

const config = { toolApiBaseUrl: "http://127.0.0.1:8090/" };

test("plugin manifest exposes exactly the six allow-listed domain tools", async () => {
  const manifest = JSON.parse(await readFile(new URL("../openclaw.plugin.json", import.meta.url)));
  assert.deepEqual(manifest.contracts.tools, [...TOOL_NAMES]);
  assert.match(
    manifest.configSchema.properties.toolApiBaseUrl.description,
    /127\.0\.0\.1:8090/,
  );
});

test("OpenClaw config includes only the non-secret tool API URL", () => {
  const serialized = JSON.stringify(toolApiConfigSchema);
  assert.match(serialized, /toolApiBaseUrl/);
  assert.match(serialized, /127\.0\.0\.1:8090/);
  assert.doesNotMatch(serialized, /apiKey|secret|password|WEKNORA/i);
});

test("tool API forwarding preserves the structured ToolResult unchanged", async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, init) => {
    const request = { url: String(url), init };
    requests.push(request);
    const expected = { ok: true, data: { toolName: request.url.split("/").at(-1) }, error: null };
    return new Response(JSON.stringify(expected), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  try {
    for (const name of TOOL_NAMES) {
      const result = await executeToolApi(name, { marker: name }, config);
      assert.deepEqual(result, {
        ok: true,
        data: { toolName: name },
        error: null,
      });
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.deepEqual(
    requests.map((request) => request.url),
    TOOL_NAMES.map((name) => `http://127.0.0.1:8090/tools/${name}`),
  );
  assert.ok(requests.every((request) => request.init.method === "POST"));
  assert.deepEqual(JSON.parse(requests[1].init.body), { marker: "get_product" });
});

test("HTTP and network failures do not expose response/provider secrets", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("api-key=secret-value", { status: 502 });
  try {
    await assert.rejects(
      executeToolApi("search_products", {}, config),
      (error) => error.message === "lab2_tool_api_http_502" && !error.message.includes("secret"),
    );
    globalThis.fetch = async () => {
      throw new Error("WEKNORA_API_KEY=secret-value");
    };
    await assert.rejects(
      executeToolApi("search_products", {}, config),
      (error) => error.message === "lab2_tool_api_unavailable" && !error.message.includes("secret"),
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
