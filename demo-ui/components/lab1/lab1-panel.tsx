"use client";

import { useState } from "react";

import { CaseExplorer } from "./case-explorer";
import { DatasetSummary } from "./dataset-summary";
import { MetricComparison } from "./metric-comparison";
import { RunSummary } from "./run-summary";
import { TrainingChart } from "./training-chart";
import { TrainingConfig } from "./training-config";
import { useLab1Dashboard } from "./hooks/use-lab1-dashboard";
import styles from "./lab1.module.css";

function LoadingState() {
  return <div className={styles.stateCard} role="status"><span className={styles.loadingMark} aria-hidden="true" />Loading Lab 1 artifacts.</div>;
}

export function Lab1Panel() {
  const { dashboard, loading, error, reload } = useLab1Dashboard();
  const [preferredCaseId, setPreferredCaseId] = useState("");

  if (loading && !dashboard) return <section className={styles.lab1}><LoadingState /></section>;
  if (!dashboard) return <section className={styles.lab1}>
    <header className={styles.pageHeader}>
      <div><p className={styles.eyebrow}>LAB 1 / MODEL</p><h1>Fine-tuning &amp; evaluation</h1><p>Training run and paired Base/LoRA benchmark results.</p></div>
    </header>
    <section className={styles.errorState} role="alert">
      <span className={styles.errorMark} aria-hidden="true">!</span>
      <div><h2>Lab 1 artifacts are unavailable</h2><p>{error ?? "The saved run and evaluation files could not be loaded."}</p><p className={styles.errorHint}>Restore the named generated artifact, then reload this panel.</p>
        <button type="button" className={styles.retryButton} onClick={reload}>Reload artifacts</button>
      </div>
    </section>
  </section>;

  const { run, inputs, evaluation } = dashboard;
  const selectedCaseId = dashboard.cases.some((item) => item.caseId === preferredCaseId)
    ? preferredCaseId
    : dashboard.cases[0]?.caseId ?? "";

  return <section className={styles.lab1} aria-labelledby="lab1-title">
    <header className={styles.pageHeader}>
      <div><p className={styles.eyebrow}>LAB 1 / MODEL</p><h1 id="lab1-title">Fine-tuning &amp; evaluation</h1><p>Recorded training run and paired Base/LoRA benchmark results.</p></div>
      <div className={styles.headerStatus}>
        <span className={`${styles.statusDot} ${run.status === "completed" ? styles.statusComplete : styles.statusPending}`} />
        <span><strong>{run.status === "completed" ? "Run completed" : "Run incomplete"}</strong><small className={styles.mono}>{run.id}</small></span>
        <button type="button" className={styles.headerReload} disabled={loading} onClick={reload}>
          {loading ? "Loading…" : "Reload"}
        </button>
      </div>
    </header>

    {error ? <div className={styles.staleNotice} role="status"><span>The latest artifact reload failed. Showing the last successfully loaded snapshot: {error}</span><button type="button" disabled={loading} onClick={reload}>Try again</button></div> : null}

    <RunSummary dashboard={dashboard} />

    <section className={styles.overviewGrid} aria-label="Training run details">
      <TrainingConfig run={run} />
      <DatasetSummary inputs={inputs} />
    </section>

    <section className={styles.chartSection} aria-label="Training curves">
      <TrainingChart title="Training loss" note="Per-step loss values recorded by the trainer" points={dashboard.trainingLoss} kind="train" />
      <TrainingChart title="Validation loss" note="Epoch evaluation checkpoints" points={dashboard.validationLoss} kind="validation" />
    </section>

    <MetricComparison metrics={evaluation.metrics} baseModel={evaluation.baseModel} candidateModel={evaluation.candidateModel} />

    <section className={styles.evaluationFoot}>
      <span><strong>{evaluation.method}</strong></span>
      <span>{evaluation.successfulCases} successful · {evaluation.failedCases} failed</span>
      <span className={styles.mono}>Benchmark {evaluation.benchmarkFingerprint}</span>
    </section>

    <CaseExplorer dashboard={dashboard} selectedCaseId={selectedCaseId} onSelectCase={setPreferredCaseId} />
  </section>;
}
