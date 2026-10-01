"use client";

import { useState, type FormEvent } from "react";

import { ConversationPanel } from "@/components/lab3/conversation-panel";
import { RequestPanel } from "@/components/request-panel";
import type { RequirementForm } from "@/lib/contracts";
import { useLab3Conversation } from "./hooks/use-lab3-conversation";
import { useLab3WorkflowRun } from "./hooks/use-lab3-workflow-run";
import { WorkflowHeader } from "./workflow-header";
import { WorkflowObservability } from "./workflow-observability";
import { WorkflowRunbar } from "./workflow-runbar";
import { WorkflowTopologyPanel } from "./workflow-topology-panel";

const initialRequirement: RequirementForm = {
  model_size_b: 20,
  usage: "inference",
  concurrent_users: 2,
  budget_vnd: 300_000_000,
  storage_requirement_gb: 1000,
};

export function WorkflowConsole() {
  const conversation = useLab3Conversation();
  const workflow = useLab3WorkflowRun(conversation.appendAssistantMessage);
  const [requirement, setRequirement] = useState(initialRequirement);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const displayError = conversation.error ?? workflow.error;

  const handleConversationSubmit = (event: FormEvent<HTMLFormElement>) => conversation.submit(event, {
    isRunActive: workflow.isRunActive,
    beginRunCreation: workflow.beginRunCreation,
    finishRunCreation: workflow.finishRunCreation,
    attachRun: workflow.attachRun,
  });

  const handleNewConversation = () => {
    if (workflow.isRunActive || workflow.creationBusy || conversation.busy) return;
    if (workflow.resetRunView()) conversation.startNewConversation();
  };

  const handleManualSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const created = await workflow.startManualRun({ ...requirement });
    if (created) setDrawerOpen(false);
  };

  const exportTopology = () => {
    if (!workflow.topology) return;
    const blob = new Blob([JSON.stringify(workflow.topology, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "lab3-workflow-topology.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  return <div className="lab3-workspace">
    <section className="lab3-main" id="lab3-workflow" aria-label="Lab 3 deterministic workflow">
      <WorkflowHeader />
      <WorkflowRunbar
        runId={workflow.runId}
        status={workflow.status}
        elapsedMs={workflow.elapsedMs}
        creationBusy={workflow.creationBusy}
        topologyAvailable={workflow.topology !== null}
        onOpenStructuredRun={() => { workflow.clearError(); setDrawerOpen(true); }}
        onExportTopology={exportTopology}
      />
      {displayError ? <p className="stitch-alert" role="alert">{displayError}</p> : null}
      {workflow.connectionNote ? <p className="stitch-alert warning" role="status">{workflow.connectionNote}</p> : null}
      <WorkflowTopologyPanel
        topology={workflow.topology}
        events={workflow.graphEvents}
        selectedState={workflow.selectedState}
        onSelectState={workflow.selectNode}
      />
      <WorkflowObservability
        events={workflow.events}
        snapshot={workflow.snapshot}
        finalState={workflow.finalState}
        selectedEvent={workflow.selectedEvent}
        selectedNodeLabel={workflow.selectedNode?.label ?? null}
        selectedStatus={workflow.selectedStatus}
        selectedDuration={workflow.selectedDuration}
        onSelectEvent={workflow.selectEvent}
      />
      <footer className="lab3-footer"><span>Deterministic state machine · contract verified</span><span>{workflow.runId ? `RUN ${workflow.runId}` : "Workflow API data appears when requested"}</span></footer>
    </section>

    <ConversationPanel
      messages={conversation.messages}
      draft={conversation.draft}
      busy={conversation.busy}
      runActive={workflow.isRunActive}
      creationBusy={workflow.creationBusy}
      error={conversation.error}
      onDraftChange={conversation.setDraft}
      onSubmit={handleConversationSubmit}
      onNewConversation={handleNewConversation}
    />
    <RequestPanel
      open={drawerOpen}
      value={requirement}
      note=""
      error={displayError}
      onChange={setRequirement}
      onSubmit={handleManualSubmit}
      onClose={() => setDrawerOpen(false)}
      disabled={workflow.creationBusy || workflow.isRunActive}
    />
  </div>;
}
