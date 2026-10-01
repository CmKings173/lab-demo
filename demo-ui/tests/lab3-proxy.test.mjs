import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { readFile } from "node:fs/promises";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { setTimeout as sleep } from "node:timers/promises";

const uiRoot = fileURLToPath(new URL("../", import.meta.url));
const repoRoot = fileURLToPath(new URL("../../", import.meta.url));

async function availablePort(port = 0) {
  const server = createServer();
  server.listen(port, "127.0.0.1");
  await once(server, "listening");
  const selected = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return selected;
}

async function ready(url, child) {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`Fixture exited: ${child.testLog}`);
    try {
      if ((await fetch(url, { signal: AbortSignal.timeout(1000) })).ok) return;
    } catch { /* server not listening yet */ }
    await sleep(100);
  }
  throw new Error(`Fixture failed to start: ${child.testLog}`);
}

function start(command, args, cwd, env = {}) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env },
    stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  child.testLog = "";
  for (const stream of [child.stdout, child.stderr]) {
    stream.on("data", chunk => { child.testLog = (child.testLog + chunk).slice(-4000); });
  }
  return child;
}

async function stop(child) {
  if (child.exitCode !== null) return;
  const exited = once(child, "exit");
  child.kill(); // only this directly spawned fixture, no process-name/global cleanup
  await exited;
}

