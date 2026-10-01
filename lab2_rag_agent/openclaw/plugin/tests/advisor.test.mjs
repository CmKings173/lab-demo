import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { test } from "node:test";

test("pinned OpenClaw 2026.9.6 accepts workspace bootstrap and exactly six tools", async () => {
  const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url)));
  assert.equal(packageJson.devDependencies.openclaw, "2026.9.6");
  const config = JSON.parse(await readFile(new URL("../examples/lab2-agent.json", import.meta.url)));
  const agent = config.agents.entries.lab2;
  // Validate against the installed, pinned runtime schema, not an invented prompt field.
  const directory = new URL("../node_modules/openclaw/dist/", import.meta.url);
  const schemaFile = (await readdir(directory)).find((name) => /^zod-schema\.agent-runtime-.*\.mjs$/.test(name));
  assert.ok(schemaFile);
  const { n: AgentEntrySchema } = await import(new URL(schemaFile, directory).href);
  AgentEntrySchema.parse({ id: "lab2", ...agent });
  assert.equal(agent.model, "vllm/Qwen/Qwen3-14B");
  assert.equal(agent.contextInjection, "always");
  assert.deepEqual(agent.skills, []);
  const manifest = JSON.parse(await readFile(new URL("../openclaw.plugin.json", import.meta.url)));
  assert.deepEqual(agent.tools.allow, manifest.contracts.tools);
  assert.equal(agent.tools.allow.length, 6);
  assert.doesNotMatch(JSON.stringify(agent.tools), /ingest|exec|browser|filesystem|mcp/i);
  assert.equal(agent.systemPrompt, undefined);
  const prompt = await readFile(new URL("../examples/lab2-workspace/SOUL.md", import.meta.url), "utf8");
  for (const name of agent.tools.allow) assert.ok(prompt.includes(name));
  assert.match(prompt, /configuration_repository_not_configured/);
  assert.match(prompt, /untrusted/);
  assert.match(prompt, /ONLY the six/);
  assert.match(prompt, /Vietnamese/);
});
