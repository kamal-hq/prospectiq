import { Activity, Check, Copy, ExternalLink, Globe2, Lock, Mail, MapPin, Phone, RotateCw, Smartphone, Star, X } from "lucide-react";
import { useState } from "react";
import type { BusinessLead } from "@/lib/types";

export default function LeadDrawer({ lead, onClose, onToast }: { lead: BusinessLead | null; onClose: () => void; onToast: (message: string) => void }) {
  const [notes, setNotes] = useState("");
  if (!lead) return null;
  const copy = (value: string, label: string) => { navigator.clipboard?.writeText(value); onToast(`${label} copied to clipboard`); };
  const audit = [
    [Globe2, "Website", lead.website_status.replace("_", " ")], [Lock, "SSL / HTTPS", lead.has_ssl ? "Secured" : "Not detected"],
    [Smartphone, "Mobile", lead.is_mobile_friendly ? "Optimized" : "Needs work"], [Activity, "Analytics", lead.has_analytics ? "Detected" : "Missing"],
  ] as const;
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="drawer" onMouseDown={(e) => e.stopPropagation()}>
    <div className="drawer-head"><div><span className="eyebrow">Lead intelligence</span><h2>{lead.business_name}</h2><p><MapPin size={13} />{lead.address}</p></div><button onClick={onClose}><X size={20} /></button></div>
    <div className="lead-hero"><div><span><Star size={13} fill="currentColor" />{lead.rating} · {lead.reviews_count} reviews</span><b>{lead.city} · {lead.industry}</b></div><div className="hero-score"><strong>{lead.opportunity_score}</strong><span>/100 · {lead.pitch_tier}</span></div></div>
    <section className="pitch-card"><span>Recommended agency pitch</span><h3>Own the local search moment.</h3><p>{lead.pitch_summary}</p></section>
    <section className="drawer-section"><h3>Digital footprint audit</h3><div className="audit-grid">{audit.map(([Icon, label, value]) => <div key={label}><Icon size={16} /><span>{label}</span><strong>{value}</strong></div>)}<div><span>CMS platform</span><strong>{lead.cms_platform || "None detected"}</strong></div><div><span>Load time</span><strong>{lead.load_time_ms ? `${lead.load_time_ms} ms` : "Unavailable"}</strong></div></div></section>
    <section className="drawer-section"><h3>Verified contact stack</h3>
      <div className="contact-card"><Mail size={17} /><div><span>Primary email</span><strong>{lead.email || "No email discovered"}</strong>{lead.email_mx_valid && <small><Check size={11} /> MX verified · Hunter fallback</small>}</div>{lead.email && <button onClick={() => copy(lead.email!, "Email")}><Copy size={15} /></button>}</div>
      <div className="contact-card"><Phone size={17} /><div><span>Direct phone</span><strong>{lead.phone}</strong></div><button onClick={() => copy(lead.phone, "Phone")}><Copy size={15} /></button></div>
    </section>
    <section className="drawer-section"><h3>Outreach CRM</h3><div className="crm-fields"><select defaultValue={lead.outreach_status}><option>NEW</option><option>CONTACTED</option><option>REPLIED</option><option>QUALIFIED</option><option>WON</option></select><textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Add context, objections, or a follow-up note..." /><button onClick={() => onToast("Agency notes saved")}>Save notes</button></div></section>
    <footer className="drawer-footer"><button disabled={!lead.website_url}><ExternalLink size={15} />Visit website</button><button onClick={() => copy(lead.pitch_summary, "Pitch brief")}><Copy size={15} />Copy brief</button><button className="primary-button" onClick={() => onToast("Lead queued for re-enrichment")}><RotateCw size={15} />Re-enrich</button></footer>
  </aside></div>;
}
