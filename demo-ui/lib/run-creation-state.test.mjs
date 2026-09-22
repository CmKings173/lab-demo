import test from "node:test";
import assert from "node:assert/strict";

import { resolveRunCreation } from "./run-creation-state.ts";

const requirement = {
  model_size_b: 20,
  usage: "inference",
  concurrent_users: 2,
  budget_vnd: 300_000_000,
  storage_requirement_gb: 1000,
};

test("successful create commits the request only after the backend confirms it", () => {
  const transition = resolveRunCreation({
    generation: 1,
    currentGeneration: 1,
    requirement,
    note: "Qwen 20B",
    outcome: { kind: "success", created: { run_id: "run-1", status: "pending" } },
  });

  assert.deepEqual(transition, {
    kind: "created",
    submitted: requirement,
    submittedNote: "Qwen 20B",
    runId: "run-1",
    status: "pending",
  });
});

test("failed create does not commit a phantom request to chat", () => {
  const transition = resolveRunCreation({
    generation: 1,
    currentGeneration: 1,
    requirement,
    note: "Qwen 20B",
    outcome: { kind: "failure", error: "Backend unavailable" },
  });

  assert.deepEqual(transition, { kind: "failed", error: "Backend unavailable" });
  assert.equal("submitted" in transition, false);
  assert.equal("runId" in transition, false);
});

test("a late response from an older generation cannot commit run state", () => {
  const transition = resolveRunCreation({
    generation: 1,
    currentGeneration: 2,
    requirement,
    note: "stale request",
    outcome: { kind: "success", created: { run_id: "old-run", status: "running" } },
  });

  assert.deepEqual(transition, { kind: "stale" });
});
