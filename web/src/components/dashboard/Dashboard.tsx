import { ArrowUpRight, Check, Clock3, MoreHorizontal } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import KpiCard from "./KpiCard";
import QuotaGuard from "@/components/settings/QuotaGuard";
import type { ApiQuotaRow, BusinessLead, PitchAngle, ScrapeJob, View } from "@/lib/types";

interface DashboardProps {
  leads: BusinessLead[];
  jobs: ScrapeJob[];
  quotas: ApiQuotaRow[];
  isOwner: boolean;
  theme: "dark" | "light";
  onNavigate: (view: View) => void;
}

const DEMO_FUNNEL = [
  { name: "Discovered", value: 1284 },
  { name: "Audited", value: 1068 },
  { name: "Contact ready", value: 692 },
  { name: "Contacted", value: 318 },
  { name: "Replied", value: 84 },
  { name: "Won", value: 23 },
];

const DEMO_BREAKDOWN = [
  { name: "No website", value: 31, color: "#c9ff35" },
  { name: "Social only", value: 24, color: "#62c5ff" },
  { name: "Redesign / SSL", value: 18, color: "#a4b6ff" },
  { name: "Missing analytics", value: 16, color: "#f59e0b" },
  { name: "Established", value: 11, color: "#334155" },
];

const ANGLE_META: Record<PitchAngle, { label: string; color: string }> = {
  NO_WEBSITE: { label: "No website", color: "#c9ff35" },
  SOCIAL_ONLY: { label: "Social only", color: "#62c5ff" },
  REDESIGN_SSL: { label: "Redesign / SSL", color: "#a4b6ff" },
  SEO_ANALYTICS: { label: "Missing analytics", color: "#f59e0b" },
  ESTABLISHED: { label: "Established", color: "#334155" },
};

