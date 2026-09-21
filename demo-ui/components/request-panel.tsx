import type { FormEvent } from "react";
import type { RequirementForm, RunStatus } from "@/lib/contracts";

type RequestPanelProps = {
  value: RequirementForm;
  onChange: (next: RequirementForm) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  disabled: boolean;
  runId: string | null;
  status: RunStatus | "idle";
};

export function RequestPanel({ value, onChange, onSubmit, disabled, runId, status }: RequestPanelProps) {
  const setNumber = (field: keyof RequirementForm, raw: string) => onChange({ ...value, [field]: Number(raw) });
  const chipClass = `status-chip ${status === "running" ? "live" : ""} ${status === "failed" ? "fail" : ""}`;
  return (
    <section className="panel" aria-labelledby="request-title">
      <div className="panel-header">
        <div><h2 className="panel-title" id="request-title">Request</h2><p className="panel-subtitle">Gửi workload vào workflow deterministic.</p></div>
        <span className={chipClass}>{status === "idle" ? "ready" : status}</span>
      </div>
      <div className="panel-body">
        <form className="request-form" onSubmit={onSubmit}>
          <div className="field"><label htmlFor="model-size">Model size (B)</label><input id="model-size" type="number" min="1" step="0.1" value={value.model_size_b} onChange={(event) => setNumber("model_size_b", event.target.value)} required /></div>
          <div className="form-grid">
            <div className="field"><label htmlFor="usage">Usage</label><select id="usage" value={value.usage} onChange={(event) => onChange({ ...value, usage: event.target.value as RequirementForm["usage"] })}><option value="inference">Inference</option><option value="fine_tune">Fine-tune</option></select></div>
            <div className="field"><label htmlFor="concurrent-users">Concurrent users</label><input id="concurrent-users" type="number" min="1" value={value.concurrent_users} onChange={(event) => setNumber("concurrent_users", event.target.value)} required /></div>
          </div>
          <div className="field"><label htmlFor="budget">Budget (VND)</label><input id="budget" type="number" min="1000000" step="1000000" value={value.budget_vnd} onChange={(event) => setNumber("budget_vnd", event.target.value)} required /></div>
          <div className="field"><label htmlFor="storage">Storage requirement (GB)</label><input id="storage" type="number" min="1" value={value.storage_requirement_gb} onChange={(event) => setNumber("storage_requirement_gb", event.target.value)} required /></div>
          <button className="primary-button" type="submit" disabled={disabled}>{disabled ? "Workflow đang chạy…" : "Start workflow"}</button>
        </form>
        {runId ? <div className="run-meta" aria-live="polite"><div className="meta-row"><span>run id</span><strong>{runId.slice(0, 12)}…</strong></div><div className="meta-row"><span>transport</span><strong>SSE / replay</strong></div></div> : null}
      </div>
    </section>
  );
}
