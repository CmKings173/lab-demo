"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { ChatPanel } from "@/components/chat-panel";
import { Inspector } from "@/components/inspector";
import { NavRail } from "@/components/nav-rail";
import { ProposalPanel } from "@/components/proposal-panel";
import { RequestPanel } from "@/components/request-panel";
import { Timeline } from "@/components/timeline";
import { WorkflowGraph } from "@/components/workflow-graph";
import { createRun, fetchTopology, subscribeToRun } from "@/lib/api";
import type { RequirementForm, RunSnapshot, RunStatus, WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { nodeStatusFor } from "@/lib/fold-events";
import { stateDuration } from "@/lib/graph-runtime";
import { fetchTerminalSnapshot } from "@/lib/terminal-snapshot";

const initialRequirement: RequirementForm = {
  model_size_b: 20,
  usage: "inference",
  concurrent_users: 2,
  budget_vnd: 300_000_000,
  storage_requirement_gb: 1000,
};

type Selection = { kind: "event"; sequence: number } | { kind: "node"; state: string } | null;

export function DemoShell() {
  const [topology, setTopology] = useState<WorkflowTopology | null>(null);
  const [requirement, setRequirement] = useState(initialRequirement);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [selection, setSelection] = useState<Selection>(null);
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<RunStatus | "idle">("idle");
  const [error, setError] = useState<string | null>(null);
  const [connectionNote, setConnectionNote] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState<RequirementForm | null>(null);
  const [submittedNote, setSubmittedNote] = useState("");
  const activeRunId = useRef<string | null>(null);
  const requestGeneration = useRef(0);
  const pinnedSelection = useRef(false);

  useEffect(() => {
    fetchTopology().then(setTopology).catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!runId) return undefined;
    const isCurrentRun = () => activeRunId.current === runId;
    const close = subscribeToRun(
      runId,
      0,
      (event) => {
        if (!isCurrentRun()) return;
        setEvents((current) => current.some((item) => item.sequence === event.sequence) ? current : [...current, event]);
        if (!pinnedSelection.current) setSelection({ kind: "event", sequence: event.sequence });
        if (event.type === "workflow.started") setStatus("running");
        if (event.type === "workflow.completed") setStatus("completed");
        if (event.type === "workflow.failed") setStatus("failed");
      },
      (message) => { if (isCurrentRun()) setConnectionNote(message); },
      () => { if (isCurrentRun()) setConnectionNote(null); },
      () => {
        fetchTerminalSnapshot(runId)
          .then((nextSnapshot) => { if (isCurrentRun()) setSnapshot(nextSnapshot); })
          .catch((reason: Error) => { if (isCurrentRun()) setError(reason.message); });
      },
    );
    return close;
  }, [runId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const generation = ++requestGeneration.current;
    activeRunId.current = null;
    pinnedSelection.current = false;
    setCreating(true);
    setError(null); setConnectionNote(null); setSnapshot(null); setEvents([]); setSelection(null); setRunId(null); setStatus("pending");
    setSubmitted({ ...requirement }); setSubmittedNote(draft);
    try {
      const created = await createRun(requirement);
      if (generation !== requestGeneration.current) return;
      activeRunId.current = created.run_id;
      setRunId(created.run_id); setStatus(created.status); setDrawerOpen(false); setDraft("");
    } catch (reason) {
      if (generation !== requestGeneration.current) return;
      setStatus("idle"); setError(reason instanceof Error ? reason.message : "Không thể tạo run.");
    } finally {
      if (generation === requestGeneration.current) setCreating(false);
    }
  };

  const terminalEvent = events.findLast((event) => event.type === "workflow.completed" || event.type === "workflow.failed");
  const finalState = snapshot?.final_state ?? terminalEvent?.state ?? null;
  const selectedEvent = selection?.kind === "event"
    ? events.find((event) => event.sequence === selection.sequence) ?? null
    : selection?.kind === "node"
      ? events.findLast((event) => event.state === selection.state) ?? null
      : null;
  const isViewingHistory = selection?.kind === "event" && selection.sequence < (events.at(-1)?.sequence ?? 0);
  const graphEvents = isViewingHistory ? events.filter((event) => event.sequence <= selection.sequence) : events;
  const selectedState = selection?.kind === "node" ? selection.state : selectedEvent?.state ?? null;
  const selectedNode = topology?.nodes.find((node) => node.id === selectedState) ?? null;
  const selectedStatus = selectedNode ? nodeStatusFor(selectedNode, graphEvents) : null;
  const selectedDuration = selectedState ? stateDuration(selectedState, graphEvents) : null;

  return <main className="dashboard" id="live">
    <NavRail />
    <header className="run-header" id="runs">
      <div className="run-heading"><p className="eyebrow">LAB 3 <span>/</span> REALTIME OBSERVABILITY</p><h1>Workflow <span>console</span></h1><p>Theo dõi luồng xử lý từ request tới proposal, trực tiếp từ sự kiện backend.</p></div>
      <div className="run-actions"><div className="run-ident"><span>ACTIVE RUN</span><strong className="mono">{runId ? runId.slice(0, 12) : "NO RUN"}</strong></div><span className={`run-indicator ${status}`}><i aria-hidden="true" />{status === "idle" ? "READY" : status.toUpperCase()}</span><button className="primary-button new-run-button" type="button" onClick={() => setDrawerOpen(true)}>+ New run</button></div>
    </header>
    {error ? <p className="alert dashboard-alert" role="alert">{error}</p> : null}
    {connectionNote ? <p className="connection-note dashboard-alert" role="status">{connectionNote}</p> : null}
    <section className="panel graph-panel" id="graph" aria-labelledby="graph-title">
      <div className="panel-header"><div><p className="panel-overline">01 / LIVE EXECUTION</p><h2 id="graph-title">Workflow graph</h2></div><div className="graph-heading-meta"><span className="live-dot" aria-hidden="true" /><span>{isViewingHistory ? `TRACE #${selection.sequence}` : finalState ? finalState.replaceAll("_", " ") : status === "running" ? "ĐANG CHẠY" : "CHỜ RUN"}</span>{isViewingHistory ? <button type="button" className="latest-button" onClick={() => { pinnedSelection.current = false; const latest = events.at(-1); setSelection(latest ? { kind: "event", sequence: latest.sequence } : null); }}>Latest</button> : null}</div></div>
      <div className="graph-key"><span><i className="key-dot pending" />Chờ</span><span><i className="key-dot running" />Đang chạy</span><span><i className="key-dot completed" />Hoàn tất</span><span><i className="key-dot failed" />Lỗi</span><span className="graph-key-hint">Cuộn ngang để theo dõi các nhánh →</span></div>
      <WorkflowGraph topology={topology} events={graphEvents} selectedState={selectedState} onSelectState={(state) => { pinnedSelection.current = true; setSelection({ kind: "node", state }); }} />
      <div className="graph-footer"><span>Topology: {topology?.nodes.length ?? "—"} states · {topology?.edges.length ?? "—"} transitions</span><span>Event driven / canonical</span></div>
    </section>
    <Inspector event={selectedEvent} stateLabel={selectedNode?.label ?? null} stateStatus={selectedStatus} duration={selectedDuration} startedAt={events[0]?.timestamp ?? null} />
    <Timeline events={events} selectedSequence={selection?.kind === "event" ? selection.sequence : null} onSelect={(item) => { pinnedSelection.current = true; setSelection({ kind: "event", sequence: item.sequence }); }} />
    <ChatPanel submitted={submitted} submittedNote={submittedNote} draft={draft} onDraftChange={setDraft} onCompose={() => setDrawerOpen(true)} events={events} status={status} runId={runId} finalState={finalState} />
    <ProposalPanel snapshot={snapshot} finalState={finalState} />
    <RequestPanel open={drawerOpen} value={requirement} note={draft} error={error} onChange={setRequirement} onSubmit={handleSubmit} onClose={() => setDrawerOpen(false)} disabled={creating} />
  </main>;
}
