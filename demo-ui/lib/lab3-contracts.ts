export const LAB3_MAX_MESSAGE_CHARS = 4000;

export type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

export type CustomerRequirement = {
  model_size_b: number | null;
  usage: "inference" | "fine_tune" | null;
  budget_vnd: number | null;
  concurrent_users: number | null;
  context_length: number | null;
  storage_requirement_gb: number | null;
  expansion_requirement: string | null;
  training_method: string | null;
};

export type ConversationRunResult = {
  status: "conversation";
  requirement: CustomerRequirement;
  missing_fields: string[];
  reply: string;
} | {
  status: "submitted";
  reply: string;
  run_id: string;
  run_status: "pending" | "running" | "completed" | "failed";
  requirement: CustomerRequirement;
};

export type RunExplanation = {
  run_id: string;
  status: "pending" | "running" | "completed" | "failed";
  final_state: string | null;
  explanation: string;
};
