import { fetchRun } from "@/lib/api";
import type { RunSnapshot } from "@/lib/contracts";

type TerminalSnapshotOptions = {
  maxAttempts?: number;
  delayMs?: number;
  sleep?: (delayMs: number) => Promise<void>;
};

const defaultSleep = (delayMs: number) => new Promise<void>((resolve) => setTimeout(resolve, delayMs));

export async function fetchTerminalSnapshot(
  runId: string,
  { maxAttempts = 5, delayMs = 50, sleep = defaultSleep }: TerminalSnapshotOptions = {},
): Promise<RunSnapshot> {
  let latest: RunSnapshot | null = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    latest = await fetchRun(runId);
    if (latest.status === "failed" || (latest.status === "completed" && latest.result !== null)) {
      return latest;
    }
    if (attempt < maxAttempts) await sleep(delayMs);
  }
  throw new Error(
    latest?.status === "completed"
      ? "Workflow đã completed nhưng snapshot chưa có kết quả cuối sau các lần thử giới hạn."
      : "Không thể đọc snapshot terminal của workflow sau các lần thử giới hạn.",
  );
}
