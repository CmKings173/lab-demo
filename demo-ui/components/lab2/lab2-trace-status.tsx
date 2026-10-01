import styles from "./lab2-panel.module.css";

export function Lab2TraceStatus({ reason }: { reason: string }) {
  return <section className={`${styles.card} ${styles.traceCard}`} aria-labelledby="trace-title">
    <div className={styles.sectionHeading}>
      <div><span className={styles.headingIcon} aria-hidden="true">!</span><h2 id="trace-title">Tool execution trace</h2></div>
      <span className={styles.unavailable}><i aria-hidden="true" /> NOT AVAILABLE</span>
    </div>
    <p>{reason}</p>
    <p className={styles.note}>No tool names, timings, product matches, database health, or WeKnora status are inferred from the final answer.</p>
  </section>;
}
