"use client";

import { useMemo, useState } from "react";

import type {
  Lab1CaseDetail,
  Lab1CaseIndexItem,
  Lab1CaseMetricKey,
  Lab1Dashboard,
  Lab1ToolCall,
} from "@/lib/lab1-contracts";
import { caseMetricPresentation } from "@/lib/lab1-metrics";
import { useLab1Case } from "./hooks/use-lab1-case";
import styles from "./lab1.module.css";

type CaseExplorerProps = {
  dashboard: Lab1Dashboard;
  selectedCaseId: string;
  onSelectCase: (caseId: string) => void;
};

type CaseFilter = "all" | "tool-required" | "no-tool-required" | "candidate-mismatch";

const caseFilterOptions: Array<{ value: CaseFilter; label: string }> = [
  { value: "all", label: "All cases" },
  { value: "tool-required", label: "Gold requires a tool" },
  { value: "no-tool-required", label: "Gold expects no tool" },
  { value: "candidate-mismatch", label: "LoRA missed tool decision" },
];

function isCaseFilter(value: string): value is CaseFilter {
  return caseFilterOptions.some((option) => option.value === value);
}

const metricRows: Array<{ key: Lab1CaseMetricKey; label: string }> = [
  { key: "tool_call_required_accuracy", label: "Tool call required" },
  { key: "tool_name_accuracy", label: "Tool name" },
  { key: "tool_argument_accuracy", label: "Tool arguments" },
  { key: "tool_call_sequence_accuracy", label: "Tool sequence" },
  { key: "abstention_accuracy", label: "Abstention" },
  { key: "missing_tool_call_rate", label: "Missing tool call" },
  { key: "unexpected_tool_call_rate", label: "Unexpected tool call" },
];

function matchesFilter(item: Lab1CaseIndexItem, filter: CaseFilter) {
  if (filter === "tool-required") return item.shouldCallTool;
  if (filter === "no-tool-required") return !item.shouldCallTool;
  if (filter === "candidate-mismatch") return item.candidateToolCallRequiredMatch === false;
  return true;
}

function formatToolCalls(calls: Lab1ToolCall[]) {
  return calls.length ? JSON.stringify(calls, null, 2) : "No tool call";
}

function ResultBadge({ value, metricKey }: { value: boolean | null; metricKey: Lab1CaseMetricKey }) {
  const presentation = caseMetricPresentation(metricKey, value);
  const state = presentation.tone === "muted" ? styles.badgeMuted
    : presentation.tone === "pass" ? styles.badgePass : styles.badgeMiss;
  return <span className={`${styles.resultBadge} ${state}`}>{presentation.label}</span>;
}

function ModelResult({ title, model, result }: { title: string; model: string; result: Lab1CaseDetail["base"] }) {
  return <section className={styles.modelResult}>
    <div className={styles.modelResultHeading}><div><p className={styles.eyebrow}>{title}</p><h4>{model}</h4></div>{result.hasError ? <span className={styles.errorTag}>Output error</span> : null}</div>
    <div className={styles.answerText}>{result.assistantText || "No assistant response stored for this case."}</div>
    <p className={styles.resultSubheading}>Predicted tool calls</p>
    <pre className={styles.codeBlock}>{formatToolCalls(result.toolCalls)}</pre>
    <div className={styles.caseMetricGrid}>
      {metricRows.map(({ key, label }) => <div className={styles.caseMetric} key={key}>
        <span>{label}</span><ResultBadge metricKey={key} value={result.metrics[key]} />
      </div>)}
    </div>
  </section>;
}

