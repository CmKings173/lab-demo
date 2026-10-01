import assert from "node:assert/strict";
import test from "node:test";

import { caseMetricPresentation, formatPercentagePointDelta } from "./lab1-metrics.ts";

test("accuracy metrics map true to pass and false to miss", () => {
  assert.deepEqual(caseMetricPresentation("tool_name_accuracy", true), { label: "PASS", tone: "pass" });
  assert.deepEqual(caseMetricPresentation("tool_name_accuracy", false), { label: "MISS", tone: "miss" });
});

test("error-rate flags distinguish an existing issue from a clear result", () => {
  assert.deepEqual(caseMetricPresentation("missing_tool_call_rate", true), { label: "ISSUE", tone: "miss" });
  assert.deepEqual(caseMetricPresentation("unexpected_tool_call_rate", false), { label: "CLEAR", tone: "pass" });
});

test("missing case metric values remain not applicable", () => {
  assert.deepEqual(caseMetricPresentation("abstention_accuracy", null), { label: "N/A", tone: "muted" });
});

test("metric differences are shown in percentage points", () => {
  assert.equal(formatPercentagePointDelta(0.0167), "+1.67 pp");
  assert.equal(formatPercentagePointDelta(-0.0833), "-8.33 pp");
});
