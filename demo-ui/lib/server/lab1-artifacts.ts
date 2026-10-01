import "server-only";

import { createHash } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import { basename, resolve } from "node:path";

import type {
  Lab1CaseDetail,
  Lab1CaseIndexItem,
  Lab1CaseMetricKey,
  Lab1Dashboard,
  Lab1MetricComparison,
  Lab1MetricKey,
  Lab1SafeValue,
  Lab1ToolCall,
  Lab1TrainingPoint,
} from "@/lib/lab1-contracts";
import { LAB1_CASE_METRIC_KEYS } from "@/lib/lab1-contracts";

type JsonRecord = Record<string, unknown>;
type ArtifactName =
  | "runs/qwen3-14b-lora-20260925-040048/run_manifest.json"
  | "runs/qwen3-14b-lora-20260925-040048/checkpoint-363/trainer_state.json"
  | "runs/qwen3-14b-lora-20260925-040048/checkpoint-121/trainer_state.json"
  | "eval/base.json"
  | "eval/lora.json"
  | "eval/comparison.json";

const artifactNames: Record<ArtifactName, string> = {
  "runs/qwen3-14b-lora-20260925-040048/run_manifest.json": "run_manifest.json",
  "runs/qwen3-14b-lora-20260925-040048/checkpoint-363/trainer_state.json": "checkpoint-363/trainer_state.json",
  "runs/qwen3-14b-lora-20260925-040048/checkpoint-121/trainer_state.json": "checkpoint-121/trainer_state.json",
  "eval/base.json": "eval/base.json",
  "eval/lora.json": "eval/lora.json",
  "eval/comparison.json": "eval/comparison.json",
};

const metricDefinitions: Array<{ key: Lab1MetricKey; label: string; direction: "higher" | "lower" }> = [
  { key: "tool_call_required_accuracy", label: "Tool call required", direction: "higher" },
  { key: "tool_name_accuracy", label: "Tool name accuracy", direction: "higher" },
  { key: "tool_call_sequence_accuracy", label: "Tool sequence accuracy", direction: "higher" },
  { key: "abstention_accuracy", label: "Abstention accuracy", direction: "higher" },
  { key: "missing_tool_call_rate", label: "Missing tool call rate", direction: "lower" },
  { key: "unexpected_tool_call_rate", label: "Unexpected tool call rate", direction: "lower" },
  { key: "tool_argument_accuracy", label: "Exact tool arguments", direction: "higher" },
];

export class Lab1ArtifactError extends Error {
  constructor(message: string, readonly status = 503) {
    super(message);
  }
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(value: unknown, label: string): JsonRecord {
  if (!isRecord(value)) throw new Lab1ArtifactError(`Lab 1 data is unavailable or invalid (${label}).`);
  return value;
}

function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function requiredNumber(value: unknown, label: string): number {
  const result = numberValue(value);
  if (result === null) throw new Lab1ArtifactError(`Lab 1 data is unavailable or invalid (${label}).`);
  return result;
}

function safeFileName(value: unknown): string {
  if (typeof value !== "string") return "Unavailable";
  const finalName = basename(value.replaceAll("\\", "/"));
  return /^[a-zA-Z0-9._-]{1,100}$/.test(finalName) ? finalName : "Unavailable";
}

function safeValue(value: unknown, depth = 0): Lab1SafeValue {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") return value.slice(0, 400);
  if (depth >= 3) return "[nested value omitted]";
  if (Array.isArray(value)) return value.slice(0, 20).map((item) => safeValue(item, depth + 1));
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => /^[a-zA-Z0-9_-]{1,64}$/.test(key))
        .slice(0, 30)
        .map(([key, item]) => [key, safeValue(item, depth + 1)]),
    );
  }
  return null;
}

function isSafeRecord(value: Lab1SafeValue): value is Record<string, Lab1SafeValue> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeToolCalls(value: unknown): Lab1ToolCall[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 20).flatMap((item) => {
    if (!isRecord(item) || typeof item.name !== "string") return [];
    const args = safeValue(item.arguments);
    return [{
      name: item.name.slice(0, 100),
      arguments: isSafeRecord(args) ? args : {},
    }];
  });
}

