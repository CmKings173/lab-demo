import { LAB2_DOMAIN_TOOL_DETAILS } from "@/lib/lab2-config";
import styles from "./lab2-panel.module.css";

export function Lab2ToolContract() {
  return <section className={styles.card} aria-labelledby="tools-title">
    <div className={styles.sectionHeading}>
      <div><span className={styles.headingIcon} aria-hidden="true">6</span><h2 id="tools-title">Lab2 domain tool contract</h2></div>
      <span className={styles.sectionMeta}>SIX TOOL NAMES</span>
    </div>
    <ul className={styles.toolGrid}>
      {LAB2_DOMAIN_TOOL_DETAILS.map((tool, index) => <li className={styles.toolItem} key={tool.name}>
        <span className={styles.toolIndex}>{String(index + 1).padStart(2, "0")}</span>
        <div><strong>{tool.name}</strong><p>{tool.detail}</p></div>
      </li>)}
    </ul>
    <p className={styles.note}>The list reflects the checked-in Lab2 plugin and allowlist. The live Gateway policy must use the same six-tool allowlist.</p>
  </section>;
}