export function CaseExplorer({ dashboard, selectedCaseId, onSelectCase }: CaseExplorerProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<CaseFilter>("all");
  const caseRequest = useLab1Case(selectedCaseId);
  const detail = caseRequest.status === "loaded" ? caseRequest.detail : null;
  const loading = caseRequest.status === "loading";
  const error = caseRequest.status === "failed" ? caseRequest.error : null;

  const visibleCases = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return dashboard.cases.filter((item) => matchesFilter(item, filter) && (
      !needle || `${item.caseId} ${item.intent} ${item.scenarioType} ${item.promptPreview}`.toLocaleLowerCase().includes(needle)
    ));
  }, [dashboard.cases, filter, query]);

  const selectedIndex = dashboard.cases.find((item) => item.caseId === selectedCaseId);
  const expected = detail?.expectedToolCalls ?? [];

  return <section className={styles.panelCard} aria-labelledby="lab1-case-title">
    <div className={styles.cardHeading}>
      <div><p className={styles.eyebrow}>CASE REVIEW</p><h2 id="lab1-case-title">Benchmark case explorer</h2></div>
      <span className={styles.smallTag}>{dashboard.cases.length} paired cases</span>
    </div>
    <div className={styles.caseExplorer}>
      <aside className={styles.caseSidebar} aria-label="Benchmark cases">
        <label className={styles.searchLabel} htmlFor="lab1-case-search">Find a case</label>
        <input id="lab1-case-search" className={styles.searchInput} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="ID, scenario or prompt" />
        <label className={styles.searchLabel} htmlFor="lab1-case-filter">Filter cases</label>
        <select id="lab1-case-filter" className={styles.filterSelect} value={filter} onChange={(event) => {
          const nextFilter = event.currentTarget.value;
          if (isCaseFilter(nextFilter)) setFilter(nextFilter);
        }}>
          {caseFilterOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <div className={styles.caseList}>
          {visibleCases.map((item) => <button key={item.caseId} type="button" className={`${styles.caseListItem} ${selectedCaseId === item.caseId ? styles.caseSelected : ""}`} onClick={() => onSelectCase(item.caseId)} aria-current={selectedCaseId === item.caseId ? "true" : undefined}>
            <span className={styles.caseListTop}><strong className={styles.mono}>{item.caseId}</strong><ResultBadge metricKey="tool_call_required_accuracy" value={item.candidateToolCallRequiredMatch} /></span>
            <span className={styles.caseScenario}>{item.scenarioType.replaceAll("_", " ")}</span>
            <span className={styles.casePromptPreview}>{item.promptPreview || "Prompt unavailable"}</span>
          </button>)}
          {visibleCases.length === 0 ? <p className={styles.emptyList}>No cases match these filters.</p> : null}
        </div>
        <p className={styles.caseCount}>{visibleCases.length} of {dashboard.cases.length} shown</p>
      </aside>

      <div className={styles.caseDetail}>
        {loading ? <p className={styles.inlineUnavailable} role="status">Loading the selected case…</p> : null}
        {error ? <p className={styles.inlineError} role="alert">{error}</p> : null}
        {!loading && !error && detail ? <>
          <div className={styles.caseDetailHeading}>
            <div><p className={styles.eyebrow}>{detail.intent.replaceAll("_", " ")} · {detail.scenarioType.replaceAll("_", " ")}</p><h3 className={styles.mono}>{detail.caseId}</h3></div>
            <div className={styles.caseBadges}>
              <span className={detail.shouldCallTool ? styles.requiredTag : styles.smallTag}>{detail.shouldCallTool ? "Tool expected" : "No tool expected"}</span>
              {detail.shouldAbstain ? <span className={styles.warningTag}>Abstention expected</span> : null}
            </div>
          </div>
          <div className={styles.promptBlock}><span className={styles.resultSubheading}>Benchmark conversation</span><p>{detail.prompt || "Input messages unavailable in the evaluation artifact."}</p></div>
          <div className={styles.expectedBlock}><div><span className={styles.resultSubheading}>Expected tool calls</span><span className={styles.expectedCount}>{expected.length}</span></div><pre className={styles.codeBlock}>{formatToolCalls(expected)}</pre></div>
          <div className={styles.modelResultGrid}>
            <ModelResult title="BASE MODEL" model={dashboard.evaluation.baseModel} result={detail.base} />
            <ModelResult title="LORA CANDIDATE" model={dashboard.evaluation.candidateModel} result={detail.candidate} />
          </div>
        </> : null}
        {!loading && !error && !detail && selectedIndex ? <p className={styles.inlineUnavailable} role="status">Select a case to load its model outputs.</p> : null}
      </div>
    </div>
  </section>;
}
