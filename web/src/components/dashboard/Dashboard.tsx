import { ArrowUpRight, Check, Clock3, MoreHorizontal } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import KpiCard from "./KpiCard";
import QuotaGuard from "@/components/settings/QuotaGuard";

const funnel = [
  { name: "Discovered", value: 1284 }, { name: "Audited", value: 1068 }, { name: "Contact ready", value: 692 },
  { name: "Contacted", value: 318 }, { name: "Replied", value: 84 }, { name: "Won", value: 23 },
];
const breakdown = [
  { name: "No website", value: 31, color: "#c9ff35" }, { name: "Social only", value: 24, color: "#62c5ff" },
  { name: "Redesign / SSL", value: 18, color: "#a4b6ff" }, { name: "Missing analytics", value: 16, color: "#f59e0b" },
  { name: "Established", value: 11, color: "#334155" },
];
const runs = [
  ["Houston × Plumbing", "CRON", "142", "18m ago"], ["Austin × HVAC", "MANUAL", "87", "1h ago"],
  ["Miami × Landscaping", "CRON", "116", "4h ago"], ["Atlanta × Auto Detailing", "CRON", "64", "Yesterday"],
];

export default function Dashboard() {
  return <div className="view-stack">
    <section className="kpi-grid">
      <KpiCard label="Total verified leads" value="1,284" detail="+142 this week" bars={[26, 40, 35, 54, 49, 68, 88]} />
      <KpiCard label="Hot agency pitches" value="318" detail="24.7% of lead pool" accent bars={[20, 34, 31, 48, 62, 59, 78]} />
      <KpiCard label="MX-verified emails" value="692" detail="94% deliverability" bars={[31, 38, 46, 40, 55, 67, 74]} />
      <KpiCard label="Active outreach deals" value="47" detail="11 replied this week" bars={[20, 25, 29, 42, 37, 54, 64]} />
    </section>
    <section className="dashboard-grid">
      <article className="panel chart-panel wide">
        <PanelTitle title="Prospecting conversion" subtitle="Lead velocity across the full pipeline" action="Last 30 days" />
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%"><AreaChart data={funnel} margin={{ top: 12, right: 8, bottom: 0, left: -18 }}>
            <defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#c9ff35" stopOpacity=".35" /><stop offset="1" stopColor="#c9ff35" stopOpacity="0" /></linearGradient></defs>
            <CartesianGrid stroke="#1f2b3a" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#708197", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "#708197", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: "#0d1724", border: "1px solid #243349", borderRadius: 10 }} /><Area type="monotone" dataKey="value" stroke="#c9ff35" strokeWidth={2} fill="url(#area)" />
          </AreaChart></ResponsiveContainer>
        </div>
      </article>
      <article className="panel chart-panel">
        <PanelTitle title="Opportunity mix" subtitle="By primary pitch angle" />
        <div className="donut-layout"><div className="donut">
          <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={breakdown} innerRadius={52} outerRadius={72} paddingAngle={3} dataKey="value">{breakdown.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie></PieChart></ResponsiveContainer>
          <div className="donut-center"><strong>1,284</strong><span>Leads</span></div>
        </div><div className="legend">{breakdown.map((item) => <div key={item.name}><i style={{ background: item.color }} /><span>{item.name}</span><b>{item.value}%</b></div>)}</div></div>
      </article>
      <article className="panel">
        <PanelTitle title="API quota guard" subtitle="Live monthly consumption" action="Manage" />
        <QuotaGuard />
      </article>
      <article className="panel wide">
        <PanelTitle title="Recent automated runs" subtitle="Worker execution activity" action="View all runs" />
        <div className="runs-list">{runs.map((run, index) => <div className="run-row" key={run[0]}>
          <div className="run-icon">{index === 0 ? <Clock3 size={16} /> : <Check size={16} />}</div>
          <div className="run-name"><strong>{run[0]}</strong><span>{run[1]} trigger</span></div>
          <span className={`status-pill ${index === 0 ? "running" : "completed"}`}>{index === 0 ? "Running" : "Completed"}</span>
          <div className="run-metric"><strong>{run[2]}</strong><span>added</span></div><time>{run[3]}</time><MoreHorizontal size={17} />
        </div>)}</div>
      </article>
    </section>
  </div>;
}

function PanelTitle({ title, subtitle, action }: { title: string; subtitle: string; action?: string }) {
  return <div className="panel-title"><div><h2>{title}</h2><p>{subtitle}</p></div>{action && <button>{action}<ArrowUpRight size={14} /></button>}</div>;
}