function evaluationCases(report: JsonRecord, label: string): JsonRecord[] {
  if (!Array.isArray(report.cases)) throw new Lab1ArtifactError(`Lab 1 evaluation cases are unavailable (${label}).`);
  return report.cases.map((item, index) => record(item, `${label}.cases[${index}]`));
}

function caseId(value: JsonRecord): string {
  return stringValue(value.case_id);
}

function caseGold(value: JsonRecord): JsonRecord {
  const gold = record(value.gold_labels, `${caseId(value)}.gold_labels`);
  if (typeof gold.intent !== "string" || typeof gold.scenario_type !== "string" ||
      typeof gold.should_call_tool !== "boolean" || typeof gold.should_abstain !== "boolean" ||
      !Array.isArray(gold.expected_tool_calls)) {
    throw new Lab1ArtifactError(`Lab 1 case labels are unavailable or invalid (${caseId(value)}).`);
  }
  return gold;
}

function casePrompt(value: JsonRecord): string {
  if (!Array.isArray(value.input_messages)) return "";
  return value.input_messages.flatMap((item) => {
    if (!isRecord(item) || (item.role !== "user" && item.role !== "assistant") || typeof item.content !== "string") return [];
    const role = item.role === "user" ? "USER" : "ASSISTANT";
    return [`${role}: ${item.content}`];
  }).join("\n\n").slice(0, 8000);
}

function caseMetricValues(value: JsonRecord): Record<Lab1CaseMetricKey, boolean | null> {
  const source = isRecord(value.metrics) ? value.metrics : {};
  const metric = (key: Lab1CaseMetricKey): boolean | null =>
    typeof source[key] === "boolean" ? source[key] : null;
  return {
    tool_call_required_accuracy: metric("tool_call_required_accuracy"),
    tool_name_accuracy: metric("tool_name_accuracy"),
    tool_argument_accuracy: metric("tool_argument_accuracy"),
    tool_call_sequence_accuracy: metric("tool_call_sequence_accuracy"),
    abstention_accuracy: metric("abstention_accuracy"),
    missing_tool_call_rate: metric("missing_tool_call_rate"),
    unexpected_tool_call_rate: metric("unexpected_tool_call_rate"),
  };
}

function caseModelResult(value: JsonRecord) {
  return {
    assistantText: stringValue(value.predicted_assistant_content).slice(0, 8000),
    toolCalls: safeToolCalls(value.predicted_tool_calls),
    metrics: caseMetricValues(value),
    hasError: value.error !== null && value.error !== undefined,
  };
}

function caseIndexItem(baseCase: JsonRecord, loraCase: JsonRecord): Lab1CaseIndexItem {
  const gold = caseGold(baseCase);
  const prompt = casePrompt(baseCase);
  const baseMetrics = caseMetricValues(baseCase);
  const candidateMetrics = caseMetricValues(loraCase);
  return {
    caseId: caseId(baseCase),
    intent: stringValue(gold.intent, "Unknown"),
    scenarioType: stringValue(gold.scenario_type, "Unknown"),
    shouldCallTool: gold.should_call_tool === true,
    promptPreview: prompt.slice(0, 220),
    baseToolCallRequiredMatch: baseMetrics.tool_call_required_accuracy,
    candidateToolCallRequiredMatch: candidateMetrics.tool_call_required_accuracy,
  };
}

function safeTrainingPoints(value: unknown, metricKey: "loss" | "eval_loss"): Lab1TrainingPoint[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!isRecord(item)) return [];
    const loss = numberValue(item[metricKey]);
    const step = numberValue(item.step);
    const epoch = numberValue(item.epoch);
    return loss !== null && step !== null && epoch !== null
      ? [{ step, epoch, value: loss }]
      : [];
  });
}

function reportMetric(value: unknown, label: string): { value: number; count: number } {
  const source = record(value, label);
  const metricValue = requiredNumber(source.value, `${label}.value`);
  const count = requiredNumber(source.count, `${label}.count`);
  if (metricValue < 0 || metricValue > 1 || count < 0 || !Number.isInteger(count)) {
    throw new Lab1ArtifactError(`Lab 1 evaluation metric is invalid (${label}).`);
  }
  return { value: metricValue, count };
}

