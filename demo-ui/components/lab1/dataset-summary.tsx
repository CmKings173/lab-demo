import type { Lab1Dashboard } from "@/lib/lab1-contracts";
import styles from "./lab1.module.css";

function Count({ label, value }: { label: string; value: number | null }) {
  return <div><dt>{label}</dt><dd>{value?.toLocaleString("en-US") ?? "Not recorded"}</dd></div>;
}

export function DatasetSummary({ inputs }: { inputs: Lab1Dashboard["inputs"] }) {
  return <article className={styles.panelCard}>
    <div className={styles.cardHeading}><div><p className={styles.eyebrow}>RUN INPUTS</p><h2>Training data provenance</h2></div><span className={styles.smallTag}>Manifest recorded</span></div>
    <div className={styles.inputFiles}>
      <div><span className={styles.fileGlyph} aria-hidden="true">TR</span><span><strong>Training export</strong><code>{inputs.trainFile}</code></span></div>
      <div><span className={`${styles.fileGlyph} ${styles.fileGlyphAmber}`} aria-hidden="true">VA</span><span><strong>Validation export</strong><code>{inputs.validationFile}</code></span></div>
    </div>
    <div className={styles.datasetGroup}>
      <h3>Gold / curated seed</h3>
      <dl className={styles.datasetCounts} aria-label="Gold seed dataset counts">
        <Count label="Examples" value={inputs.goldSeedExamples} />
        <Count label="Families" value={inputs.goldSeedFamilies} />
        <Count label="Train split" value={inputs.goldSeedTrainRows} />
        <Count label="Validation split" value={inputs.goldSeedValidationRows} />
        <Count label="Test split" value={inputs.goldSeedTestRows} />
      </dl>
    </div>
    <div className={styles.datasetGroup}>
      <h3>Generated training exports</h3>
      <dl className={styles.datasetCounts} aria-label="Generated training export counts">
        <Count label="Training records" value={inputs.trainingRows} />
        <Count label="Validation records" value={inputs.validationRows} />
      </dl>
    </div>
    <dl className={styles.fingerprintList}>
      <div><dt>Run train SHA-256</dt><dd className={styles.mono}>{inputs.trainFingerprint ?? "Not recorded"}</dd></div>
      <div><dt>Run validation SHA-256</dt><dd className={styles.mono}>{inputs.validationFingerprint ?? "Not recorded"}</dd></div>
    </dl>
    <p className={`${styles.footnote} ${inputs.generatedExportsMatchRunManifest === false ? styles.integrityWarning : ""}`}>
      {inputs.generatedExportsMatchRunManifest === true
        ? "Local generated export bytes match both run-manifest SHA-256 values. "
        : inputs.generatedExportsMatchRunManifest === false
          ? "Local export rows match the dataset manifest, but one or more file hashes differ from the training run manifest. Counts describe the current local exports, not proof of identical training bytes. "
          : "Run-manifest hash comparison is unavailable. "}
      Gold counts and splits come from the curated seed manifest; token-length estimates are omitted.
    </p>
  </article>;
}
