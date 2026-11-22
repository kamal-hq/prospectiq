const quotas = [
  { name: "SerpApi", value: 42, max: 250, color: "#c9ff35" },
  { name: "Brave Search", value: 18, max: 1000, color: "#62c5ff" },
  { name: "Hunter.io", value: 11, max: 50, color: "#a4b6ff" },
];

export default function QuotaGuard({ large = false }: { large?: boolean }) {
  return <div className={large ? "quota-grid" : "quota-list"}>
    {quotas.map((quota) => <div className={large ? "quota-card" : "quota-row"} key={quota.name}>
      <div className="quota-meta"><strong>{quota.name}</strong><span className="mono">{quota.value} / {quota.max}</span></div>
      {large && <div className="quota-big mono">{Math.round(quota.value / quota.max * 100)}<small>%</small></div>}
      <div className="progress"><i style={{ width: `${quota.value / quota.max * 100}%`, background: quota.color }} /></div>
      <p>{quota.name === "Hunter.io" ? "Free-first protected" : large ? "Resets Nov 01, 2025" : `${quota.max - quota.value} credits available`}</p>
    </div>)}
  </div>;
}
