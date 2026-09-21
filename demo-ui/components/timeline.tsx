import type { WorkflowEvent } from "@/lib/contracts";

type TimelineProps = { events: WorkflowEvent[]; selectedSequence: number | null; onSelect: (event: WorkflowEvent) => void; };

export function Timeline({ events, selectedSequence, onSelect }: TimelineProps) {
  return <section className="panel timeline-panel" aria-labelledby="timeline-title">
    <div className="panel-header"><div><h2 className="panel-title" id="timeline-title">Timeline / events</h2><p className="panel-subtitle">Ordered event stream từ RunStore replay.</p></div><span className="status-chip">{events.length} events</span></div>
    {events.length === 0 ? <div className="empty-state">Chưa có event. Start workflow để xem trace realtime.</div> : <div className="timeline-list" role="list">
      {events.map((event) => <button className={`timeline-event ${selectedSequence === event.sequence ? "selected" : ""}`} key={event.event_id} type="button" onClick={() => onSelect(event)} aria-pressed={selectedSequence === event.sequence}>
        <span className="timeline-sequence">#{String(event.sequence).padStart(2, "0")}</span><span className="timeline-name">{event.type}</span><span className="timeline-state">{event.state ?? "system"}</span>
      </button>)}
    </div>}
  </section>;
}
