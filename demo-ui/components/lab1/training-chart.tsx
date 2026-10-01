import type { Lab1TrainingPoint } from "@/lib/lab1-contracts";
import styles from "./lab1.module.css";

type TrainingChartProps = {
  title: string;
  note: string;
  points: Lab1TrainingPoint[];
  kind: "train" | "validation";
};

function chartGeometry(points: Lab1TrainingPoint[]) {
  const width = 720;
  const height = 190;
  const inset = 14;
  const values = points.map((point) => point.value);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const range = high - low || 1;
  const coordinates = points.map((point, index) => ({
    x: inset + (points.length <= 1 ? 0 : index / (points.length - 1)) * (width - inset * 2),
    y: height - inset - ((point.value - low) / range) * (height - inset * 2),
  }));
  const line = coordinates.map(({ x, y }, index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const first = coordinates[0];
  const last = coordinates.at(-1);
  const area = first && last ? `${line} L${last.x.toFixed(2)},${(height - inset).toFixed(2)} L${first.x.toFixed(2)},${(height - inset).toFixed(2)} Z` : "";
  return { width, height, inset, line, area, low, high };
}

const numberFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });

export function TrainingChart({ title, note, points, kind }: TrainingChartProps) {
  const chart = points.length ? chartGeometry(points) : null;
  const first = points[0];
  const last = points.at(-1);
  const isTrain = kind === "train";

  return <section className={styles.chartCard} aria-label={title}>
    <div className={styles.chartHeading}>
      <div><h3>{title}</h3><p>{note}</p></div>
      {last ? <strong className={isTrain ? styles.blueText : styles.amberText}>{numberFormat.format(last.value)}</strong> : null}
    </div>
    {chart ? <>
      <div className={styles.chartCanvas}>
        <svg viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={`${title} from step ${first?.step} to step ${last?.step}`}>
          {[0, 1, 2, 3].map((line) => {
            const y = chart.inset + line * (chart.height - chart.inset * 2) / 3;
            return <line key={line} x1={chart.inset} x2={chart.width - chart.inset} y1={y} y2={y} className={styles.chartGrid} />;
          })}
          <path d={chart.area} className={isTrain ? styles.trainArea : styles.validationArea} />
          <path d={chart.line} className={isTrain ? styles.trainLine : styles.validationLine} />
        </svg>
      </div>
      <div className={styles.chartAxis}>
        <span>Step {first?.step} · {numberFormat.format(first?.value ?? 0)}</span>
        <span>{points.length} recorded {isTrain ? "training" : "validation"} values</span>
        <span>Step {last?.step} · {numberFormat.format(last?.value ?? 0)}</span>
      </div>
    </> : <p className={styles.inlineUnavailable}>Loss history is unavailable in this run artifact.</p>}
  </section>;
}
