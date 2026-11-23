import {
  Activity,
  Check,
  ChevronDown,
  Globe2,
  Lock,
  Mail,
  MoreHorizontal,
  Phone,
  Search,
  Smartphone,
  Star,
} from "lucide-react";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { BusinessLead, OutreachStatus } from "@/lib/types";

const filters = [
  "All leads",
  "Hot: No website",
  "Social only",
  "Redesign / SSL",
  "MX-verified email",
  "Phone ready",
];

const angleLabel: Record<BusinessLead["pitch_angle"], string> = {
  NO_WEBSITE: "No website",
  SOCIAL_ONLY: "Social only",
  REDESIGN_SSL: "Redesign / SSL",
  SEO_ANALYTICS: "SEO / Analytics",
  ESTABLISHED: "Established",
};

const PAGE_SIZE = 15;

interface LeadTableProps {
  leads: BusinessLead[];
  globalQuery: string;
  onLead: (lead: BusinessLead) => void;
  onStatus: (id: string, status: OutreachStatus) => void;
  onBulkStatus: (ids: string[], status: OutreachStatus) => void;
  onExport: (rows: BusinessLead[]) => void;
}

export default function LeadTable({
  leads,
  globalQuery,
  onLead,
  onStatus,
  onBulkStatus,
  onExport,
}: LeadTableProps) {
  const [activeFilter, setActiveFilter] = useState(filters[0]);
  const [query, setQuery] = useState("");
  const [cityFilter, setCityFilter] = useState("ALL");
  const [industryFilter, setIndustryFilter] = useState("ALL");
  const [minScore, setMinScore] = useState(0);
  const [outreachFilter, setOutreachFilter] = useState("ALL");
  const [selected, setSelected] = useState<string[]>([]);
  const [sortDesc, setSortDesc] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (globalQuery) setQuery(globalQuery);
  }, [globalQuery]);

  const cities = useMemo(
    () => Array.from(new Set(leads.map((l) => l.city))).sort(),
    [leads],
  );
  const industries = useMemo(
    () => Array.from(new Set(leads.map((l) => l.industry))).sort(),
    [leads],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return leads
      .filter((lead) => {
        const haystack = `${lead.business_name} ${lead.city} ${lead.industry} ${lead.website_url ?? ""} ${lead.email ?? ""}`.toLowerCase();
        if (q && !haystack.includes(q)) return false;
        if (cityFilter !== "ALL" && lead.city !== cityFilter) return false;
        if (industryFilter !== "ALL" && lead.industry !== industryFilter) return false;
        if (lead.opportunity_score < minScore) return false;
        if (outreachFilter !== "ALL" && lead.outreach_status !== outreachFilter) return false;

        if (activeFilter === "Hot: No website") return lead.pitch_angle === "NO_WEBSITE";
        if (activeFilter === "Social only") return lead.pitch_angle === "SOCIAL_ONLY";
        if (activeFilter === "Redesign / SSL") return lead.pitch_angle === "REDESIGN_SSL";
        if (activeFilter === "MX-verified email") return Boolean(lead.email && lead.email_mx_valid);
        if (activeFilter === "Phone ready") return Boolean(lead.phone);
        return true;
      })
      .sort((a, b) =>
        sortDesc
          ? b.opportunity_score - a.opportunity_score
          : a.opportunity_score - b.opportunity_score,
      );
  }, [leads, activeFilter, query, cityFilter, industryFilter, minScore, outreachFilter, sortDesc]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = visible.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );

  const selectedLeads = visible.filter((l) => selected.includes(l.id));

  return (
    <div className="view-stack">
      <div className="filter-pills">
        {filters.map((filter) => (
          <button
            className={activeFilter === filter ? "active" : ""}
            key={filter}
            onClick={() => {
              setActiveFilter(filter);
              setPage(1);
            }}
          >
            {filter}
          </button>
        ))}
      </div>

      <div className="panel table-panel">
        <div className="table-tools">
          <label>
            <Search size={16} />
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Search businesses..."
            />
          </label>
          <select
            value={cityFilter}
            onChange={(e) => {
              setCityFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="ALL">All cities</option>
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            value={industryFilter}
            onChange={(e) => {
              setIndustryFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="ALL">All industries</option>
            {industries.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </select>
          <select
            value={minScore}
            onChange={(e) => {
              setMinScore(Number(e.target.value));
              setPage(1);
            }}
          >
            <option value={0}>Score: Any</option>
            <option value={80}>Score: 80+ (Hot)</option>
            <option value={50}>Score: 50+ (Warm+)</option>
          </select>
          <select
            value={outreachFilter}
            onChange={(e) => {
              setOutreachFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="ALL">Outreach: All</option>
            <option value="NEW">New</option>
            <option value="CONTACTED">Contacted</option>
            <option value="FOLLOW_UP">Follow-up</option>
            <option value="REPLIED">Replied</option>
            <option value="QUALIFIED">Qualified</option>
            <option value="WON">Won</option>
            <option value="DISQUALIFIED">Disqualified</option>
          </select>
          <button
            className="export-button"
            onClick={() => onExport(visible)}
            disabled={visible.length === 0}
          >
            Export CSV
          </button>
        </div>

        {pageItems.length === 0 ? (
          <div className="empty-state">
            <strong>No matching leads</strong>
            Adjust your filters or dispatch a live scrape from Auto-Scraper to populate{" "}
            <code>prospectiq.leads</code>.
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={selected.length === pageItems.length && pageItems.length > 0}
                      onChange={() =>
                        setSelected(
                          selected.length === pageItems.length
                            ? []
                            : pageItems.map((lead) => lead.id),
                        )
                      }
                    />
                  </th>
                  <th>Business</th>
                  <th onClick={() => setSortDesc(!sortDesc)} className="sortable">
                    Score <ChevronDown size={12} />
                  </th>
                  <th>Pitch angle</th>
                  <th>Digital health</th>
                  <th>Contacts</th>
                  <th>Outreach stage</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pageItems.map((lead) => {
                  const tierClass =
                    lead.opportunity_score >= 80
                      ? "hot"
                      : lead.opportunity_score >= 50
                        ? "warm"
                        : "cold";
                  return (
                    <tr key={lead.id} onClick={() => onLead(lead)}>
                      <td onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selected.includes(lead.id)}
                          onChange={() => toggle(lead.id)}
                        />
                      </td>
                      <td>
                        <div className="business-cell">
                          <strong>{lead.business_name}</strong>
                          <span>
                            {lead.city} · {lead.industry}
                          </span>
                          {lead.rating !== null && (
                            <small>
                              <Star size={11} fill="currentColor" /> {lead.rating}{" "}
                              <i>({lead.reviews_count})</i>
                            </small>
                          )}
                        </div>
                      </td>
                      <td>
                        <span
                          className={`score ${tierClass}`}
                          style={{ "--score": lead.opportunity_score } as CSSProperties}
                        >
                          {lead.opportunity_score}
                        </span>
                      </td>
                      <td>
                        <span className={`angle angle-${lead.pitch_angle.toLowerCase()}`}>
                          {angleLabel[lead.pitch_angle]}
                        </span>
                      </td>
                      <td>
                        <div className="health-icons">
                          <Globe2
                            className={
                              lead.website_status === "LIVE" ||
                              lead.website_status === "WAF_PROTECTED"
                                ? "good"
                                : "bad"
                            }
                          />
                          <Lock className={lead.has_ssl ? "good" : ""} />
                          <Smartphone className={lead.is_mobile_friendly ? "good" : ""} />
                          <Activity className={lead.has_analytics ? "good" : ""} />
                          {lead.cms_platform && <b>{lead.cms_platform}</b>}
                        </div>
                      </td>
                      <td>
                        <div className="contact-cell">
                          {lead.email ? (
                            <span>
                              <Mail size={13} />
                              {lead.email}
                              {lead.email_mx_valid && <Check size={12} className="verified" />}
                            </span>
                          ) : (
                            <span className="muted">No email found</span>
                          )}
                          <span>
                            <Phone size={13} />
                            {lead.phone || "No phone"}
                          </span>
                        </div>
                      </td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <select
                          value={lead.outreach_status}
                          onChange={(e) =>
                            onStatus(lead.id, e.target.value as OutreachStatus)
                          }
                        >
                          <option value="NEW">New</option>
                          <option value="CONTACTED">Contacted</option>
                          <option value="FOLLOW_UP">Follow-up</option>
                          <option value="REPLIED">Replied</option>
                          <option value="QUALIFIED">Qualified</option>
                          <option value="WON">Won</option>
                          <option value="DISQUALIFIED">Disqualified</option>
                        </select>
                      </td>
                      <td>
                        <MoreHorizontal size={16} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="table-footer">
          <span>
            Showing {pageItems.length} of {visible.length} matching leads ({leads.length} total)
          </span>
          <div>
            <button disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>
              Previous
            </button>
            <b>{safePage}</b>
            <button disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>
              Next
            </button>
          </div>
        </div>
      </div>

      {selected.length > 0 && (
        <div className="bulk-bar">
          <strong>{selected.length} selected</strong>
          <i />
          <button onClick={() => onExport(selectedLeads)}>Export CSV</button>
          <button
            onClick={() => {
              onBulkStatus(selected, "CONTACTED");
              setSelected([]);
            }}
          >
            Mark Contacted
          </button>
          <button
            className="danger"
            onClick={() => {
              onBulkStatus(selected, "DISQUALIFIED");
              setSelected([]);
            }}
          >
            Disqualify
          </button>
        </div>
      )}
    </div>
  );
}