test("production Next → real FastAPI conversation/explanation regression (local fixtures only)",
  { timeout: 150_000 }, async t => {
    // Existing generic rewrites are built for localhost:8000; do not mutate them
    // or their SSE policy just to test the new selective filesystem route.
    const manifest = JSON.parse(await readFile(new URL("../.next/routes-manifest.json", import.meta.url), "utf8"));
    const rewrite = manifest.rewrites.afterFiles.find(route => route.source === "/api/backend/:path*");
    assert.equal(rewrite?.destination, "http://127.0.0.1:8000/:path*",
      "Build this fixture with BACKEND_URL=http://127.0.0.1:8000; never contact live providers.");
    assert.deepEqual(manifest.rewrites.afterFiles.map(({ source, destination }) => ({ source, destination })), [
      { source: "/api/backend/:path*", destination: "http://127.0.0.1:8000/:path*" },
    ], "The generic backend/SSE rewrite must retain its original mapping and order.");
    assert.deepEqual(manifest.rewrites.beforeFiles.map(({ source, destination }) => ({ source, destination })), [
      { source: "/api/backend/runs/:runId/explanation", destination: "/api/lab3/runs/:runId/explanation" },
    ], "Only explanation may bypass the generic rewrite through the shared local handler.");
    await availablePort(8000); // fails safely if an operator's server owns this port
    const children = [];
    try {
      const backend = start(process.env.LAB3_TEST_PYTHON ?? "python", ["-m", "uvicorn",
        "lab3_workflow.tests.proxy_fixture:app", "--host", "127.0.0.1", "--port", "8000"], repoRoot);
      children.push(backend);
      await ready("http://127.0.0.1:8000/health", backend);
      const ports = [await availablePort(), await availablePort()];
      for (const [index, port] of ports.entries()) {
        const next = start(process.execPath, ["node_modules/next/dist/bin/next", "start",
          "--hostname", "127.0.0.1", "--port", String(port)], uiRoot, {
          BACKEND_URL: "http://127.0.0.1:8000",
          LAB3_CONVERSATION_TIMEOUT_MS: index === 0 ? "135000" : "300",
          LAB3_EXPLANATION_TIMEOUT_MS: index === 0 ? "75000" : "300",
        });
        children.push(next);
        await ready(`http://127.0.0.1:${port}/api/backend/health`, next);
      }
      const post = (port, messages, workflowRunId = null) => fetch(
        `http://127.0.0.1:${port}/api/backend/conversation/runs`, {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ messages, workflow_run_id: workflowRunId }),
          signal: AbortSignal.timeout(45_000),
        });

      await t.test("32-second advisor response survives the former 30-second rewrite timeout", async () => {
        const startTime = Date.now();
        const response = await post(ports[0], [{ role: "user", content: "slow" }]);
        const elapsed = Date.now() - startTime;
        assert.equal(response.status, 200);
        assert.equal((await response.json()).status, "conversation");
        assert.ok(elapsed > 30_000 && elapsed < 45_000, `elapsed=${elapsed}ms`);
        t.diagnostic(`slow conversation HTTP 200 after ${elapsed}ms; deadline 135000ms`);
      });
      await t.test("a genuinely exceeded configured deadline returns safe 504", async () => {
        const response = await post(ports[1], [{ role: "user", content: "timeout" }]);
        assert.equal(response.status, 504);
        assert.equal((await response.json()).error.code, "LAB3_CONVERSATION_TIMEOUT");
      });
      await t.test("SSE still streams actual events and follow-ups do not create another run", async () => {
        const user = { role: "user", content: "14B inference 500 triệu" };
        const submitted = await post(ports[0], [user]);
        assert.equal(submitted.status, 202);
        const first = await submitted.json();
        const events = await fetch(`http://127.0.0.1:${ports[0]}/api/backend/runs/${first.run_id}/events`);
        assert.match(events.headers.get("content-type"), /text\/event-stream/);
        assert.match(await events.text(), /event: workflow.completed/);
        const history = [user, { role: "assistant", content: first.reply },
          { role: "user", content: "cảm ơn" }];
        for (let attempt = 0; attempt < 2; attempt++) {
          const follow = await post(ports[0], history, first.run_id);
          assert.equal(follow.status, 200);
          assert.equal((await follow.json()).status, "conversation");
        }
        assert.equal((await (await fetch("http://127.0.0.1:8000/test/run-count")).json()).run_count, 1);
      });
      const explain = (port, runId) => fetch(
        `http://127.0.0.1:${port}/api/backend/runs/${runId}/explanation`, {
          method: "POST", signal: AbortSignal.timeout(45_000),
        });
      const explanationMode = async mode => {
        const response = await fetch(`http://127.0.0.1:8000/test/explanation-mode/${mode}`, { method: "POST" });
        assert.equal(response.status, 200);
      };
      let explanationRunId;
      await t.test("32-second explanation survives the former generic rewrite timeout", async () => {
        const submitted = await post(ports[0], [{ role: "user", content: "14B inference 500 triệu" }]);
        assert.equal(submitted.status, 202);
        explanationRunId = (await submitted.json()).run_id;
        const events = await fetch(`http://127.0.0.1:${ports[0]}/api/backend/runs/${explanationRunId}/events`);
        assert.match(await events.text(), /event: workflow.completed/);
        await explanationMode("slow");
        const startTime = Date.now();
        const response = await explain(ports[0], explanationRunId);
        const elapsed = Date.now() - startTime;
        assert.equal(response.status, 200);
        const body = await response.json();
        assert.equal(body.run_id, explanationRunId);
        assert.equal(body.status, "completed");
        assert.match(body.explanation, /Fixture:/);
        assert.ok(body.explanation.length > 0 && body.explanation.length <= 4000);
        assert.ok(elapsed > 30_000 && elapsed < 45_000, `elapsed=${elapsed}ms`);
        t.diagnostic(`slow explanation HTTP 200 after ${elapsed}ms; deadline 75000ms`);
      });
      await t.test("explanation exceeds its injected deadline with a sanitized 504", async () => {
        await explanationMode("timeout");
        const response = await explain(ports[1], explanationRunId);
        assert.equal(response.status, 504);
        assert.equal((await response.clone().json()).error.code, "LAB3_EXPLANATION_TIMEOUT");
        assert.doesNotMatch(await response.text(), /provider-secret|https?:\/\/|password/);
      });
      await t.test("explanation preserves terminal success, missing 404 and not-ready 409", async () => {
        await explanationMode("normal");
        const success = await explain(ports[0], explanationRunId);
        assert.equal(success.status, 200);
        assert.ok((await success.json()).explanation.length <= 4000);
        const pendingResponse = await fetch("http://127.0.0.1:8000/test/pending-run", { method: "POST" });
        assert.equal(pendingResponse.status, 200);
        const pending = (await pendingResponse.json()).run_id;
        for (const [runId, status] of [["0".repeat(32), 404], [pending, 409]]) {
          const response = await explain(ports[0], runId);
          assert.equal(response.status, status);
          assert.equal((await response.clone().json()).error.code, "LAB3_BACKEND_ERROR");
          assert.doesNotMatch(await response.text(), /provider-secret|https?:\/\/|password/);
        }
      });
    } finally {
      await Promise.all(children.map(stop));
    }
  });
