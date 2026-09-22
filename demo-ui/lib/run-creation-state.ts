import type { CreateRunResponse, RequirementForm, RunStatus } from "./contracts";

export type RunCreationOutcome =
  | { kind: "success"; created: CreateRunResponse }
  | { kind: "failure"; error: string };

export type RunCreationTransition =
  | { kind: "stale" }
  | { kind: "failed"; error: string }
  | {
      kind: "created";
      submitted: RequirementForm;
      submittedNote: string;
      runId: string;
      status: RunStatus;
    };

export function resolveRunCreation(input: {
  generation: number;
  currentGeneration: number;
  requirement: RequirementForm;
  note: string;
  outcome: RunCreationOutcome;
}): RunCreationTransition {
  if (input.generation !== input.currentGeneration) return { kind: "stale" };
  if (input.outcome.kind === "failure") return { kind: "failed", error: input.outcome.error };

  return {
    kind: "created",
    submitted: input.requirement,
    submittedNote: input.note,
    runId: input.outcome.created.run_id,
    status: input.outcome.created.status,
  };
}
