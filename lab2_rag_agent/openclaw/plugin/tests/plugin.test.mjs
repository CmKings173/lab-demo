import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";
import { Check } from "typebox/value";

import plugin, { executeToolApi, TOOL_NAMES, toolApiConfigSchema } from "../dist/index.js";

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

test("search_products keeps a closed schema and rejects invented workload filters", () => {
  const metadata = getToolPluginMetadata(plugin);
  assert.deepEqual(metadata.tools.map((tool) => tool.name), [...TOOL_NAMES]);
  const schema = metadata.tools.find((tool) => tool.name === "search_products").parameters;
  assert.equal(schema.additionalProperties, false);
  assert.equal(schema.properties.filters.additionalProperties, false);
  assert.deepEqual(Object.keys(schema.properties), ["filters", "query", "limit"]);
  assert.deepEqual(Object.keys(schema.properties.filters.properties).sort(), [
    "availability", "gpu_vendor", "max_base_price_vnd", "max_listed_price_vnd",
    "min_gpu_count", "min_installed_ram_gb", "min_ram_gb",
    "min_total_gpu_vram_gb", "product_type",
  ]);
  const args = { filters: { product_type: "ai_workstation" }, query: null, limit: 3 };
  assert.equal(Check(schema, args), true);
  for (const key of ["usage", "vram_gb", "system_ram_gb", "model_size_b", "context_length"]) {
    assert.equal(Check(schema, { ...args, [key]: 1 }), false, `unexpected root key: ${key}`);
    assert.equal(
      Check(schema, { ...args, filters: { ...args.filters, [key]: 1 } }),
      false,
      `unexpected filter key: ${key}`,
    );
  }
});

test("model-facing descriptions separate category search from free text and sizing", () => {
  const tools = getToolPluginMetadata(plugin).tools;
  const search = tools.find((tool) => tool.name === "search_products");
  const filters = search.parameters.properties.filters;
  assert.match(filters.properties.product_type.description, /structured category filter/);
  assert.match(filters.properties.product_type.description, /AI workstation.*ai_workstation/);
  assert.match(search.parameters.properties.query.description, /ONLY.*product name.*SKU.*manufacturer/);
  assert.match(search.parameters.properties.query.description, /null.*category/);
  assert.match(search.parameters.properties.limit.description, /requested.*count/);
  assert.match(search.description, /tìm 3 workstation AI/);
  const example = search.description.match(/Example:\s*(\{[^\n]+\})/);
  assert.ok(example, "tool description must give explicit category-search arguments");
  assert.deepEqual(JSON.parse(example[1]), {
    filters: { product_type: "ai_workstation" }, query: null, limit: 3,
  });
  assert.match(filters.description, /Never send/);
  for (const key of ["usage", "vram_gb", "system_ram_gb", "model_size_b", "context_length"]) {
    assert.ok(filters.description.includes(key), `missing unsupported-key instruction: ${key}`);
  }
  assert.match(search.description, /workload\/model sizing.*estimate_ai_requirements/);
  const sizing = tools.find((tool) => tool.name === "estimate_ai_requirements");
  assert.match(sizing.description, /workload\/model sizing/);
  for (const key of ["min_total_gpu_vram_gb", "min_installed_ram_gb", "min_gpu_count"]) {
    assert.ok(sizing.description.includes(key), `missing supported sizing translation: ${key}`);
  }
});

test("workstation category arguments reach the Tool API without query or filter rewriting", async () => {
  const originalFetch = globalThis.fetch;
  const args = { filters: { product_type: "ai_workstation" }, query: null, limit: 3 };
  let forwarded;
  globalThis.fetch = async (url, init) => {
    assert.equal(String(url), "http://127.0.0.1:8090/tools/search_products");
    forwarded = JSON.parse(init.body);
    return new Response(JSON.stringify({ ok: true, data: [], error: null }), { status: 200 });
  };
  try {
    await executeToolApi("search_products", args, config);
    assert.deepEqual(forwarded, args);
  } finally {
    globalThis.fetch = originalFetch;
  }
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
