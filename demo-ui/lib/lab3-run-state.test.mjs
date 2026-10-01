import assert from "node:assert/strict";
import test from "node:test";

import { canBeginRun, isRunInProgress } from "./lab3-run-state.ts";

test("pending and running workflow runs remain active", () => {
  assert.equal(isRunInProgress("pending"), true);
  assert.equal(isRunInProgress("running"), true);
  assert.equal(canBeginRun("pending", false), false);
  assert.equal(canBeginRun("running", false), false);
});

test("terminal and idle statuses allow an explicitly requested new run", () => {
  assert.equal(isRunInProgress("completed"), false);
  assert.equal(isRunInProgress("failed"), false);
  assert.equal(isRunInProgress("idle"), false);
  assert.equal(canBeginRun("completed", false), true);
});

test("only one run creation may be reserved at a time", () => {
  assert.equal(canBeginRun("idle", true), false);
  assert.equal(canBeginRun("completed", true), false);
});
