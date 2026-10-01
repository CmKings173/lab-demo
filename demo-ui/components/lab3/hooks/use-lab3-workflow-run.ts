"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { createRun, fetchTopology, subscribeToRun } from "@/lib/api";
import { fetchRunExplanation } from "@/lib/api/lab3";
import type { RequirementForm, RunSnapshot, RunStatus, WorkflowEvent, WorkflowTopology } from "@/lib/contracts";
import { nodeStatusFor } from "@/lib/fold-events";
import { stateDuration } from "@/lib/graph-runtime";
import { canBeginRun, isRunInProgress, type Lab3RunStatus } from "@/lib/lab3-run-state";
import { resolveRunCreation } from "@/lib/run-creation-state";
import { fetchTerminalSnapshot } from "@/lib/terminal-snapshot";

type Selection = { kind: "event"; sequence: number } | { kind: "node"; state: string } | null;

export function useLab3WorkflowRun(onExplanationMessage: (message: string) => void) {
  const [topology, setTopology] = useState<WorkflowTopology | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [selection, setSelection] = useState<Selection>(null);
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<Lab3RunStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [connectionNote, setConnectionNote] = useState<string | null>(null);
  const [creationBusy, setCreationBusy] = useState(false);
  const activeRunId = useRef<string | null>(null);
  const statusRef = useRef<Lab3RunStatus>("idle");
  const creationReserved = useRef(false);
  const requestGeneration = useRef(0);
  const pinnedSelection = useRef(false);

  const updateStatus = useCallback((nextStatus: Lab3RunStatus) => {
    statusRef.current = nextStatus;
    setStatus(nextStatus);
  }, []);

  const beginRunCreation = useCallback(() => {
    if (!canBeginRun(statusRef.current, creationReserved.current)) return false;
    creationReserved.current = true;
    setCreationBusy(true);
    return true;
  }, []);

  const finishRunCreation = useCallback(() => {
    creationReserved.current = false;
    setCreationBusy(false);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const attachRun = useCallback((nextRunId: string, nextStatus: RunStatus) => {
    if (activeRunId.current !== null && isRunInProgress(statusRef.current)) return false;
    activeRunId.current = nextRunId;
    pinnedSelection.current = false;
    setConnectionNote(null);
    setSnapshot(null);
    setEvents([]);
    setSelection(null);
    setRunId(nextRunId);
    setError(null);
    updateStatus(nextStatus);
    return true;
  }, [updateStatus]);

  const resetRunView = useCallback(() => {
    if (!canBeginRun(statusRef.current, creationReserved.current)) return false;
    requestGeneration.current += 1;
    activeRunId.current = null;
    pinnedSelection.current = false;
    setConnectionNote(null);
    setSnapshot(null);
    setEvents([]);
    setSelection(null);
    setRunId(null);
    setError(null);
    updateStatus("idle");
    return true;
  }, [updateStatus]);

  const startManualRun = useCallback(async (requirement: RequirementForm) => {
    if (!beginRunCreation()) return false;
    const generation = ++requestGeneration.current;
    setError(null);
    try {
      const created = await createRun(requirement);
      const transition = resolveRunCreation({
        generation,
        currentGeneration: requestGeneration.current,
        requirement,
        note: "",
        outcome: { kind: "success", created },
      });
      if (transition.kind !== "created") return false;
      return attachRun(transition.runId, transition.status);
    } catch (reason) {
      const transition = resolveRunCreation({
        generation,
        currentGeneration: requestGeneration.current,
        requirement,
        note: "",
        outcome: { kind: "failure", error: reason instanceof Error ? reason.message : "Không thể tạo workflow run." },
      });
      if (transition.kind === "failed") setError(transition.error);
      return false;
    } finally {
      finishRunCreation();
    }
  }, [attachRun, beginRunCreation, finishRunCreation]);

  useEffect(() => {
    let current = true;
    fetchTopology()
      .then((value) => { if (current) setTopology(value); })
      .catch((reason: unknown) => {
        if (current) setError(reason instanceof Error ? reason.message : "Workflow topology could not be loaded.");
      });
    return () => { current = false; };
  }, []);

  useEffect(() => {
    if (!runId) return undefined;
    let terminalHandled = false;
    const isCurrentRun = () => activeRunId.current === runId;
    const close = subscribeToRun(
      runId,
      0,
      (event) => {
        if (!isCurrentRun()) return;
        setEvents((current) => current.some((item) => item.sequence === event.sequence) ? current : [...current, event]);
        if (!pinnedSelection.current) setSelection({ kind: "event", sequence: event.sequence });
        if (event.type === "workflow.started") updateStatus("running");
        if (event.type === "workflow.completed") updateStatus("completed");
        if (event.type === "workflow.failed") updateStatus("failed");
      },
      (message) => { if (isCurrentRun()) setConnectionNote(message); },
      () => { if (isCurrentRun()) setConnectionNote(null); },
      () => {
        if (terminalHandled) return;
        terminalHandled = true;
        void fetchTerminalSnapshot(runId)
          .then(async (nextSnapshot) => {
            if (!isCurrentRun()) return;
            setSnapshot(nextSnapshot);
            updateStatus(nextSnapshot.status);
            const result = await fetchRunExplanation(runId);
            if (isCurrentRun()) onExplanationMessage(result.explanation);
          })
          .catch((reason: unknown) => {
            if (isCurrentRun()) setError(reason instanceof Error ? reason.message : "The terminal workflow result could not be loaded.");
          });
      },
    );
    return close;
  }, [onExplanationMessage, runId, updateStatus]);

  const selectEvent = useCallback((event: WorkflowEvent) => {
    pinnedSelection.current = true;
    setSelection({ kind: "event", sequence: event.sequence });
  }, []);

  const selectNode = useCallback((state: string) => {
    pinnedSelection.current = true;
    setSelection({ kind: "node", state });
  }, []);

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
  const elapsedMs = snapshot?.started_at && snapshot.completed_at
    ? Math.max(0, new Date(snapshot.completed_at).getTime() - new Date(snapshot.started_at).getTime())
    : null;

  return {
    topology, events, graphEvents, selectedEvent, selectedState, selectedNode, selectedStatus, selectedDuration,
    snapshot, runId, status, error, connectionNote, creationBusy, finalState, elapsedMs,
    isRunActive: isRunInProgress(status), beginRunCreation, finishRunCreation, attachRun, resetRunView,
    startManualRun, selectEvent, selectNode, clearError,
  };
}
