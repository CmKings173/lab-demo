import type { Lab1Dashboard } from "@/lib/lab1-contracts";
import styles from "./lab1.module.css";

function formatNumber(value: number | null, digits = 4) {
  return value === null ? "-" : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return "Not recorded";
  const wholeSeconds = Math.round(seconds);
  return `${Math.floor(wholeSeconds / 60)}m ${wholeSeconds % 60}s`;
}

function StatCard({ label, value, detail, tone = "default" }: {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "blue" | "green";
}) {
  const valueClass = tone === "blue" ? styles.blueText : tone === "green" ? styles.greenText : "";
  return <article className={styles.statCard}><span>{label}</span><strong className={valueClass}>{value}</strong><small>{detail}</small></article>;
}

export function RunSummary({ dashboard }: { dashboard: Lab1Dashboard }) {
  const { run, evaluation } = dashboard;
  return <section className={styles.statsGrid} aria-label="Run summary">
    <StatCard label="Training progress" value={`${run.globalStep} / ${run.maxSteps}`} detail={`${formatNumber(run.epoch, 2)} of ${run.epochs} epochs`} tone="blue" />
    <StatCard label="Benchmark cases" value={`${evaluation.successfulCases} / ${evaluation.benchmarkCases}`} detail={`${evaluation.failedCases} failed in the recorded LoRA evaluation`} tone="green" />
    <StatCard label="Best checkpoint" value={run.bestCheckpoint ?? "Not recorded"} detail={`Epoch ${run.bestCheckpointEpoch ?? "-"} / step ${run.bestCheckpointStep ?? "-"}; validation loss ${formatNumber(run.bestEvalLoss)}`} />
    <StatCard label="Trainer summary loss" value={formatNumber(run.trainLoss)} detail={`Manifest value · runtime ${formatDuration(run.runtimeSeconds)}`} />
  </section>;
}