async function resolveArtifactRoot(): Promise<string> {
  const workingDirectory = process.cwd();
  const candidates = [
    resolve(workingDirectory, "artifacts", "lab1"),
    resolve(workingDirectory, "..", "artifacts", "lab1"),
  ];
  const runManifest = "runs/qwen3-14b-lora-20260925-040048/run_manifest.json";
  for (const candidate of candidates) {
    try {
      await access(resolve(candidate, runManifest));
      return candidate;
    } catch {
      // Try the other fixed location; no request value participates in resolution.
    }
  }
  throw new Lab1ArtifactError(
    "Lab 1 data is unavailable (run_manifest.json). Looked in the fixed repository artifact location from the current directory and its parent.",
  );
}

async function readArtifact(root: string, name: ArtifactName): Promise<unknown> {
  const filePath = resolve(root, name);
  try {
    const value: unknown = JSON.parse(await readFile(filePath, "utf8"));
    return value;
  } catch {
    throw new Lab1ArtifactError(`Lab 1 data is unavailable (${artifactNames[name]}). Restore that generated artifact and reload.`);
  }
}

async function readJsonlSummary(
  repositoryRoot: string,
  relativePath: string,
): Promise<{ rowCount: number; sha256: string } | null> {
  try {
    const bytes = await readFile(resolve(repositoryRoot, relativePath));
    const rows = bytes.toString("utf8").split(/\r?\n/).filter((line) => line.trim().length > 0);
    for (const row of rows) {
      if (!isRecord(JSON.parse(row))) return null;
    }
    return { rowCount: rows.length, sha256: createHash("sha256").update(bytes).digest("hex") };
  } catch {
    return null;
  }
}

async function readGoldSeedCounts(repositoryRoot: string): Promise<{
  examples: number | null;
  families: number | null;
  trainRows: number | null;
  validationRows: number | null;
  testRows: number | null;
}> {
  try {
    const source: unknown = JSON.parse(await readFile(resolve(repositoryRoot, "lab1_finetune/data/gold_specs.json"), "utf8"));
    const manifestValue: unknown = JSON.parse(await readFile(resolve(repositoryRoot, "lab1_finetune/data/manifests/gold_seed_vi_manifest.json"), "utf8"));
    if (!Array.isArray(source) || source.length === 0 || !isRecord(manifestValue)) {
      return { examples: null, families: null, trainRows: null, validationRows: null, testRows: null };
    }
    const splitCounts = manifestValue.split_counts;
    if (!isRecord(splitCounts)) return { examples: null, families: null, trainRows: null, validationRows: null, testRows: null };

    const exampleIds = new Set<string>();
    const families = new Set<string>();
    for (const item of source) {
      if (!isRecord(item) || typeof item.example_id !== "string" || !item.example_id.trim() ||
          typeof item.family !== "string" || !item.family.trim() || exampleIds.has(item.example_id)) {
        return { examples: null, families: null, trainRows: null, validationRows: null, testRows: null };
      }
      exampleIds.add(item.example_id);
      families.add(item.family);
    }
    const trainRows = numberValue(splitCounts.train);
    const validationRows = numberValue(splitCounts.validation);
    const testRows = numberValue(splitCounts.test);
    const declaredExamples = numberValue(manifestValue.example_count);
    const declaredFamilies = numberValue(manifestValue.family_count);
    const isValidCount = (count: number | null): count is number =>
      count !== null && Number.isInteger(count) && count >= 0;
    if (!isValidCount(trainRows) || !isValidCount(validationRows) || !isValidCount(testRows) ||
        declaredExamples !== exampleIds.size || declaredFamilies !== families.size ||
        trainRows + validationRows + testRows !== exampleIds.size) {
      return { examples: null, families: null, trainRows: null, validationRows: null, testRows: null };
    }
    return { examples: exampleIds.size, families: families.size, trainRows, validationRows, testRows };
  } catch {
    return { examples: null, families: null, trainRows: null, validationRows: null, testRows: null };
  }
}

