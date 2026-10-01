import type { RunSnapshot, WorkflowEvent } from "@/lib/contracts";
import { Inspector } from "@/components/inspector";
import { ProposalPanel } from "@/components/proposal-panel";
import { Timeline } from "@/components/timeline";
import type { NodeStatus } from "@/lib/contracts";

export function WorkflowObservability({
  events,
  snapshot,
  finalState,
  selectedEvent,
  selectedNodeLabel,
  selectedStatus,
  selectedDuration,
  onSelectEvent,
}: {
  events: WorkflowEvent[];
  snapshot: RunSnapshot | null;
  finalState: string | null;
  selectedEvent: WorkflowEvent | null;
  selectedNodeLabel: string | null;
  selectedStatus: NodeStatus | null;
  selectedDuration: number | null;
  onSelectEvent: (event: WorkflowEvent) => void;
}) {
  return <div className="lab3-observability">
    <Timeline events={events} selectedSequence={selectedEvent?.sequence ?? null} onSelect={onSelectEvent} />
    <div className="lab3-inspector-column">
      <Inspector event={selectedEvent} stateLabel={selectedNodeLabel} stateStatus={selectedStatus} duration={selectedDuration} startedAt={events[0]?.timestamp ?? null} />
      <ProposalPanel snapshot={snapshot} finalState={finalState} />
    </div>
  </div>;
}
