import { Activity, Check, ChevronDown, Globe2, Lock, Mail, MoreHorizontal, Phone, Search, Smartphone, Star } from "lucide-react";
import { useMemo, useState } from "react";
import type { BusinessLead } from "@/lib/types";

const filters = ["All leads", "Hot: No website", "Social only", "Redesign / SSL", "MX-verified email", "Phone ready"];
const angleLabel: Record<BusinessLead["pitch_angle"], string> = { NO_WEBSITE: "No website", SOCIAL_ONLY: "Social only", REDESIGN_SSL: "Redesign / SSL", SEO_ANALYTICS: "SEO / Analytics", ESTABLISHED: "Established" };

export default function LeadTable({ leads, onLead, onStatus }: { leads: BusinessLead[]; onLead: (lead: BusinessLead) => void; onStatus: (id: string, status: BusinessLead["outreach_status"]) => void }) {
  const [activeFilter, setActiveFilter] = useState(filters[0]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [sortDesc, setSortDesc] = useState(true);
  const visible = useMemo(() => leads.filter((lead) => {
    const matches = `${lead.business_name} ${lead.city} ${lead.industry}`.toLowerCase().includes(query.toLowerCase());
    if (activeFilter === "Hot: No website") return matches && lead.pitch_angle === "NO_WEBSITE";
    if (activeFilter === "Social only") return matches && lead.pitch_angle === "SOCIAL_ONLY";
    if (activeFilter === "Redesign / SSL") return matches && lead.pitch_angle === "REDESIGN_SSL";
    if (activeFilter === "MX-verified email") return matches && lead.email_mx_valid;
    return matches;
  }).sort((a, b) => sortDesc ? b.opportunity_score - a.opportunity_score : a.opportunity_score - b.opportunity_score), [leads, activeFilter, query, sortDesc]);
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);

  return <div className="view-stack">
    <div className="filter-pills">{filters.map((filter) => <button className={activeFilter === filter ? "active" : ""} key={filter} onClick={() => setActiveFilter(filter)}>{filter}</button>)}</div>
    <div className="panel table-panel">
      <div className="table-tools">
        <label><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search businesses..." /></label>
        {["All cities", "All industries", "Score: Any", "Outreach: All"].map((text) => <button key={text}>{text}<ChevronDown size={14} /></button>)}
        <button className="export-button">Export CSV</button>
      </div>
      <div className="table-scroll"><table><thead><tr>
        <th><input type="checkbox" checked={selected.length === visible.length && !!visible.length} onChange={() => setSelected(selected.length === visible.length ? [] : visible.map((lead) => lead.id))} /></th>
        <th>Business</th><th onClick={() => setSortDesc(!sortDesc)} className="sortable">Score <ChevronDown size={12} /></th><th>Pitch angle</th><th>Digital health</th><th>Contacts</th><th>Outreach stage</th><th />
      </tr></thead><tbody>{visible.map((lead) => <tr key={lead.id} onClick={() => onLead(lead)}>
        <td onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={selected.includes(lead.id)} onChange={() => toggle(lead.id)} /></td>
        <td><div className="business-cell"><strong>{lead.business_name}</strong><span>{lead.city} · {lead.industry}</span><small><Star size={11} fill="currentColor" /> {lead.rating} <i>({lead.reviews_count})</i></small></div></td>
        <td><span className={`score ${lead.opportunity_score >= 80 ? "hot" : "warm"}`}>{lead.opportunity_score}</span></td>
        <td><span className={`angle angle-${lead.pitch_angle.toLowerCase()}`}>{angleLabel[lead.pitch_angle]}</span></td>
        <td><div className="health-icons"><Globe2 className={lead.website_status !== "NO_WEBSITE" ? "good" : "bad"} /><Lock className={lead.has_ssl ? "good" : ""} /><Smartphone className={lead.is_mobile_friendly ? "good" : ""} /><Activity className={lead.has_analytics ? "good" : ""} />{lead.cms_platform && <b>{lead.cms_platform}</b>}</div></td>
        <td><div className="contact-cell">{lead.email ? <span><Mail size={13} />{lead.email}{lead.email_mx_valid && <Check size={12} className="verified" />}</span> : <span className="muted">No email found</span>}<span><Phone size={13} />{lead.phone}</span></div></td>
        <td onClick={(e) => e.stopPropagation()}><select value={lead.outreach_status} onChange={(e) => onStatus(lead.id, e.target.value as BusinessLead["outreach_status"])}><option value="NEW">New</option><option value="CONTACTED">Contacted</option><option value="FOLLOW_UP">Follow-up</option><option value="REPLIED">Replied</option><option value="QUALIFIED">Qualified</option><option value="WON">Won</option><option value="DISQUALIFIED">Disqualified</option></select></td>
        <td><MoreHorizontal size={16} /></td>
      </tr>)}</tbody></table></div>
      <div className="table-footer"><span>Showing {visible.length} of 1,284 leads</span><div><button>Previous</button><b>1</b><button>2</button><button>3</button><button>Next</button></div></div>
    </div>
    {!!selected.length && <div className="bulk-bar"><strong>{selected.length} selected</strong><i /><button>Export CSV</button><button>Set outreach status</button><button className="danger">Disqualify</button></div>}
  </div>;
}
