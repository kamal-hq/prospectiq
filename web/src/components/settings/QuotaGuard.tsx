import type { ApiProvider, ApiQuotaRow } from "@/lib/types";

const PROVIDER_META: Record<ApiProvider, { label: string; color: string }> = {
  serpapi: { label: "SerpApi", color: "var(--quota-lime)" },
  brave: { label: "Brave Search", color: "var(--quota-sky)" },
  hunter: { label: "Hunter.io", color: "var(--quota-indigo)" },
};

function nextMonthResetLabel(): string {
  const now = new Date();
  const nextMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1));
  return nextMonth.toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  });
}

export default function QuotaGuard({
  quotas,
  large = false,
}: {
  quotas: ApiQuotaRow[];
  large?: boolean;
}) {
  const resetDate = nextMonthResetLabel();

  return (
    <div className={large ? "quota-grid" : "quota-list"}>
      {quotas.map((quota) => {
        const meta = PROVIDER_META[quota.provider];
        const pct = quota.monthly_limit > 0 ? Math.min(100, Math.round((quota.calls_used / quota.monthly_limit) * 100)) : 0;
        const remaining = Math.max(0, quota.monthly_limit - quota.calls_used);
        return (
          <div className={large ? "quota-card" : "quota-row"} key={quota.provider}>
            <div className="quota-meta">
              <strong>{meta.label}</strong>
              <span className="mono">
                {quota.calls_used} / {quota.monthly_limit.toLocaleString()}
              </span>
            </div>
            {large && (
              <div className="quota-big mono">
                {pct}
                <small>%</small>
              </div>
            )}
            <div className="progress">
              <i style={{ width: `${pct}%`, background: meta.color }} />
            </div>
            <p>
              {quota.provider === "hunter"
                ? "Free-first protected"
                : large
                  ? `Resets ${resetDate}`
                  : `${remaining.toLocaleString()} credits available`}
            </p>
          </div>
        );
      })}
    </div>
  );
}
