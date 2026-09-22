import type { WorkflowEvent } from "@/lib/contracts";
import { labelForStatus } from "@/lib/fold-events";
import type { NodeStatus } from "@/lib/contracts";

type Detail = { label: string; value: string };

function valueOf(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value) && value.every((item) => typeof item === "string" || typeof item === "number")) {
    return value.length ? value.join(", ") : "Không có";
  }
  return null;
}

function details(event: WorkflowEvent): { input: Detail[]; output: Detail[]; evidence: Detail[]; validation: Detail[]; error: string | null } {
  const payload = event.payload;
  const pick = (keys: [string, string][]): Detail[] => keys.flatMap(([key, label]) => {
    const value = valueOf(payload[key]);
    return value === null ? [] : [{ label, value }];
  });
  switch (event.type) {
    case "tool.started":
    case "tool.completed":
    case "tool.failed":
      return { input: pick([["tool", "Service"]]), output: [], evidence: [], validation: [], error: valueOf(payload.error) };
    case "validation.result":
      return { input: pick([["configuration_id", "Configuration"]]), output: [], evidence: [], validation: pick([["status", "Kết quả"], ["failure_fields", "Trường lỗi"], ["unknown_fields", "Chưa biết"]]), error: null };
    case "document.hit":
      return { input: [], output: [], evidence: pick([["product_id", "Product"], ["document_id", "Document"], ["source_url", "Nguồn"], ["page", "Trang"], ["retrieval_score", "Retrieval"], ["rerank_score", "Rerank"]]), validation: [], error: null };
    case "fact.resolved":
    case "fact.rejected":
    case "fact.conflict":
      return { input: [], output: pick([["field_name", "Technical field"], ["verified", "Verified"]]), evidence: pick([["product_id", "Product"], ["document_id", "Document"], ["source_url", "Nguồn"], ["page", "Trang"], ["confidence", "Confidence"]]), validation: [], error: null };
    case "proposal.generated":
      return { input: [], output: pick([["configuration_ids", "Configurations"], ["evidence_count", "Evidence"]]), evidence: [], validation: [], error: null };
    case "proposal.verified":
      return { input: [], output: [], evidence: [], validation: pick([["valid", "Hợp lệ"], ["error_count", "Số lỗi"]]), error: null };
    case "workflow.completed":
      return { input: [], output: pick([["final_state", "Final state"]]), evidence: [], validation: [], error: null };
    case "workflow.failed":
    case "state.failed":
      return { input: [], output: [], evidence: [], validation: [], error: valueOf(payload.error) };
    default:
      return { input: [], output: [], evidence: [], validation: [], error: null };
  }
}

function DetailSection({ title, rows }: { title: string; rows: Detail[] }) {
  if (!rows.length) return null;
  return <section className="inspector-section"><h4>{title}</h4><dl>{rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl></section>;
}

export function Inspector({ event, stateLabel, stateStatus, duration, startedAt }: {
  event: WorkflowEvent | null;
  stateLabel: string | null;
  stateStatus: NodeStatus | null;
  duration: number | null;
  startedAt: string | null;
}) {
  const info = event ? details(event) : null;
  const offset = event && startedAt ? Math.max(0, new Date(event.timestamp).getTime() - new Date(startedAt).getTime()) : null;
  return <aside className="panel inspector-panel" aria-labelledby="inspector-title">
    <div className="panel-header"><div><p className="panel-overline">03 / DETAILS</p><h2 id="inspector-title">Inspector</h2></div><span className="panel-meta">LIVE CONTEXT</span></div>
    {!event && !stateLabel ? <div className="empty-state inspector-empty">Chọn một node hoặc event trong trace để xem dữ liệu quan sát được.</div> : <div className="inspector-content">
      <div className="inspector-hero"><p className="inspector-kicker">{event ? `#${String(event.sequence).padStart(2, "0")} · ${event.type}` : "WORKFLOW STATE"}</p><h3>{stateLabel ?? event?.type}</h3>{stateStatus ? <span className={`status-pill ${stateStatus}`}>{labelForStatus(stateStatus)}</span> : null}</div>
      <dl className="inspector-metrics">
        <div><dt>Duration</dt><dd>{duration ?? event?.duration_ms ?? "—"}{duration !== null || event?.duration_ms != null ? " ms" : ""}</dd></div>
        <div><dt>Offset</dt><dd>{offset === null ? "—" : `+${offset} ms`}</dd></div>
        <div><dt>Timestamp</dt><dd>{event ? new Date(event.timestamp).toLocaleTimeString("vi-VN") : "—"}</dd></div>
      </dl>
      {info ? <>
        <DetailSection title="Input summary" rows={info.input} />
        <DetailSection title="Output summary" rows={info.output} />
        <DetailSection title="Validation" rows={info.validation} />
        <DetailSection title="Evidence" rows={info.evidence} />
        {info.error ? <section className="inspector-section error-section"><h4>Error</h4><p>{info.error}</p></section> : null}
      </> : null}
      {!info?.input.length && !info?.output.length && !info?.validation.length && !info?.evidence.length && !info?.error ? <p className="inspector-muted">Backend chưa phát thêm chi tiết cho mục này.</p> : null}
    </div>}
  </aside>;
}
