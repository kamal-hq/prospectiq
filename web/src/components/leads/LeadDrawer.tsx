import {
  Activity,
  Check,
  Copy,
  ExternalLink,
  Globe2,
  Lock,
  Mail,
  MapPin,
  Phone,
  RotateCw,
  Smartphone,
  Star,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { BusinessLead, OutreachStatus } from "@/lib/types";

interface LeadDrawerProps {
  lead: BusinessLead | null;
  onClose: () => void;
  onSaveNotes: (id: string, notes: string) => void;
  onStatusChange: (id: string, status: OutreachStatus) => void;
  onToast: (message: string) => void;
}

function emailSourceLabel(status: string): string {
  if (status === "FOUND_JSONLD") return "On-site JSON-LD";
  if (status === "FOUND_SCRAPE") return "On-site Scrape";
  if (status === "FOUND_API") return "Hunter Fallback";
  return status.replace(/_/g, " ");
}

export default function LeadDrawer({
  lead,
  onClose,
  onSaveNotes,
  onStatusChange,
  onToast,
}: LeadDrawerProps) {
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<OutreachStatus>("NEW");

  useEffect(() => {
    if (lead) {
      setNotes(lead.outreach_notes || "");
      setStatus(lead.outreach_status);
    }
  }, [lead]);

  if (!lead) return null;

  const copy = (value: string, label: string) => {
    void navigator.clipboard?.writeText(value);
    onToast(`${label} copied to clipboard`);
  };

  const audit = [
    [Globe2, "Website", lead.website_status.replace(/_/g, " ")],
    [Lock, "SSL / HTTPS", lead.has_ssl ? "Secured" : "Not detected"],
    [Smartphone, "Mobile", lead.is_mobile_friendly ? "Optimized" : "Needs work"],
    [Activity, "Analytics", lead.has_analytics ? "Detected" : "Missing"],
  ] as const;

  const socials = [
    ["Facebook", lead.facebook],
    ["Instagram", lead.instagram],
    ["LinkedIn", lead.linkedin],
    ["X / Twitter", lead.twitter],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]));

  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside className="drawer" onMouseDown={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div>
            <span className="eyebrow">Lead intelligence</span>
            <h2>{lead.business_name}</h2>
            <p>
              <MapPin size={13} />
              {lead.address || lead.city}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close drawer">
            <X size={20} />
          </button>
        </div>

        <div className="lead-hero">
          <div>
            <span>
              <Star size={13} fill="currentColor" />
              {lead.rating !== null ? `${lead.rating} · ` : ""}
              {lead.reviews_count} reviews
            </span>
            <b>
              {lead.city} · {lead.industry}
            </b>
          </div>
          <div className="hero-score">
            <strong>{lead.opportunity_score}</strong>
            <span>/100 · {lead.pitch_tier}</span>
          </div>
        </div>

        <section className="pitch-card">
          <span>Recommended agency pitch · {lead.pitch_angle.replace(/_/g, " ")}</span>
          <h3>Own the local search moment.</h3>
          <p>{lead.pitch_summary || "No pitch summary recorded yet."}</p>
        </section>

        <section className="drawer-section">
          <h3>Digital footprint audit</h3>
          <div className="audit-grid">
            {audit.map(([Icon, label, value]) => (
              <div key={label}>
                <Icon size={16} />
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
            <div>
              <span>CMS platform</span>
              <strong>{lead.cms_platform || "None detected"}</strong>
            </div>
            <div>
              <span>Load time</span>
              <strong>{lead.load_time_ms ? `${lead.load_time_ms} ms` : "Unavailable"}</strong>
            </div>
          </div>
        </section>

        <section className="drawer-section">
          <h3>Verified contact stack</h3>
          <div className="contact-card">
            <Mail size={17} />
            <div>
              <span>Primary email</span>
              <strong>{lead.email || "No email discovered"}</strong>
              {lead.email && (
                <small>
                  {lead.email_mx_valid && <Check size={11} />}{" "}
                  {lead.email_mx_valid ? "MX verified · " : ""}
                  {emailSourceLabel(lead.email_status)}
                </small>
              )}
            </div>
            {lead.email && (
              <button onClick={() => copy(lead.email!, "Email")} aria-label="Copy email">
                <Copy size={15} />
              </button>
            )}
          </div>
          <div className="contact-card">
            <Phone size={17} />
            <div>
              <span>Direct phone</span>
              <strong>{lead.phone || "No phone discovered"}</strong>
            </div>
            {lead.phone && (
              <button onClick={() => copy(lead.phone!, "Phone")} aria-label="Copy phone">
                <Copy size={15} />
              </button>
            )}
          </div>
          {socials.length > 0 && (
            <div className="social-links">
              {socials.map(([label, href]) => (
                <a key={label} href={href} target="_blank" rel="noopener noreferrer">
                  {label} ↗
                </a>
              ))}
            </div>
          )}
        </section>

        <section className="drawer-section">
          <h3>Outreach CRM</h3>
          <div className="crm-fields">
            <select
              value={status}
              onChange={(e) => {
                const next = e.target.value as OutreachStatus;
                setStatus(next);
                onStatusChange(lead.id, next);
              }}
            >
              <option value="NEW">NEW</option>
              <option value="CONTACTED">CONTACTED</option>
              <option value="FOLLOW_UP">FOLLOW UP</option>
              <option value="REPLIED">REPLIED</option>
              <option value="QUALIFIED">QUALIFIED</option>
              <option value="WON">WON</option>
              <option value="DISQUALIFIED">DISQUALIFIED</option>
            </select>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add context, objections, or a follow-up note..."
            />
            <button onClick={() => onSaveNotes(lead.id, notes)}>Save notes</button>
          </div>
        </section>

        <footer className="drawer-footer">
          <button
            disabled={!lead.website_url}
            onClick={() =>
              lead.website_url &&
              window.open(lead.website_url, "_blank", "noopener,noreferrer")
            }
          >
            <ExternalLink size={15} />
            Visit website
          </button>
          <button
            onClick={() => copy(lead.pitch_summary || lead.business_name, "Pitch brief")}
          >
            <Copy size={15} />
            Copy brief
          </button>
          <button
            className="primary-button"
            onClick={() => onToast("Use Auto-Scraper to re-run enrichment for this market")}
          >
            <RotateCw size={15} />
            Re-enrich
          </button>
        </footer>
      </aside>
    </div>
  );
}
