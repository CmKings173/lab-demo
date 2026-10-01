import {
  LAB1_CASE_METRIC_KEYS,
  LAB1_METRIC_KEYS,
  type Lab1CaseDetail,
  type Lab1CaseIndexItem,
  type Lab1CaseMetricKey,
  type Lab1Dashboard,
  type Lab1MetricComparison,
  type Lab1SafeValue,
  type Lab1ToolCall,
  type Lab1TrainingPoint,
} from "@/lib/lab1-contracts";
import { isFiniteNumber, isNullableNumber, isNullableString, isRecord, isString, parseApiResponse } from "./http";

function isSafeValue(value: unknown, depth = 0): value is Lab1SafeValue {
  if (value === null || typeof value === "boolean" || isString(value)) return true;
  if (isFiniteNumber(value)) return true;
  if (depth >= 4) return false;
  if (Array.isArray(value)) return value.length <= 20 && value.every((item) => isSafeValue(item, depth + 1));
  if (!isRecord(value)) return false;
  const entries = Object.entries(value);
  return entries.length <= 30 && entries.every(([key, item]) =>
    /^[a-zA-Z0-9_-]{1,64}$/.test(key) && isSafeValue(item, depth + 1));
}

function isToolCall(value: unknown): value is Lab1ToolCall {
  return isRecord(value) && isString(value.name) && isRecord(value.arguments) &&
    Object.values(value.arguments).every((item) => isSafeValue(item));
}

function isToolCalls(value: unknown): value is Lab1ToolCall[] {
  return Array.isArray(value) && value.length <= 20 && value.every(isToolCall);
}

function isCaseMetricMap(value: unknown): value is Record<Lab1CaseMetricKey, boolean | null> {
  return isRecord(value) && LAB1_CASE_METRIC_KEYS.every((key) => value[key] === null || typeof value[key] === "boolean");
}

function isCaseModelResult(value: unknown): boolean {
  return isRecord(value) && isString(value.assistantText) && isToolCalls(value.toolCalls) &&
    isCaseMetricMap(value.metrics) && typeof value.hasError === "boolean";
}

function isTrainingPoint(value: unknown): value is Lab1TrainingPoint {
  return isRecord(value) && isFiniteNumber(value.step) && isFiniteNumber(value.epoch) && isFiniteNumber(value.value);
}

function isMetricComparison(value: unknown): value is Lab1MetricComparison {
  return isRecord(value) && isString(value.key) && LAB1_METRIC_KEYS.some((key) => key === value.key) &&
    isString(value.label) && (value.direction === "higher" || value.direction === "lower") &&
    isFiniteNumber(value.base) && isFiniteNumber(value.candidate) && isFiniteNumber(value.delta) &&
    isFiniteNumber(value.baseCount) && isFiniteNumber(value.candidateCount);
}

function isCaseIndexItem(value: unknown): value is Lab1CaseIndexItem {
  return isRecord(value) && isString(value.caseId) && isString(value.intent) && isString(value.scenarioType) &&
    typeof value.shouldCallTool === "boolean" && isString(value.promptPreview) &&
    (value.baseToolCallRequiredMatch === null || typeof value.baseToolCallRequiredMatch === "boolean") &&
    (value.candidateToolCallRequiredMatch === null || typeof value.candidateToolCallRequiredMatch === "boolean");
}

export function isLab1Dashboard(value: unknown): value is Lab1Dashboard {
  if (!isRecord(value) || !isRecord(value.run) || !isRecord(value.inputs) || !isRecord(value.evaluation)) return false;
  const { run, inputs, evaluation } = value;
  return isString(run.id) && (run.status === "completed" || run.status === "incomplete") &&
    isString(run.baseModel) && isString(run.candidateModel) && isString(run.method) && isString(run.precision) &&
    typeof run.loraEnabled === "boolean" && typeof run.qloraEnabled === "boolean" &&
    isFiniteNumber(run.epochs) && isFiniteNumber(run.epoch) && isFiniteNumber(run.globalStep) && isFiniteNumber(run.maxSteps) &&
    isNullableNumber(run.runtimeSeconds) && isNullableNumber(run.trainLoss) && isNullableNumber(run.bestEvalLoss) &&
    isNullableString(run.bestCheckpoint) && isNullableNumber(run.bestCheckpointEpoch) && isNullableNumber(run.bestCheckpointStep) &&
    isNullableNumber(run.maxSequenceLength) && isNullableNumber(run.learningRate) && isNullableString(run.scheduler) &&
    isNullableNumber(run.warmupRatio) && isNullableNumber(run.perDeviceBatchSize) &&
    isNullableNumber(run.perDeviceEvalBatchSize) && isNullableNumber(run.gradientAccumulationSteps) &&
    isNullableNumber(run.seed) && isNullableNumber(run.loraRank) && isNullableNumber(run.loraAlpha) &&
    isNullableNumber(run.loraDropout) && isString(run.targetModules) &&
    isString(inputs.trainFile) && isString(inputs.validationFile) &&
    isNullableString(inputs.trainFingerprint) && isNullableString(inputs.validationFingerprint) &&
    (inputs.generatedExportsMatchRunManifest === null || typeof inputs.generatedExportsMatchRunManifest === "boolean") &&
    isNullableNumber(inputs.trainingRows) && isNullableNumber(inputs.validationRows) &&
    isNullableNumber(inputs.goldSeedExamples) && isNullableNumber(inputs.goldSeedFamilies) &&
    isNullableNumber(inputs.goldSeedTrainRows) && isNullableNumber(inputs.goldSeedValidationRows) &&
    isNullableNumber(inputs.goldSeedTestRows) &&
    Array.isArray(value.trainingLoss) && value.trainingLoss.every(isTrainingPoint) &&
    Array.isArray(value.validationLoss) && value.validationLoss.every(isTrainingPoint) &&
    isFiniteNumber(evaluation.benchmarkCases) && isFiniteNumber(evaluation.successfulCases) &&
    isFiniteNumber(evaluation.failedCases) && isString(evaluation.method) && isString(evaluation.benchmarkFingerprint) &&
    isString(evaluation.baseModel) && isString(evaluation.candidateModel) && Array.isArray(evaluation.metrics) &&
    evaluation.metrics.every(isMetricComparison) && Array.isArray(value.cases) && value.cases.every(isCaseIndexItem);
}

function isLab1CaseDetail(value: unknown): value is Lab1CaseDetail {
  return isRecord(value) && isString(value.caseId) && isString(value.prompt) && isString(value.intent) &&
    isString(value.scenarioType) && typeof value.shouldCallTool === "boolean" && typeof value.shouldAbstain === "boolean" &&
    isToolCalls(value.expectedToolCalls) && isCaseModelResult(value.base) && isCaseModelResult(value.candidate);
}

export function fetchLab1Dashboard(signal?: AbortSignal): Promise<Lab1Dashboard> {
  return fetch("/api/lab1", { cache: "no-store", signal })
    .then((response) => parseApiResponse(response, isLab1Dashboard, "Lab 1 dashboard request failed"));
}

export function fetchLab1Case(caseId: string, signal?: AbortSignal): Promise<Lab1CaseDetail> {
  return fetch(`/api/lab1/cases/${encodeURIComponent(caseId)}`, { cache: "no-store", signal })
    .then((response) => parseApiResponse(response, isLab1CaseDetail, "Lab 1 case request failed"));
}