async function readGeneratedSplitCounts(repositoryRoot: string, manifest: JsonRecord): Promise<{
  trainingRows: number | null;
  validationRows: number | null;
  generatedExportsMatchRunManifest: boolean | null;
}> {
  try {
    const rawDataset: unknown = JSON.parse(await readFile(resolve(repositoryRoot, "lab1_finetune/data/generated/manifest.json"), "utf8"));
    const dataset = record(
      rawDataset,
      "generated dataset manifest",
    );
    const splitCounts = record(dataset.split_counts, "generated dataset split counts");
    const declaredTrainingRows = requiredNumber(splitCounts.train, "generated training row count");
    const declaredValidationRows = requiredNumber(splitCounts.validation, "generated validation row count");
    const declaredTotal = numberValue(dataset.total_examples);
    if (!Number.isInteger(declaredTrainingRows) || declaredTrainingRows < 0 ||
        !Number.isInteger(declaredValidationRows) || declaredValidationRows < 0 ||
        declaredTotal !== declaredTrainingRows + declaredValidationRows) {
      return { trainingRows: null, validationRows: null, generatedExportsMatchRunManifest: null };
    }
    const [training, validation] = await Promise.all([
      readJsonlSummary(repositoryRoot, "lab1_finetune/data/generated/exports/train_qwen.jsonl"),
      readJsonlSummary(repositoryRoot, "lab1_finetune/data/generated/exports/validation_qwen.jsonl"),
    ]);
    const expectedTrainingHash = stringValue(manifest.train_sha256).toLowerCase();
    const expectedValidationHash = stringValue(manifest.validation_sha256).toLowerCase();
    const hasRunHashes = /^[a-f0-9]{64}$/.test(expectedTrainingHash) && /^[a-f0-9]{64}$/.test(expectedValidationHash);
    return {
      trainingRows: training?.rowCount === declaredTrainingRows ? training.rowCount : null,
      validationRows: validation?.rowCount === declaredValidationRows ? validation.rowCount : null,
      generatedExportsMatchRunManifest: training && validation && hasRunHashes
        ? training.sha256 === expectedTrainingHash && validation.sha256 === expectedValidationHash
        : null,
    };
  } catch {
    return { trainingRows: null, validationRows: null, generatedExportsMatchRunManifest: null };
  }
}

function pairCases(baseCases: JsonRecord[], loraCases: JsonRecord[]): void {
  if (baseCases.length !== loraCases.length || baseCases.some((item, index) => caseId(item) !== caseId(loraCases[index]))) {
    throw new Lab1ArtifactError("Lab 1 evaluation files do not contain the same ordered benchmark cases.");
  }
  if (new Set(baseCases.map(caseId)).size !== baseCases.length) {
    throw new Lab1ArtifactError("Lab 1 evaluation reports contain duplicate case IDs.");
  }
}

async function loadArtifactSet() {
  const root = await resolveArtifactRoot();
  const manifest = record(await readArtifact(root, "runs/qwen3-14b-lora-20260925-040048/run_manifest.json"), "run manifest");
  const trainer = record(await readArtifact(root, "runs/qwen3-14b-lora-20260925-040048/checkpoint-363/trainer_state.json"), "trainer state");
  const bestTrainer = record(await readArtifact(root, "runs/qwen3-14b-lora-20260925-040048/checkpoint-121/trainer_state.json"), "best checkpoint trainer state");
  const base = record(await readArtifact(root, "eval/base.json"), "base evaluation");
  const lora = record(await readArtifact(root, "eval/lora.json"), "LoRA evaluation");
  const comparison = record(await readArtifact(root, "eval/comparison.json"), "evaluation comparison");
  const baseCases = evaluationCases(base, "base");
  const loraCases = evaluationCases(lora, "LoRA");
  pairCases(baseCases, loraCases);
  const declaredCaseCount = requiredNumber(base.total_cases, "benchmark case count");
  if (!Number.isInteger(declaredCaseCount) || baseCases.length !== declaredCaseCount) {
    throw new Lab1ArtifactError("Lab 1 evaluation case count does not match the cases stored in the reports.");
  }

  const baseHash = stringValue(base.benchmark_hash);
  const loraHash = stringValue(lora.benchmark_hash);
  const comparisonHash = stringValue(comparison.benchmark_hash);
  if (!baseHash || baseHash !== loraHash || baseHash !== comparisonHash || base.total_cases !== lora.total_cases) {
    throw new Lab1ArtifactError("Lab 1 evaluation files do not share the same benchmark fingerprint and case count.");
  }
  if (JSON.stringify(base.evaluation_config) !== JSON.stringify(lora.evaluation_config)) {
    throw new Lab1ArtifactError("Lab 1 evaluation files use different evaluation configurations.");
  }

  const bestMetric = requiredNumber(trainer.best_metric, "best validation loss");
  const checkpointMetric = requiredNumber(bestTrainer.best_metric, "best checkpoint validation loss");
  if (Math.abs(bestMetric - checkpointMetric) > 1e-7) {
    throw new Lab1ArtifactError("Lab 1 best checkpoint does not match the trainer state's best validation loss.");
  }

  return {
    root,
    manifest,
    trainer,
    base,
    lora,
    comparison,
    baseCases,
    loraCases,
    benchmark: { caseCount: declaredCaseCount, fingerprint: baseHash },
    bestCheckpoint: {
      epoch: numberValue(bestTrainer.epoch),
      step: numberValue(bestTrainer.global_step),
      validationLoss: checkpointMetric,
    },
  };
}

