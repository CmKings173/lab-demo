import type { Lab1Dashboard } from "@/lib/lab1-contracts";
import styles from "./lab1.module.css";

function formatNumber(value: number | null, digits = 4) {
  return value === null ? "Not recorded" : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}

export function TrainingConfig({ run }: { run: Lab1Dashboard["run"] }) {
  return <article className={styles.panelCard}>
    <div className={styles.cardHeading}><div><p className={styles.eyebrow}>TRAINING RUN</p><h2>Model configuration &amp; runtime</h2></div><span className={styles.smallTag}>{run.method}</span></div>
    <dl className={styles.detailsGrid}>
      <div><dt>Base model</dt><dd>{run.baseModel}</dd></div>
      <div><dt>Method / precision</dt><dd>{run.method} · {run.precision}{run.qloraEnabled ? " · QLoRA enabled" : " · QLoRA disabled"}</dd></div>
      <div><dt>Max sequence length</dt><dd>{run.maxSequenceLength ?? "Not recorded"}</dd></div>
      <div><dt>Learning rate</dt><dd>{formatNumber(run.learningRate)}</dd></div>
      <div><dt>Scheduler / warmup</dt><dd>{run.scheduler ?? "Not recorded"} · {run.warmupRatio === null ? "Not recorded" : `${formatNumber(run.warmupRatio * 100, 2)}%`}</dd></div>
      <div><dt>Epochs / optimizer steps</dt><dd>{run.epochs} · {run.globalStep}/{run.maxSteps}</dd></div>
      <div><dt>Batch / accumulation</dt><dd>{run.perDeviceBatchSize ?? "-"} per device · {run.gradientAccumulationSteps ?? "-"} steps</dd></div>
      <div><dt>Evaluation batch</dt><dd>{run.perDeviceEvalBatchSize ?? "Not recorded"}</dd></div>
      <div><dt>LoRA rank / alpha</dt><dd>r={run.loraRank ?? "-"} · α={run.loraAlpha ?? "-"}</dd></div>
      <div><dt>LoRA dropout / seed</dt><dd>{formatNumber(run.loraDropout, 2)} · {run.seed ?? "Not recorded"}</dd></div>
      <div><dt>Target modules</dt><dd className={styles.mono}>{run.targetModules}</dd></div>
      <div><dt>Best checkpoint</dt><dd className={styles.blueText}>{run.bestCheckpoint ?? "Not recorded"} · epoch {run.bestCheckpointEpoch ?? "-"} / step {run.bestCheckpointStep ?? "-"}</dd></div>
    </dl>
    <div className={styles.progressMeta}><span>Recorded progress</span><strong className={styles.mono}>{(run.maxSteps > 0 ? Math.min(100, (run.globalStep / run.maxSteps) * 100) : 0).toFixed(0)}%</strong></div>
    <div className={styles.progressTrack} role="progressbar" aria-label="Recorded training progress" aria-valuenow={run.maxSteps > 0 ? Math.min(100, (run.globalStep / run.maxSteps) * 100) : 0} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${run.maxSteps > 0 ? Math.min(100, (run.globalStep / run.maxSteps) * 100) : 0}%` }} /></div>
    <p className={styles.footnote}>Configuration and progress come from the recorded run manifest and trainer state.</p>
  </article>;
}
