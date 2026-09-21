"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Inspector } from "@/components/inspector";
import { RequestPanel } from "@/components/request-panel";
import { Timeline } from "@/components/timeline";
import { WorkflowGraph } from "@/components/workflow-graph";
import { createRun, fetchTopology, subscribeToRun } from "@/lib/api";
import type { RequirementForm, RunSnapshot, RunStatus, WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { fetchTerminalSnapshot } from "@/lib/terminal-snapshot";

const initialRequirement: RequirementForm = {
  model_size_b: 20,
  usage: "inference",
  concurrent_users: 2,
  budget_vnd: 300_000_000,
  storage_requirement_gb: 1000,
};

export function DemoShell() {
  const [topology, setTopology] = useState<WorkflowTopology | null>(null);
  const [requirement, setRequirement] = useState(initialRequirement);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<WorkflowEvent | null>(null);
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<RunStatus | "idle">("idle");
  const [error, setError] = useState<string | null>(null);
  const [connectionNote, setConnectionNote] = useState<string | null>(null);

  useEffect(() => {
    fetchTopology().then(setTopology).catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!runId) return undefined;
    const close = subscribeToRun(
      runId,
      0,
      (event) => {
        setEvents((current) => current.some((item) => item.sequence === event.sequence) ? current : [...current, event]);
        setSelectedEvent(event);
        if (event.type === "workflow.started") setStatus("running");
        if (event.type === "workflow.completed") setStatus("completed");
        if (event.type === "workflow.failed") setStatus("failed");
      },
      setConnectionNote,
      () => setConnectionNote(null),
      () => {
        fetchTerminalSnapshot(runId)
          .then(setSnapshot)
          .catch((reason: Error) => setError(reason.message));
      },
    );
    return close;
  }, [runId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null); setConnectionNote(null); setSnapshot(null); setEvents([]); setSelectedEvent(null); setStatus("pending");
    try {
      const created = await createRun(requirement);
      setRunId(created.run_id); setStatus(created.status);
    } catch (reason) {
      setStatus("idle"); setError(reason instanceof Error ? reason.message : "Không thể tạo run.");
    }
  };

  const finalState = snapshot?.final_state ?? events.findLast((event) => event.type === "workflow.completed" || event.type === "workflow.failed")?.state;
  const isBusy = status === "pending" || status === "running";
  const selectedState = selectedEvent?.state ?? null;
  const eventForInspector = selectedState ? events.findLast((event) => event.state === selectedState) ?? selectedEvent : selectedEvent;

  return <main className="app-frame">
    <header className="app-header">
      <div className="brand-lockup"><div className="brand-mark" aria-hidden="true">LD</div><div><p className="eyebrow">Lab 3 / realtime observability</p><h1 className="page-title">Workflow trace</h1></div></div>
      <p className="header-note">Một cửa sổ quan sát cho request, state machine, evidence và proposal — tất cả do backend phát event.</p>
    </header>
    {error ? <p className="alert" role="alert">{error}</p> : null}
    {connectionNote ? <p className="alert" role="status">{connectionNote}</p> : null}
    <div className="layout-grid">
      <RequestPanel value={requirement} onChange={setRequirement} onSubmit={handleSubmit} disabled={isBusy} runId={runId} status={status} />
      <section className="panel" aria-labelledby="graph-title">
        <div className="panel-header"><div><h2 className="panel-title" id="graph-title">Live workflow graph</h2><p className="panel-subtitle">Topology lấy trực tiếp từ server.</p></div><span className={`status-chip ${isBusy ? "live" : ""} ${status === "failed" ? "fail" : ""}`}>{finalState ?? "waiting"}</span></div>
        <WorkflowGraph topology={topology} events={events} selectedEvent={selectedEvent} onSelectState={(state) => setSelectedEvent(events.findLast((event) => event.state === state) ?? null)} />
      </section>
      <Inspector event={eventForInspector} />
      <Timeline events={events} selectedSequence={selectedEvent?.sequence ?? null} onSelect={setSelectedEvent} />
    </div>
    {snapshot?.result?.proposal ? <p className="panel-subtitle proposal-note">Proposal: {snapshot.result.proposal.option_count} option(s) · {snapshot.result.proposal.evidence_count} evidence hit(s).</p> : null}
  </main>;
}
