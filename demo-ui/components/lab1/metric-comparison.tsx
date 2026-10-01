import type { Lab1MetricComparison } from "@/lib/lab1-contracts";
import { formatPercentagePointDelta } from "@/lib/lab1-metrics";
import styles from "./lab1.module.css";

type MetricComparisonProps = {
  metrics: Lab1MetricComparison[];
  baseModel: string;
  candidateModel: string;
};

const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });

function deltaTone(metric: Lab1MetricComparison) {
  const improvement = metric.direction === "higher" ? metric.delta : -metric.delta;
  return improvement > 0 ? styles.positive : improvement < 0 ? styles.negative : styles.neutral;
}

function sampleCount(value: number, count: number) {
  return `${percent.format(value)} · ${count} cases`;
}

export function MetricComparison({ metrics, baseModel, candidateModel }: MetricComparisonProps) {
  return <section className={styles.panelCard} aria-labelledby="lab1-evaluation-title">
    <div className={styles.cardHeading}>
      <div><p className={styles.eyebrow}>BENCHMARK</p><h2 id="lab1-evaluation-title">Base vs LoRA evaluation</h2></div>
      <span className={styles.smallTag}>Paired case metrics</span>
    </div>
    <div className={styles.tableScroll}>
      <table className={styles.metricTable}>
        <thead><tr>
          <th scope="col">Metric</th>
          <th scope="col">{baseModel}</th>
          <th scope="col">{candidateModel}</th>
          <th scope="col">Δ candidate - base (pp)</th>
        </tr></thead>
        <tbody>{metrics.map((metric) => <tr key={metric.key}>
          <th scope="row">{metric.label}<span className={styles.metricDirection}>{metric.direction === "higher" ? "Higher is better" : "Lower is better"}</span></th>
          <td>{sampleCount(metric.base, metric.baseCount)}</td>
          <td className={styles.candidateValue}>{sampleCount(metric.candidate, metric.candidateCount)}</td>
          <td><span className={`${styles.deltaPill} ${deltaTone(metric)}`}>
            {formatPercentagePointDelta(metric.delta)}
          </span></td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className={styles.footnote}>Each metric uses its recorded case count. There is no combined score; tool arguments and sequence use smaller subsets than the full benchmark.</p>
  </section>;
}
