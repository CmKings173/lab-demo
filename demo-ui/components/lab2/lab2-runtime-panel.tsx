import { LAB2_AGENT_ID, LAB2_MODEL_TARGET } from "@/lib/lab2-config";
import type { Lab2RequestState } from "./hooks/use-lab2-chat";
import { Lab2RuntimePath } from "./lab2-runtime-path";
import { Lab2ToolContract } from "./lab2-tool-contract";
import { Lab2TraceStatus } from "./lab2-trace-status";
import styles from "./lab2-panel.module.css";

export function Lab2RuntimePanel({ requestState, traceReason }: {
  requestState: Lab2RequestState;
  traceReason: string;
}) {
  return <aside className={styles.card} aria-label="Lab2 runtime">
    <div className={styles.sectionHeading}><h2>Runtime</h2></div>
    <dl className={styles.runtimeFacts}>
      <dt>Advisor</dt><dd>CNTTShop</dd>
      <dt>Agent</dt><dd className={styles.runtimeValue}>{LAB2_AGENT_ID}</dd>
      <dt>Model</dt><dd className={styles.runtimeValue}>{LAB2_MODEL_TARGET}</dd>
      <dt>Request state</dt><dd className={styles[`turn_${requestState}`]}>{requestState}</dd>
      <dt>Configured data sources</dt><dd>PostgreSQL / WeKnora</dd>
      <Lab2TraceStatus reason={traceReason} />
    </dl>
    <details className={styles.architecture}>
      <summary>Architecture &amp; tools</summary>
      <div className={styles.architectureContent}>
        <Lab2RuntimePath />
        <Lab2ToolContract />
      </div>
    </details>
  </aside>;
}
