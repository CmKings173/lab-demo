import type { ConfigurationSummary, RunSnapshot } from "@/lib/contracts";

function money(value: number | null): string {
  return value === null
    ? "Not available"
    : new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(value);
}

function ConfigurationCard({ item }: { item: ConfigurationSummary }) {
  return <article className="proposal-configuration">
    <div className="proposal-config-heading"><strong>{item.product_name}</strong><span className="mono">{item.configuration_id}</span></div>
    {item.manufacturer ? <p>{item.manufacturer}</p> : null}
    <dl>
      {item.gpu ? <div><dt>GPU</dt><dd>{item.gpu}{item.gpu_count ? ` × ${item.gpu_count}` : ""}</dd></div> : null}
      {item.ram_gb !== null ? <div><dt>RAM</dt><dd>{item.ram_gb} GB</dd></div> : null}
      {item.storage_gb !== null ? <div><dt>Storage</dt><dd>{item.storage_gb} GB</dd></div> : null}
      <div><dt>Estimated</dt><dd>{money(item.estimated_price_vnd)}</dd></div>
    </dl>
    {item.evidence_sources.length ? <div className="proposal-evidence"><span>Evidence sources</span><ul>{item.evidence_sources.map((source, index) => <li key={`${index}-${source}`}><a href={source} target="_blank" rel="noreferrer">{source}</a></li>)}</ul></div> : <p className="proposal-source-empty">No source URL is attached to this configuration summary.</p>}
  </article>;
}

export function ProposalPanel({ snapshot, finalState }: { snapshot: RunSnapshot | null; finalState: string | null }) {
  const proposal = snapshot?.result?.proposal;
  const verified = finalState === "complete";
  return <section className="panel proposal-panel" id="proposal" aria-labelledby="proposal-title">
    <div className="panel-header"><div><p className="panel-overline">06 / OUTPUT</p><h2 id="proposal-title">Proposal summary</h2></div><span className="panel-meta">{proposal ? verified ? "VERIFIED" : "UNVERIFIED DRAFT" : finalState ? "NO PROPOSAL" : "PENDING"}</span></div>
    {!proposal ? <div className="proposal-empty"><span className="proposal-icon" aria-hidden="true">◇</span><h3>{finalState ? finalState.replaceAll("_", " ") : "Chưa có proposal"}</h3><p>{snapshot?.error ?? (snapshot?.result?.errors.length ? snapshot.result.errors.join(" · ") : finalState ? "Workflow kết thúc mà không tạo proposal." : "Kết quả sẽ xuất hiện khi workflow trả về proposal.")}</p></div> : <div className="proposal-content">
      <div className="proposal-state"><span>FINAL STATE</span><strong className={verified ? "" : "unverified"}>{snapshot?.final_state?.replaceAll("_", " ")}</strong></div>
      <div className="proposal-figures"><div><strong>{proposal.option_count}</strong><span>Options</span></div><div><strong>{proposal.evidence_count}</strong><span>Evidence</span></div><div><strong>{proposal.selected_configuration_ids.length}</strong><span>Selected</span></div></div>
      <div className="proposal-price"><span>{verified ? "ESTIMATED PRICE" : "PROPOSED PRICE · UNVERIFIED"}</span><strong>{money(proposal.estimated_price_vnd)}</strong></div>
      {proposal.selected_configurations.length ? <div className="proposal-detail"><h3>Selected configurations</h3><div className="proposal-config-list">{proposal.selected_configurations.map((item) => <ConfigurationCard key={item.configuration_id} item={item} />)}</div></div> : null}
      {proposal.options.length ? <div className="proposal-detail"><h3>Proposal options</h3><div className="proposal-config-list">{proposal.options.map((option) => <div className="proposal-option" key={`${option.name}-${option.configuration.configuration_id}`}><strong>{option.name}</strong><p>{option.rationale}</p><ConfigurationCard item={option.configuration} />{option.limitations.length ? <ul>{option.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : null}</div>)}</div></div> : null}
      {proposal.limitations.length ? <div className="proposal-detail"><h3>Limitations</h3><ul>{proposal.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div> : null}
      {proposal.sources.length ? <div className="proposal-detail"><h3>Evidence / sources</h3><ul>{proposal.sources.map((source, index) => <li key={`${index}-${source}`}><a href={source} target="_blank" rel="noreferrer">{source}</a></li>)}</ul></div> : null}
      <p className="proposal-foot">{proposal.sources.length} source reference(s) from backend</p>
    </div>}
  </section>;
}
