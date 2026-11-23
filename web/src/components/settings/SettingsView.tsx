import { Plus, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import QuotaGuard from "./QuotaGuard";
import type { ApiQuotaRow, ExclusionPatternType, ExclusionRule } from "@/lib/types";

const TABS: { label: string; type: ExclusionPatternType }[] = [
  { label: "Aggregator domains", type: "DOMAIN" },
  { label: "Franchises", type: "FRANCHISE" },
  { label: "Junk email domains", type: "EMAIL_DOMAIN" },
];

interface SettingsViewProps {
  isOwner: boolean;
  quotas: ApiQuotaRow[];
  exclusions: ExclusionRule[];
  onAddExclusion: (type: ExclusionPatternType, value: string) => void;
  onDeleteExclusion: (id: string) => void;
  onRequireAuth: () => void;
}

export default function SettingsView({
  isOwner,
  quotas,
  exclusions,
  onAddExclusion,
  onDeleteExclusion,
  onRequireAuth,
}: SettingsViewProps) {
  const [activeTab, setActiveTab] = useState<ExclusionPatternType>("DOMAIN");
  const [inputValue, setInputValue] = useState("");

  const activeLabel = TABS.find((t) => t.type === activeTab)?.label ?? "Aggregator domains";
  const visibleRules = exclusions.filter((rule) => rule.pattern_type === activeTab);

  const handleAdd = (e: FormEvent) => {
    e.preventDefault();
    if (!isOwner) {
      onRequireAuth();
      return;
    }
    const cleaned = inputValue.trim().toLowerCase();
    if (!cleaned) return;
    onAddExclusion(activeTab, cleaned);
    setInputValue("");
  };

  return (
    <div className="view-stack">
      <section>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Usage controls</span>
            <h2>Monthly API quotas</h2>
          </div>
          <p>Atomic database metering protects your 100% free tiers.</p>
        </div>
        <QuotaGuard quotas={quotas} large />
      </section>

      <section className="settings-grid">
        <article className="panel exclusions">
          <div className="panel-title">
            <div>
              <h2>Anti-garbage exclusion list</h2>
              <p>Keep directories, chains, and junk domains out of your pipeline</p>
            </div>
          </div>
          <div className="settings-tabs">
            {TABS.map((item) => (
              <button
                className={activeTab === item.type ? "active" : ""}
                onClick={() => setActiveTab(item.type)}
                key={item.type}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="chip-cloud">
            {visibleRules.map((rule) => (
              <span key={rule.id}>
                {rule.pattern_value}
                <X
                  size={13}
                  onClick={() => (isOwner ? onDeleteExclusion(rule.id) : onRequireAuth())}
                />
              </span>
            ))}
          </div>
          <form className="add-exclusion" onSubmit={handleAdd}>
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={`Add ${activeLabel.toLowerCase()}...`}
            />
            <button type="submit">
              <Plus size={15} />
              Add exclusion
            </button>
          </form>
        </article>

        <article className="panel formula">
          <div className="panel-title">
            <div>
              <h2>Opportunity score formula</h2>
              <p>Transparent deterministic agency-fit weighting</p>
            </div>
            <span className="formula-total mono">100 pts</span>
          </div>
          {(
            [
              ["No owned website", "+35", 35],
              ["High Google reviews", "+20", 20],
              ["Phone / email ready", "+20", 20],
              ["Missing SSL / analytics", "+15", 15],
              ["Social audience detected", "+10", 10],
              ["Franchise penalty", "−40", 40],
            ] as const
          ).map((row, i) => (
            <div className="formula-row" key={row[0]}>
              <div>
                <span>{row[0]}</span>
                <strong className={i === 5 ? "negative" : ""}>{row[1]}</strong>
              </div>
              <i>
                <b style={{ width: `${row[2] * 2.3}%` }} />
              </i>
            </div>
          ))}
        </article>
      </section>
    </div>
  );
}
