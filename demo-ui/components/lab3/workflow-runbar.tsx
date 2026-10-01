import type { Lab3RunStatus } from "@/lib/lab3-run-state";

export function WorkflowRunbar({
  runId,
  status,
  elapsedMs,
  creationBusy,
  topologyAvailable,
  onOpenStructuredRun,
  onExportTopology,
}: {
  runId: string | null;
  status: Lab3RunStatus;
  elapsedMs: number | null;
  creationBusy: boolean;
  topologyAvailable: boolean;
  onOpenStructuredRun: () => void;
  onExportTopology: () => void;
}) {
  const runActive = status === "pending" || status === "running";
  return <section className="lab3-runbar" aria-label="Active workflow run">
    <div className="lab3-run-info"><span>RUN:</span><strong className="mono">{runId ?? "NO RUN"}</strong><span className={`lab3-status ${status}`}>{status === "idle" ? "READY" : status.toUpperCase()}</span>{elapsedMs !== null ? <span className="mono">{elapsedMs} ms</span> : null}</div>
    <div className="lab3-actions">
      <button className="stitch-button" type="button" onClick={onOpenStructuredRun} disabled={creationBusy || runActive}>STRUCTURED RUN</button>
      <button className="stitch-button primary" type="button" onClick={onExportTopology} disabled={!topologyAvailable}>EXPORT DAG</button>
    </div>
  </section>;
}
