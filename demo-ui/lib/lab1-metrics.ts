import type { Lab1CaseMetricKey } from "./lab1-contracts";

export type CaseMetricPresentation = {
  label: "PASS" | "MISS" | "ISSUE" | "CLEAR" | "N/A";
  tone: "pass" | "miss" | "muted";
};

export function caseMetricPresentation(
  key: Lab1CaseMetricKey,
  value: boolean | null,
): CaseMetricPresentation {
  if (value === null) return { label: "N/A", tone: "muted" };

  if (key === "missing_tool_call_rate" || key === "unexpected_tool_call_rate") {
    return value
      ? { label: "ISSUE", tone: "miss" }
      : { label: "CLEAR", tone: "pass" };
  }

  return value
    ? { label: "PASS", tone: "pass" }
    : { label: "MISS", tone: "miss" };
}

const percentagePointFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});

export function formatPercentagePointDelta(delta: number): string {
  return `${percentagePointFormat.format(delta * 100)} pp`;
}
