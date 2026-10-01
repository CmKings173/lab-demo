import { LAB2_ROUTE_STEPS } from "@/lib/lab2-config";
import styles from "./lab2-panel.module.css";

export function Lab2RuntimePath() {
  return <section className={styles.card} aria-labelledby="route-title">
    <div className={styles.sectionHeading}>
      <div><span className={styles.headingIcon} aria-hidden="true">&gt;</span><h2 id="route-title">Configured request path</h2></div>
      <span className={styles.sectionMeta}>LAB2 RUNTIME CONTRACT</span>
    </div>
    <ol className={styles.routeGrid}>
      {LAB2_ROUTE_STEPS.map((step, index) => <li className={styles.routeStep} key={step.label}>
        <span className={styles.routeNumber}>{String(index + 1).padStart(2, "0")}</span>
        <span className={styles.routeLabel}>{step.label}</span>
        <strong>{step.value}</strong>
      </li>)}
    </ol>
    <p className={styles.note}>This is the configured architecture path, not a live execution trace. Tool calls run inside OpenClaw and the private Tool API.</p>
  </section>;
}
