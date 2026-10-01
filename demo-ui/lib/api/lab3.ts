import type {
  ConfigurationSummary,
  ProposalOptionSummary,
  ProposalSummary,
  RunResultSummary,
  RunSnapshot,
  RunStatus,
} from "@/lib/contracts";
import type { ConversationMessage, ConversationRunResult, CustomerRequirement, RunExplanation } from "@/lib/lab3-contracts";
import { isFiniteNumber, isNullableNumber, isNullableString, isRecord, isString, isStringArray, parseApiResponse } from "./http";

function isRunStatus(value: unknown): value is RunStatus {
  return value === "pending" || value === "running" || value === "completed" || value === "failed";
}

function isCustomerRequirement(value: unknown): value is CustomerRequirement {
  if (!isRecord(value)) return false;
  return isNullableNumber(value.model_size_b) &&
    (value.usage === null || value.usage === "inference" || value.usage === "fine_tune") &&
    isNullableNumber(value.budget_vnd) && isNullableNumber(value.concurrent_users) &&
    isNullableNumber(value.context_length) && isNullableNumber(value.storage_requirement_gb) &&
    isNullableString(value.expansion_requirement) && isNullableString(value.training_method);
}

function isConversationRunResult(value: unknown): value is ConversationRunResult {
  if (!isRecord(value) || !isCustomerRequirement(value.requirement)) return false;
  if (value.status === "needs_information") {
    return isStringArray(value.missing_fields) && value.missing_fields.length > 0 && isString(value.question);
  }
  return value.status === "submitted" && isString(value.run_id) && isRunStatus(value.run_status);
}

function isConfigurationSummary(value: unknown): value is ConfigurationSummary {
  return isRecord(value) && isString(value.configuration_id) && isString(value.product_name) &&
    isNullableString(value.manufacturer) && isNullableString(value.gpu) && isNullableNumber(value.gpu_count) &&
    isNullableNumber(value.ram_gb) && isNullableNumber(value.storage_gb) &&
    isNullableNumber(value.estimated_price_vnd) && isStringArray(value.evidence_sources);
}

function isProposalOptionSummary(value: unknown): value is ProposalOptionSummary {
  return isRecord(value) && isString(value.name) && isString(value.rationale) &&
    isConfigurationSummary(value.configuration) && isNullableNumber(value.estimated_price_vnd) &&
    isStringArray(value.limitations);
}

function isProposalSummary(value: unknown): value is ProposalSummary {
  return isRecord(value) && isStringArray(value.selected_configuration_ids) &&
    isFiniteNumber(value.option_count) && isFiniteNumber(value.evidence_count) &&
    isNullableNumber(value.estimated_price_vnd) && isStringArray(value.limitations) &&
    isStringArray(value.sources) && Array.isArray(value.selected_configurations) &&
    value.selected_configurations.every(isConfigurationSummary) && Array.isArray(value.options) &&
    value.options.every(isProposalOptionSummary);
}

function isRunResultSummary(value: unknown): value is RunResultSummary {
  return isRecord(value) && isString(value.final_state) && isStringArray(value.history) &&
    isStringArray(value.candidate_configuration_ids) && typeof value.proposal_available === "boolean" &&
    (value.proposal === null || isProposalSummary(value.proposal)) && isStringArray(value.errors);
}

export function isRunSnapshot(value: unknown): value is RunSnapshot {
  return isRecord(value) && isString(value.run_id) && isRunStatus(value.status) &&
    isString(value.created_at) && isNullableString(value.started_at) && isNullableString(value.completed_at) &&
    isNullableString(value.final_state) && (value.result === null || isRunResultSummary(value.result)) &&
    isNullableString(value.error) && isFiniteNumber(value.event_count);
}

function isRunExplanation(value: unknown): value is RunExplanation {
  return isRecord(value) && isString(value.run_id) && isRunStatus(value.status) &&
    isNullableString(value.final_state) && isString(value.explanation) && value.explanation.length > 0;
}

export function submitConversation(
  messages: ConversationMessage[],
  signal?: AbortSignal,
): Promise<ConversationRunResult> {
  return fetch("/api/backend/conversation/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal,
  }).then((response) => parseApiResponse(response, isConversationRunResult, "Lab 3 conversation request failed"));
}

export function fetchRunExplanation(runId: string, signal?: AbortSignal): Promise<RunExplanation> {
  return fetch(`/api/backend/runs/${encodeURIComponent(runId)}/explanation`, {
    method: "POST",
    signal,
  }).then((response) => parseApiResponse(response, isRunExplanation, "Lab 3 explanation request failed"));
}
