import type { RunSnapshot } from "@/lib/contracts";

export function ProposalPanel({ snapshot, finalState }: { snapshot: RunSnapshot | null; finalState: string | null }) {
  const proposal = snapshot?.result?.proposal;
  const verified = finalState === "complete";
  return <section className="panel proposal-panel" id="proposal" aria-labelledby="proposal-title">
    <div className="panel-header"><div><p className="panel-overline">06 / OUTPUT</p><h2 id="proposal-title">Proposal summary</h2></div><span className="panel-meta">{proposal ? verified ? "VERIFIED" : "UNVERIFIED DRAFT" : finalState ? "NO PROPOSAL" : "PENDING"}</span></div>
    {!proposal ? <div className="proposal-empty"><span className="proposal-icon" aria-hidden="true">◇</span><h3>{finalState ? finalState.replaceAll("_", " ") : "Chưa có proposal"}</h3><p>{snapshot?.error ?? (snapshot?.result?.errors.length ? snapshot.result.errors.join(" · ") : finalState ? "Workflow kết thúc mà không tạo proposal." : "Kết quả sẽ xuất hiện khi workflow trả về proposal.")}</p></div> : <div className="proposal-content">
      <div className="proposal-state"><span>FINAL STATE</span><strong className={verified ? "" : "unverified"}>{snapshot?.final_state?.replaceAll("_", " ")}</strong></div>
      <div className="proposal-figures"><div><strong>{proposal.option_count}</strong><span>Options</span></div><div><strong>{proposal.evidence_count}</strong><span>Evidence</span></div><div><strong>{proposal.selected_configuration_ids.length}</strong><span>Selected</span></div></div>
      <div className="proposal-price"><span>{verified ? "ESTIMATED PRICE" : "PROPOSED PRICE · UNVERIFIED"}</span><strong>{proposal.estimated_price_vnd === null ? "Chưa có giá đầy đủ" : new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(proposal.estimated_price_vnd)}</strong></div>
      {proposal.selected_configuration_ids.length ? <div className="proposal-detail"><h3>Configurations</h3><ul>{proposal.selected_configuration_ids.map((id) => <li className="mono" key={id}>{id}</li>)}</ul></div> : null}
      {proposal.limitations.length ? <div className="proposal-detail"><h3>Limitations</h3><ul>{proposal.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div> : null}
      <p className="proposal-foot">{proposal.sources.length} source(s) trong proposal backend</p>
    </div>}
  </section>;
}