function formatRelativeTime(iso: string): string {
  const diffMin = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.round(diffHr / 24)}d ago`;
}

export default function Dashboard({
  leads,
  jobs,
  quotas,
  isOwner,
  theme,
  onNavigate,
}: DashboardProps) {
  const isLight = theme === "light";
  const chartStroke = isLight ? "#65a30d" : "#c9ff35";
  const chartGrid = isLight ? "#e2e8f0" : "#1f2b3a";
  const chartTick = isLight ? "#64748b" : "#708197";
  const tooltipStyle = isLight
    ? { background: "#ffffff", border: "1px solid #cbd5e1", borderRadius: 10, color: "#0f172a" }
    : { background: "#0d1724", border: "1px solid #243349", borderRadius: 10 };
  const totalLeads = isOwner ? leads.length : 1284;
  const hotLeads = isOwner ? leads.filter((l) => l.opportunity_score >= 80).length : 318;
  const mxEmails = isOwner ? leads.filter((l) => l.email && l.email_mx_valid).length : 692;
  const withEmail = isOwner ? leads.filter((l) => Boolean(l.email)).length : 736;
  const activeDeals = isOwner
    ? leads.filter((l) => ["CONTACTED", "FOLLOW_UP", "REPLIED", "QUALIFIED", "WON"].includes(l.outreach_status)).length
    : 47;
  const repliedDeals = isOwner
    ? leads.filter((l) => ["REPLIED", "QUALIFIED", "WON"].includes(l.outreach_status)).length
    : 11;

  const hotPct = totalLeads > 0 ? ((hotLeads / totalLeads) * 100).toFixed(1) : "0.0";
  const mxPct = withEmail > 0 ? Math.round((mxEmails / withEmail) * 100) : 0;

  const funnel = isOwner
    ? [
        { name: "Discovered", value: leads.length },
        { name: "Audited", value: leads.filter((l) => Boolean(l.website_status)).length },
        { name: "Contact ready", value: leads.filter((l) => Boolean(l.email || l.phone)).length },
        { name: "Contacted", value: activeDeals },
        { name: "Replied", value: repliedDeals },
        { name: "Won", value: leads.filter((l) => l.outreach_status === "WON").length },
      ]
    : DEMO_FUNNEL;

  const rawBreakdown = isOwner
    ? (Object.keys(ANGLE_META) as PitchAngle[]).map((angle) => {
        const count = leads.filter((l) => l.pitch_angle === angle).length;
        const pct = leads.length > 0 ? Math.round((count / leads.length) * 100) : 0;
        return { name: ANGLE_META[angle].label, value: pct, color: ANGLE_META[angle].color };
      })
    : DEMO_BREAKDOWN;

  const breakdown = rawBreakdown.map((item) => ({
    ...item,
    color:
      isLight && item.color === "#c9ff35"
        ? "#65a30d"
        : isLight && item.color === "#62c5ff"
          ? "#0284c7"
          : isLight && item.color === "#a4b6ff"
            ? "#4f46e5"
            : item.color,
  }));

  const chartBreakdown = breakdown.some((b) => b.value > 0)
    ? breakdown
    : [{ name: "Awaiting first scrape", value: 100, color: isLight ? "#e2e8f0" : "#1e3042" }];

  return (
    <div className="view-stack">
      <section className="kpi-grid">
        <KpiCard
          label="Total verified leads"
          value={totalLeads.toLocaleString()}
          detail={isOwner ? "Live prospectiq.leads pool" : "+142 this week"}
          bars={[26, 40, 35, 54, 49, 68, 88]}
        />
        <KpiCard
          label="Hot agency pitches"
          value={hotLeads.toLocaleString()}
          detail={`${hotPct}% of lead pool`}
          accent
          bars={[20, 34, 31, 48, 62, 59, 78]}
        />
        <KpiCard
          label="MX-verified emails"
          value={mxEmails.toLocaleString()}
          detail={`${mxPct}% deliverability`}
          bars={[31, 38, 46, 40, 55, 67, 74]}
        />
        <KpiCard
          label="Active outreach deals"
          value={activeDeals.toLocaleString()}
          detail={`${repliedDeals} replied / qualified`}
          bars={[20, 25, 29, 42, 37, 54, 64]}
        />
      </section>

      <section className="dashboard-grid">
        <article className="panel chart-panel wide">
          <PanelTitle
            title="Prospecting conversion"
            subtitle="Lead velocity across the full pipeline"
            action="Lead explorer"
            onAction={() => onNavigate("leads")}
          />
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={funnel} margin={{ top: 12, right: 8, bottom: 0, left: -18 }}>
                <defs>
                  <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0" stopColor={chartStroke} stopOpacity=".35" />
                    <stop offset="1" stopColor={chartStroke} stopOpacity="0" />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={chartGrid} vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fill: chartTick, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: chartTick, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={chartStroke}
                  strokeWidth={2}
                  fill="url(#area)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-panel">
          <PanelTitle title="Opportunity mix" subtitle="By primary pitch angle" />
          <div className="donut-layout">
            <div className="donut">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartBreakdown}
                    innerRadius={52}
                    outerRadius={72}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {chartBreakdown.map((item) => (
                      <Cell key={item.name} fill={item.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="donut-center">
                <strong>{totalLeads.toLocaleString()}</strong>
                <span>Leads</span>
              </div>
            </div>
            <div className="legend">
              {breakdown.map((item) => (
                <div key={item.name}>
                  <i style={{ background: item.color }} />
                  <span>{item.name}</span>
                  <b>{item.value}%</b>
                </div>
              ))}
            </div>
          </div>
        </article>

        <article className="panel">
          <PanelTitle
            title="API quota guard"
            subtitle="Live monthly consumption"
            action="Manage"
            onAction={() => onNavigate("settings")}
          />
          <QuotaGuard quotas={quotas} />
        </article>

        <article className="panel wide">
          <PanelTitle
            title="Recent automated runs"
            subtitle="Worker execution activity"
            action="View all runs"
            onAction={() => onNavigate("scraper")}
          />
          {jobs.length === 0 ? (
            <div className="empty-state">
              <strong>No live scrape runs recorded yet</strong>
              Dispatch your first GitHub Action from Auto-Scraper or wait for the 08:00 UTC cron.
            </div>
          ) : (
            <div className="runs-list">
              {jobs.slice(0, 4).map((job) => {
                const targetLabel = `${job.cities[0] ?? "Queue"} × ${job.niches[0] ?? "All"}`;
                const isRunning = job.status === "RUNNING" || job.status === "QUEUED";
                return (
                  <div className="run-row" key={job.id}>
                    <div className="run-icon">
                      {isRunning ? <Clock3 size={16} /> : <Check size={16} />}
                    </div>
                    <div className="run-name">
                      <strong>{targetLabel}</strong>
                      <span>{job.trigger_source} trigger</span>
                    </div>
                    <span className={`status-pill ${job.status.toLowerCase()}`}>{job.status}</span>
                    <div className="run-metric">
                      <strong>{job.leads_inserted}</strong>
                      <span>added</span>
                    </div>
                    <time>{formatRelativeTime(job.started_at)}</time>
                    <MoreHorizontal size={17} />
                  </div>
                );
              })}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}

function PanelTitle({
  title,
  subtitle,
  action,
  onAction,
}: {
  title: string;
  subtitle: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {action && (
        <button onClick={onAction}>
          {action}
          <ArrowUpRight size={14} />
        </button>
      )}
    </div>
  );
}
