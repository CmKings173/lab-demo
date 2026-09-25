import type { WorkflowEvent } from "@/lib/contracts";

type TimelineProps = { events: WorkflowEvent[]; selectedSequence: number | null; onSelect: (event: WorkflowEvent) => void; };

function tone(event: WorkflowEvent): string {
  if (event.type.endsWith("failed")) return "failed";
  if (event.type.endsWith("started")) return "running";
  if (event.type === "validation.result" && event.payload.status === "unknown") return "unknown";
  if (event.type === "validation.result" && event.payload.status === "fail") return "failed";
  return "completed";
}

export function Timeline({ events, selectedSequence, onSelect }: TimelineProps) {
  const first = events.length ? new Date(events[0].timestamp).getTime() : 0;
  const end = Math.max(first + 1, ...events.map((event) => new Date(event.timestamp).getTime()));
  const span = end - first;
  return <section className="panel timeline-panel" id="trace" aria-labelledby="timeline-title">
    <div className="panel-header"><div><p className="panel-overline">04 / EVENT STREAM</p><h2 id="timeline-title">Trace timeline</h2></div><span className="panel-meta">{events.length} EVENTS</span></div>
    {events.length === 0 ? <div className="empty-state trace-empty">Event sẽ xuất hiện ở đây khi workflow bắt đầu chạy.</div> : <div className="trace-scroll">
      <div className="trace-head"><span>EVENT</span><span>STATE / SERVICE</span><span>TIME</span><span>EXECUTION</span></div>
      <div className="trace-rows">
        {events.map((event) => {
          const timestamp = new Date(event.timestamp).getTime();
          const offset = Math.max(0, timestamp - first);
          const duration = event.duration_ms ?? 0;
          const left = Math.max(0, ((offset - duration) / span) * 100);
          const width = Math.max(0.8, (duration / span) * 100);
          const status = tone(event);
          return <button
            className={`trace-row ${status} ${selectedSequence === event.sequence ? "selected" : ""}`}
            key={event.event_id}
            type="button"
            onClick={() => onSelect(event)}
            aria-pressed={selectedSequence === event.sequence}
            aria-label={`Event ${event.sequence}: ${event.type}, ${event.state ?? "system"}, +${offset} mili giây`}
          >
            <span className="trace-event"><b className="mono">#{String(event.sequence).padStart(2, "0")}</b><span className="trace-dot" aria-hidden="true" /><strong>{event.type}</strong></span>
            <span className="trace-state">{event.state ?? (typeof event.payload.tool === "string" ? event.payload.tool : "system")}</span>
            <span className="trace-time mono">+{offset} ms{event.duration_ms === null ? "" : ` · ${event.duration_ms} ms`}</span>
            <span className="trace-lane" aria-hidden="true"><i style={{ left: `${Math.min(left, 99)}%`, width: `${Math.min(width, 100 - Math.min(left, 99))}%` }} /></span>
          </button>;
        })}
      </div>
    </div>}
  </section>;
}
