import { ArrowUpRight } from "lucide-react";

interface KpiCardProps {
  label: string;
  value: string;
  detail: string;
  badge?: string;
  accent?: boolean;
  bars: number[];
}

export default function KpiCard({
  label,
  value,
  detail,
  badge = "Live",
  accent = false,
  bars,
}: KpiCardProps) {
  return (
    <article className={`kpi-card ${accent ? "accent" : ""}`}>
      <div className="kpi-head">
        <span>{label}</span>
        <b>
          <ArrowUpRight size={13} />
          {badge}
        </b>
      </div>
      <strong className="kpi-value">{value}</strong>
      <div className="sparkline">
        {bars.map((bar, i) => (
          <i key={i} style={{ height: `${bar}%` }} />
        ))}
      </div>
      <p>{detail}</p>
    </article>
  );
}
