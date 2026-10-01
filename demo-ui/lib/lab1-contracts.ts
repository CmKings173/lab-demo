export const LAB1_METRIC_KEYS = [
  "tool_call_required_accuracy",
  "tool_name_accuracy",
  "tool_call_sequence_accuracy",
  "abstention_accuracy",
  "missing_tool_call_rate",
  "unexpected_tool_call_rate",
  "tool_argument_accuracy",
] as const;

export type Lab1MetricKey = (typeof LAB1_METRIC_KEYS)[number];

export interface Lab1MetricComparison {
  key: Lab1MetricKey;
  label: string;
  direction: "higher" | "lower";
  base: number;
  candidate: number;
  delta: number;
  baseCount: number;
  candidateCount: number;
}

export const LAB1_CASE_METRIC_KEYS = LAB1_METRIC_KEYS;

export const LAB1_ERROR_METRIC_KEYS = [
  "missing_tool_call_rate",
  "unexpected_tool_call_rate",
] as const;

export interface Lab1TrainingPoint {
  step: number;
  epoch: number;
  value: number;
}

export interface Lab1CaseIndexItem {
  caseId: string;
  intent: string;
  scenarioType: string;
  shouldCallTool: boolean;
  promptPreview: string;
  baseToolCallRequiredMatch: boolean | null;
  candidateToolCallRequiredMatch: boolean | null;
}

export interface Lab1Dashboard {
  run: {
    id: string;
    status: "completed" | "incomplete";
    baseModel: string;
    candidateModel: string;
    method: string;
    precision: string;
    loraEnabled: boolean;
    qloraEnabled: boolean;
    epochs: number;
    epoch: number;
    globalStep: number;
    maxSteps: number;
    runtimeSeconds: number | null;
    trainLoss: number | null;
    bestEvalLoss: number | null;
    bestCheckpoint: string | null;
    bestCheckpointEpoch: number | null;
    bestCheckpointStep: number | null;
    maxSequenceLength: number | null;
    learningRate: number | null;
    scheduler: string | null;
    warmupRatio: number | null;
    perDeviceBatchSize: number | null;
    perDeviceEvalBatchSize: number | null;
    gradientAccumulationSteps: number | null;
    seed: number | null;
    loraRank: number | null;
    loraAlpha: number | null;
    loraDropout: number | null;
    targetModules: string;
  };
  inputs: {
    trainFile: string;
    validationFile: string;
    trainFingerprint: string | null;
    validationFingerprint: string | null;
    generatedExportsMatchRunManifest: boolean | null;
    trainingRows: number | null;
    validationRows: number | null;
    goldSeedExamples: number | null;
    goldSeedFamilies: number | null;
    goldSeedTrainRows: number | null;
    goldSeedValidationRows: number | null;
    goldSeedTestRows: number | null;
  };
  trainingLoss: Lab1TrainingPoint[];
  validationLoss: Lab1TrainingPoint[];
  evaluation: {
    benchmarkCases: number;
    successfulCases: number;
    failedCases: number;
    method: string;
    benchmarkFingerprint: string;
    baseModel: string;
    candidateModel: string;
    metrics: Lab1MetricComparison[];
  };
  cases: Lab1CaseIndexItem[];
}

export type Lab1SafeValue = string | number | boolean | null | Lab1SafeValue[] | { [key: string]: Lab1SafeValue };

export interface Lab1ToolCall {
  name: string;
  arguments: { [key: string]: Lab1SafeValue };
}

export type Lab1CaseMetricKey = (typeof LAB1_CASE_METRIC_KEYS)[number];

export interface Lab1CaseModelResult {
  assistantText: string;
  toolCalls: Lab1ToolCall[];
  metrics: Record<Lab1CaseMetricKey, boolean | null>;
  hasError: boolean;
}

export interface Lab1CaseDetail {
  caseId: string;
  prompt: string;
  intent: string;
  scenarioType: string;
  shouldCallTool: boolean;
  shouldAbstain: boolean;
  expectedToolCalls: Lab1ToolCall[];
  base: Lab1CaseModelResult;
  candidate: Lab1CaseModelResult;
}
