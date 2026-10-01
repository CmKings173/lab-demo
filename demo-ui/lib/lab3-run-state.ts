import type { RunStatus } from "./contracts";

export type Lab3RunStatus = RunStatus | "idle";

export function isRunInProgress(status: Lab3RunStatus): boolean {
  return status === "pending" || status === "running";
}

export function canBeginRun(status: Lab3RunStatus, creationReserved: boolean): boolean {
  return !creationReserved && !isRunInProgress(status);
}
