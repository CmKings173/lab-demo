export type RunStatus = "pending" | "running" | "completed" | "failed";

export type WorkflowEventType =
  | "workflow.started" | "workflow.completed" | "workflow.failed"
  | "state.started" | "state.completed" | "state.failed"
  | "tool.started" | "tool.completed" | "tool.failed"
  | "validation.result" | "document.hit" | "fact.resolved"
  | "fact.rejected" | "fact.conflict" | "proposal.generated" | "proposal.verified";

export interface WorkflowTopologyNode { id: string; label: string; kind: "state"; terminal: boolean; }
export interface WorkflowTopologyEdge { source: string; target: string; conditional: boolean; }
export interface WorkflowTopology { nodes: WorkflowTopologyNode[]; edges: WorkflowTopologyEdge[]; }

export interface WorkflowEvent {
  event_id: string;
  run_id: string;
  sequence: number;
  type: WorkflowEventType;
  timestamp: string;
  state: string | null;
  duration_ms: number | null;
  payload: Record<string, unknown>;
}

export interface CreateRunResponse { run_id: string; status: RunStatus; }
export interface ProposalSummary {
  selected_configuration_ids: string[];
  option_count: number;
  evidence_count: number;
  estimated_price_vnd: number | null;
  limitations: string[];
  sources: string[];
}
export interface RunResultSummary {
  final_state: string;
  history: string[];
  candidate_configuration_ids: string[];
  proposal_available: boolean;
  proposal: ProposalSummary | null;
  errors: string[];
}
export interface RunSnapshot {
  run_id: string;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  final_state: string | null;
  result: RunResultSummary | null;
  error: string | null;
  event_count: number;
}

export type RequirementForm = {
  model_size_b: number;
  usage: "inference" | "fine_tune";
  concurrent_users: number;
  budget_vnd: number;
  storage_requirement_gb: number;
};
export type NodeStatus = "pending" | "running" | "completed" | "failed";
