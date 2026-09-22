import type { FormEvent } from "react";
import type { RequirementForm, RunStatus, WorkflowEvent } from "@/lib/contracts";

export function ChatPanel({ submitted, submittedNote, draft, onDraftChange, onCompose, events, status, runId, finalState }: {
  submitted: RequirementForm | null;
  submittedNote: string;
  draft: string;
  onDraftChange: (text: string) => void;
  onCompose: () => void;
  events: WorkflowEvent[];
  status: RunStatus | "idle";
  runId: string | null;
  finalState: string | null;
}) {
  const recent = events.filter((event) => event.type === "state.started" || event.type === "state.failed" || event.type === "workflow.completed" || event.type === "workflow.failed").slice(-5);
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); onCompose(); };
  return <section className="panel chat-panel" id="chat" aria-labelledby="chat-title">
    <div className="panel-header"><div><p className="panel-overline">05 / INTERACTION</p><h2 id="chat-title">Chat with agent</h2></div><span className="panel-meta">WORKFLOW STATUS</span></div>
    <div className="chat-messages" aria-live="polite">
      {!submitted ? <div className="chat-empty"><span className="chat-empty-mark" aria-hidden="true">↗</span><h3>Bắt đầu một phiên quan sát</h3><p>Nhập ghi chú, thiết lập thông số và theo dõi các bước mà backend phát ra.</p></div> : <>
        <div className="message user-message"><span className="message-role">Bạn · request</span><p>{submittedNote.trim() || "Yêu cầu cấu hình hạ tầng AI"}</p><small>{submitted.model_size_b}B · {submitted.usage} · {submitted.concurrent_users} users · {submitted.storage_requirement_gb} GB · {submitted.budget_vnd.toLocaleString("vi-VN")} ₫</small></div>
        <div className="message status-message"><span className="message-role">Workflow · {runId ? runId.slice(0, 8) : "đang tạo"}</span><p>{status === "running" ? "Đang xử lý các bước của workflow" : status === "completed" ? `Workflow kết thúc: ${finalState?.replaceAll("_", " ") ?? "completed"}` : status === "failed" ? "Workflow gặp lỗi kỹ thuật" : "Đang khởi tạo run"}</p>
          {recent.length ? <ul>{recent.map((event) => <li key={event.event_id}><span aria-hidden="true">{event.type === "state.failed" || event.type === "workflow.failed" ? "!" : event.type.endsWith("completed") ? "✓" : "•"}</span> {event.type} {event.state ?? ""}</li>)}</ul> : <small>Chờ event từ server…</small>}
        </div>
      </>}
    </div>
    <form className="chat-compose" onSubmit={submit}><label htmlFor="chat-draft">Ghi chú cho run mới</label><div className="chat-compose-row"><textarea id="chat-draft" rows={2} value={draft} onChange={(event) => onDraftChange(event.target.value)} placeholder="Ví dụ: server chạy mô hình 20B cho 2 người dùng…" /><button type="submit" className="compose-send" aria-label="Mở bảng thiết lập run">↗</button></div><p>Chat hiện là giao diện tương tác. Ghi chú không được gửi tới agent; workflow dùng thông số trong bảng thiết lập.</p></form>
  </section>;
}
