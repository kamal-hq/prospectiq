import { Plus, X } from "lucide-react";
import { useState } from "react";
import QuotaGuard from "./QuotaGuard";

export default function SettingsView() {
  const [tab, setTab] = useState("Aggregator domains");
  const [chips, setChips] = useState(["yelp.com", "angi.com", "thumbtack.com", "homeadvisor.com", "yellowpages.com"]);
  return <div className="view-stack">
    <section><div className="section-heading"><div><span className="eyebrow">Usage controls</span><h2>Monthly API quotas</h2></div><p>Live metering protects your free and starter tiers.</p></div><QuotaGuard large /></section>
    <section className="settings-grid">
      <article className="panel exclusions"><div className="panel-title"><div><h2>Anti-garbage exclusion list</h2><p>Keep low-value records out of your pipeline</p></div></div>
        <div className="settings-tabs">{["Aggregator domains", "Franchises", "Junk email domains"].map((item) => <button className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item}</button>)}</div>
        <div className="chip-cloud">{chips.map((chip) => <span key={chip}>{chip}<X size={13} onClick={() => setChips(chips.filter((x) => x !== chip))} /></span>)}</div>
        <label className="add-exclusion"><input placeholder={`Add ${tab.toLowerCase()}...`} /><button><Plus size={15} />Add exclusion</button></label>
      </article>
      <article className="panel formula"><div className="panel-title"><div><h2>Opportunity score formula</h2><p>Transparent agency-fit weighting</p></div><span className="formula-total mono">100 pts</span></div>
        {([["No owned website", "+35", 35], ["High Google reviews", "+20", 20], ["Phone / email ready", "+20", 20], ["Missing SSL / analytics", "+15", 15], ["Social audience detected", "+10", 10], ["Franchise penalty", "−40", 40]] as const).map((row, i) => <div className="formula-row" key={row[0]}><div><span>{row[0]}</span><strong className={i === 5 ? "negative" : ""}>{row[1]}</strong></div><i><b style={{ width: `${row[2] * 2.3}%` }} /></i></div>)}
      </article>
    </section>
  </div>;
}
