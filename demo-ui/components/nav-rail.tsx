export type LabKey = "lab1" | "lab2" | "lab3";

const labs: { key: LabKey; short: string; label: string }[] = [
  { key: "lab1", short: "L1", label: "Model fine-tuning" },
  { key: "lab2", short: "L2", label: "Agent + RAG" },
  { key: "lab3", short: "L3", label: "Workflow" },
];

export function NavRail({ activeLab, onSelect }: { activeLab: LabKey; onSelect: (lab: LabKey) => void }) {
  return <aside className="app-sidebar">
    <div className="sidebar-top">
      <a className="sidebar-brand" href="#main-content" aria-label="Lab Console home"><span className="brand-mark">LC</span><span><strong>LAB CONSOLE</strong><small>AI ENGINEERING</small></span></a>
      <div className="sidebar-environment"><span>ENVIRONMENT</span><strong>LOCAL · UNVERIFIED</strong></div>
      <nav className="sidebar-nav" aria-label="Labs">
        <p className="sidebar-label">WORKSPACE</p>
        {labs.map((lab) => <button key={lab.key} type="button" className={`sidebar-link ${activeLab === lab.key ? "active" : ""}`} aria-current={activeLab === lab.key ? "page" : undefined} onClick={() => onSelect(lab.key)}><span className="sidebar-short">{lab.short}</span><span>{lab.label}</span></button>)}
      </nav>
    </div>
    <footer className="sidebar-footer">
      <div className="sidebar-runtime"><span>BASE MODEL</span><strong>Qwen3-14B</strong><span>GATEWAY</span><strong className="unverified"><i aria-hidden="true" />UNVERIFIED</strong></div>
      <div className="sidebar-quicklinks"><span>DOCS</span><span className="mono">REPOSITORY</span></div>
    </footer>
  </aside>;
}
