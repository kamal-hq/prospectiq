import { ArrowUpRight } from "lucide-react";

export default function KpiCard({ label, value, detail, accent = false, bars }: { label: string; value: string; detail: string; accent?: boolean; bars: number[] }) {
  return <article className={`kpi-card ${accent ? "accent" : ""}`}>
    <div className="kpi-head"><span>{label}</span><b><ArrowUpRight size={13} />12.4%</b></div>
    <strong className="kpi-value">{value}</strong>
    <div className="sparkline">{bars.map((bar, i) => <i key={i} style={{ height: `${bar}%` }} />)}</div>
    <p>{detail}</p>
  </article>;
}
