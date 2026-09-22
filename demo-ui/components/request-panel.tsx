import { useEffect, useRef, type FormEvent } from "react";
import type { RequirementForm } from "@/lib/contracts";

type RequestPanelProps = {
  open: boolean;
  value: RequirementForm;
  note: string;
  error: string | null;
  onChange: (next: RequirementForm) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClose: () => void;
  disabled: boolean;
};

export function RequestPanel({ open, value, note, error, onChange, onSubmit, onClose, disabled }: RequestPanelProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  const setNumber = (field: keyof RequirementForm, raw: string) => onChange({ ...value, [field]: Number(raw) });

  return <dialog ref={dialogRef} className="run-dialog" onClose={onClose} aria-labelledby="request-title" aria-describedby="request-help">
    <div className="dialog-header"><div><p className="panel-overline">NEW EXECUTION</p><h2 id="request-title">Thiết lập workflow</h2></div><button className="icon-button" type="button" onClick={onClose} aria-label="Đóng bảng tạo run">×</button></div>
    <p id="request-help" className="dialog-intro">Backend chạy theo năm thông số này. Ghi chú chat chỉ hiển thị trong giao diện.</p>
    {error ? <p className="alert" role="alert">{error}</p> : null}
    {note.trim() ? <p className="request-note"><span>Ghi chú</span>{note.trim()}</p> : null}
    <form className="request-form" onSubmit={onSubmit}>
      <div className="field"><label htmlFor="model-size">Model size · B</label><input id="model-size" type="number" min="1" step="0.1" value={value.model_size_b} onChange={(event) => setNumber("model_size_b", event.target.value)} required /></div>
      <div className="form-grid">
        <div className="field"><label htmlFor="usage">Usage</label><select id="usage" value={value.usage} onChange={(event) => onChange({ ...value, usage: event.target.value as RequirementForm["usage"] })}><option value="inference">Inference</option><option value="fine_tune">Fine-tune</option></select></div>
        <div className="field"><label htmlFor="concurrent-users">Concurrent users</label><input id="concurrent-users" type="number" min="1" value={value.concurrent_users} onChange={(event) => setNumber("concurrent_users", event.target.value)} required /></div>
      </div>
      <div className="field"><label htmlFor="budget">Budget · VND</label><input id="budget" type="number" min="1000000" step="1000000" value={value.budget_vnd} onChange={(event) => setNumber("budget_vnd", event.target.value)} required /></div>
      <div className="field"><label htmlFor="storage">Storage requirement · GB</label><input id="storage" type="number" min="1" value={value.storage_requirement_gb} onChange={(event) => setNumber("storage_requirement_gb", event.target.value)} required /></div>
      <div className="dialog-actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit" disabled={disabled}>{disabled ? "Đang tạo run…" : "Start workflow →"}</button></div>
    </form>
  </dialog>;
}
