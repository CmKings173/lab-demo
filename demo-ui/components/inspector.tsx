import type { WorkflowEvent } from "@/lib/contracts";

export function Inspector({ event }: { event: WorkflowEvent | null }) {
  return <section className="panel inspector-panel" aria-labelledby="inspector-title">
    <div className="panel-header"><div><h2 className="panel-title" id="inspector-title">Inspector</h2><p className="panel-subtitle">Observable data, không có hidden reasoning.</p></div></div>
    <div className="panel-body inspector-body">
      {!event ? <div className="empty-state">Chọn một node hoặc event để xem chi tiết.</div> : <>
        <p className="event-kicker">Event #{event.sequence}</p><h3 className="event-title">{event.type}</h3>
        <dl className="detail-list">
          <div className="detail-item"><dt>State</dt><dd>{event.state ?? "—"}</dd></div>
          <div className="detail-item"><dt>Timestamp</dt><dd>{new Date(event.timestamp).toLocaleTimeString()}</dd></div>
          <div className="detail-item"><dt>Duration</dt><dd>{event.duration_ms == null ? "—" : `${event.duration_ms} ms`}</dd></div>
          <div className="detail-item"><dt>Event id</dt><dd>{event.event_id}</dd></div>
        </dl>
        <pre className="payload" aria-label="Event payload">{JSON.stringify(event.payload, null, 2)}</pre>
      </>}
    </div>
  </section>;
}