export async function getLab1Dashboard(): Promise<Lab1Dashboard> {
  const { root, manifest, trainer, base, lora, comparison, baseCases, loraCases, benchmark, bestCheckpoint } = await loadArtifactSet();
  const repositoryRoot = resolve(root, "..", "..");
  const [generatedSplits, goldSeed] = await Promise.all([
    readGeneratedSplitCounts(repositoryRoot, manifest),
    readGoldSeedCounts(repositoryRoot),
  ]);
  const config = record(manifest.config, "run config");
  const trainMetrics = record(manifest.train_metrics, "training summary");
  const logHistory = Array.isArray(trainer.log_history) ? trainer.log_history : [];
  const metricSource = record(comparison.metrics, "comparison metrics");
  const baseMetricSource = record(base.metrics, "base metrics");
  const loraMetricSource = record(lora.metrics, "LoRA metrics");
  const metrics: Lab1MetricComparison[] = metricDefinitions.map(({ key, label, direction }) => {
    const source = record(metricSource[key], `${key} comparison`);
    const baseReport = reportMetric(baseMetricSource[key], `base.${key}`);
    const candidateReport = reportMetric(loraMetricSource[key], `lora.${key}`);
    const comparisonBase = requiredNumber(source.base, `${key}.comparison.base`);
    const comparisonCandidate = requiredNumber(source.candidate, `${key}.comparison.candidate`);
    const comparisonDelta = requiredNumber(source.delta, `${key}.comparison.delta`);
    const comparisonBaseCount = requiredNumber(source.base_count, `${key}.comparison.base_count`);
    const comparisonCandidateCount = requiredNumber(source.candidate_count, `${key}.comparison.candidate_count`);
    if (Math.abs(baseReport.value - comparisonBase) > 1e-7 ||
        Math.abs(candidateReport.value - comparisonCandidate) > 1e-7 ||
        Math.abs(candidateReport.value - baseReport.value - comparisonDelta) > 1e-6 ||
        baseReport.count !== comparisonBaseCount || candidateReport.count !== comparisonCandidateCount) {
      throw new Lab1ArtifactError(`Lab 1 comparison file does not match the Base and LoRA reports (${key}).`);
    }
    const baseValue = baseReport.value;
    const candidateValue = candidateReport.value;
    return {
      key, label, direction, base: baseValue, candidate: candidateValue,
      delta: candidateValue - baseValue, baseCount: baseReport.count, candidateCount: candidateReport.count,
    };
  });

  const globalStep = requiredNumber(trainer.global_step, "training step");
  const maxSteps = requiredNumber(trainer.max_steps, "maximum training steps");
  const epoch = requiredNumber(trainer.epoch, "training epoch");
  const epochs = requiredNumber(config.num_train_epochs, "configured epochs");
  const bestCheckpointPath = stringValue(trainer.best_model_checkpoint);
  const benchmarkCases = benchmark.caseCount;
  const baseSuccessful = requiredNumber(base.successful_cases, "base successful evaluation cases");
  const baseFailed = requiredNumber(base.failed_cases, "base failed evaluation cases");
  const candidateSuccessful = requiredNumber(lora.successful_cases, "LoRA successful evaluation cases");
  const candidateFailed = requiredNumber(lora.failed_cases, "LoRA failed evaluation cases");
  if (baseSuccessful + baseFailed !== benchmarkCases || candidateSuccessful + candidateFailed !== benchmarkCases) {
    throw new Lab1ArtifactError("Lab 1 evaluation success and failure counts do not match the benchmark size.");
  }

  return {
    run: {
      id: "qwen3-14b-lora-20260925-040048",
      status: globalStep >= maxSteps && epoch >= epochs ? "completed" : "incomplete",
      baseModel: stringValue(base.model_name, stringValue(config.model_name, "Base model")),
      candidateModel: stringValue(lora.model_name, "LoRA adapter"),
      method: config.use_lora === true ? "LoRA" : "Full fine-tuning",
      precision: config.bf16 === true ? "BF16" : "Not recorded",
      loraEnabled: config.use_lora === true,
      qloraEnabled: config.use_qlora === true,
      epochs,
      epoch,
      globalStep,
      maxSteps,
      runtimeSeconds: numberValue(trainMetrics.train_runtime),
      trainLoss: numberValue(trainMetrics.train_loss),
      bestEvalLoss: numberValue(trainer.best_metric),
      bestCheckpoint: bestCheckpointPath ? safeFileName(bestCheckpointPath) : null,
      bestCheckpointEpoch: bestCheckpoint.epoch,
      bestCheckpointStep: bestCheckpoint.step,
      maxSequenceLength: numberValue(config.max_seq_length),
      learningRate: numberValue(config.learning_rate),
      scheduler: stringValue(config.lr_scheduler_type) || null,
      warmupRatio: numberValue(config.warmup_ratio),
      perDeviceBatchSize: numberValue(config.per_device_batch_size),
      perDeviceEvalBatchSize: numberValue(config.per_device_eval_batch_size),
      gradientAccumulationSteps: numberValue(config.gradient_accumulation_steps),
      seed: numberValue(config.seed),
      loraRank: numberValue(config.lora_rank),
      loraAlpha: numberValue(config.lora_alpha),
      loraDropout: numberValue(config.lora_dropout),
      targetModules: stringValue(config.lora_target_modules, "Not recorded"),
    },
    inputs: {
      trainFile: safeFileName(config.train_file),
      validationFile: safeFileName(config.validation_file),
      trainFingerprint: stringValue(manifest.train_sha256).slice(0, 12) || null,
      validationFingerprint: stringValue(manifest.validation_sha256).slice(0, 12) || null,
      generatedExportsMatchRunManifest: generatedSplits.generatedExportsMatchRunManifest,
      trainingRows: generatedSplits.trainingRows,
      validationRows: generatedSplits.validationRows,
      goldSeedExamples: goldSeed.examples,
      goldSeedFamilies: goldSeed.families,
      goldSeedTrainRows: goldSeed.trainRows,
      goldSeedValidationRows: goldSeed.validationRows,
      goldSeedTestRows: goldSeed.testRows,
    },
    trainingLoss: safeTrainingPoints(logHistory, "loss"),
    validationLoss: safeTrainingPoints(logHistory, "eval_loss"),
    evaluation: {
      benchmarkCases,
      successfulCases: candidateSuccessful,
      failedCases: candidateFailed,
      method: stringValue(record(lora.evaluation_config, "evaluation configuration").method, "Not recorded"),
      benchmarkFingerprint: benchmark.fingerprint.slice(0, 12),
      baseModel: stringValue(base.model_name, "Base model"),
      candidateModel: stringValue(lora.model_name, "LoRA adapter"),
      metrics,
    },
    cases: baseCases.map((item, index) => caseIndexItem(item, loraCases[index])),
  };
}

export async function getLab1Case(caseIdValue: string): Promise<Lab1CaseDetail> {
  const { baseCases, loraCases } = await loadArtifactSet();
  const index = baseCases.findIndex((item) => caseId(item) === caseIdValue);
  if (index < 0) throw new Lab1ArtifactError("Lab 1 case was not found.", 404);

  const base = baseCases[index];
  const candidate = loraCases[index];
  const gold = caseGold(base);
  const expectedCalls = safeToolCalls(gold.expected_tool_calls);
  return {
    caseId: caseIdValue,
    prompt: casePrompt(base),
    intent: stringValue(gold.intent, "Unknown"),
    scenarioType: stringValue(gold.scenario_type, "Unknown"),
    shouldCallTool: gold.should_call_tool === true,
    shouldAbstain: gold.should_abstain === true,
    expectedToolCalls: expectedCalls,
    base: caseModelResult(base),
    candidate: caseModelResult(candidate),
  };
}
