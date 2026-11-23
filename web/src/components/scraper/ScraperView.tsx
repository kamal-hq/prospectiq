import { Check, CirclePlus, ExternalLink, LockKeyhole, Play, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import type { ScrapeJob, TargetQueueItem } from "@/lib/types";

interface ScraperViewProps {
  isOwner: boolean;
  queue: TargetQueueItem[];
  jobs: ScrapeJob[];
  onDispatch: (payload: { cities: string[]; niches: string[]; max_results: number }) => Promise<void>;
  onToggleTarget: (id: string, enabled: boolean) => void;
  onAddTarget: (city: string, industry: string) => void;
  onRequireAuth: () => void;
}

function formatDuration(startedAt: string, finishedAt: string | null): string {
  const startMs = new Date(startedAt).getTime();
  const endMs = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const totalSec = Math.max(0, Math.round((endMs - startMs) / 1000));
  const mins = String(Math.floor(totalSec / 60)).padStart(2, "0");
  const secs = String(totalSec % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function formatLastRun(iso: string | null): string {
  if (!iso) return "Never";
  const diffMin = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.round(diffHr / 24)}d ago`;
}

export default function ScraperView({
  isOwner,
  queue,
  jobs,
  onDispatch,
  onToggleTarget,
  onAddTarget,
  onRequireAuth,
}: ScraperViewProps) {
  const [cities, setCities] = useState(["Houston, TX", "Austin, TX"]);
  const [cityInput, setCityInput] = useState("");
  const [niches, setNiches] = useState(["Plumbing", "HVAC"]);
  const [nicheInput, setNicheInput] = useState("");
  const [maxResults, setMaxResults] = useState(10);
  const [dispatching, setDispatching] = useState(false);

  const [addingTarget, setAddingTarget] = useState(false);
  const [newCity, setNewCity] = useState("");
  const [newIndustry, setNewIndustry] = useState("");

  const addCity = () => {
    const val = cityInput.trim();
    if (val && !cities.includes(val)) setCities([...cities, val]);
    setCityInput("");
  };

  const addNiche = () => {
    const val = nicheInput.trim();
    if (val && !niches.includes(val)) setNiches([...niches, val]);
    setNicheInput("");
  };

  const handleDispatch = async () => {
    if (!isOwner) {
      onRequireAuth();
      return;
    }
    if (!cities.length || !niches.length) return;
    setDispatching(true);
    try {
      await onDispatch({ cities, niches, max_results: maxResults });
    } finally {
      setDispatching(false);
    }
  };

  const handleAddTargetSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!isOwner) {
      onRequireAuth();
      return;
    }
    if (!newCity.trim() || !newIndustry.trim()) return;
    onAddTarget(newCity.trim(), newIndustry.trim());
    setNewCity("");
    setNewIndustry("");
    setAddingTarget(false);
  };

  const estCredits = cities.length * niches.length;

  return (
    <div className="view-stack">
      <section className="scrape-grid">
        <article className="panel launcher">
          <div className="panel-title">
            <div>
              <h2>Launch on-demand scrape</h2>
              <p>Dispatch a targeted GitHub Actions discovery run</p>
            </div>
            <span className="signal">{isOwner ? "Worker ready" : "Owner only"}</span>
          </div>

          <label className="field-label">Cities</label>
          <div className="tag-input">
            {cities.map((city) => (
              <span key={city}>
                {city}
                <X size={12} onClick={() => setCities(cities.filter((x) => x !== city))} />
              </span>
            ))}
            <input
              value={cityInput}
              onChange={(e) => setCityInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCity();
                }
              }}
              placeholder="e.g. Dallas, TX"
            />
            <button type="button" onClick={addCity}>
              Add
            </button>
          </div>

          <label className="field-label">Service niches</label>
          <div className="tag-input">
            {niches.map((niche) => (
              <span key={niche}>
                {niche}
                <X size={12} onClick={() => setNiches(niches.filter((x) => x !== niche))} />
              </span>
            ))}
            <input
              value={nicheInput}
              onChange={(e) => setNicheInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addNiche();
                }
              }}
              placeholder="e.g. Roofing"
            />
            <button type="button" onClick={addNiche}>
              Add
            </button>
          </div>

          <div className="range-head">
            <label>Max results per query</label>
            <strong className="mono">{maxResults}</strong>
          </div>
          <input
            type="range"
            min="5"
            max="20"
            value={maxResults}
            onChange={(e) => setMaxResults(Number(e.target.value))}
          />

          <div className="estimator">
            <div>
              <span>Estimated cost</span>
              <strong>
                {estCredits} SerpApi {estCredits === 1 ? "credit" : "credits"}
              </strong>
            </div>
            <p>Free-first email waterfall · Hunter.io fallback only</p>
          </div>

          <button
            className="dispatch-button"
            disabled={dispatching || estCredits === 0}
            onClick={handleDispatch}
          >
            {isOwner ? <Play size={16} fill="currentColor" /> : <LockKeyhole size={15} />}
            {dispatching
              ? "Dispatching GitHub Action..."
              : isOwner
                ? "Dispatch GitHub Action"
                : "Sign in as Owner to dispatch"}
          </button>
        </article>

        <article className="panel queue-card">
          <div className="panel-title">
            <div>
              <h2>Automated target queue</h2>
              <p>Daily 08:00 UTC schedule (top 2 enabled targets/run)</p>
            </div>
            <button onClick={() => (isOwner ? setAddingTarget(!addingTarget) : onRequireAuth())}>
              <CirclePlus size={15} />
              Add target
            </button>
          </div>

          {addingTarget && (
            <form className="inline-target-form" onSubmit={handleAddTargetSubmit}>
              <input
                value={newCity}
                onChange={(e) => setNewCity(e.target.value)}
                placeholder="City (e.g. Phoenix, AZ)"
                required
              />
              <input
                value={newIndustry}
                onChange={(e) => setNewIndustry(e.target.value)}
                placeholder="Industry (e.g. Roofing)"
                required
              />
              <button type="submit">Save</button>
            </form>
          )}

          <div className="queue-table">
            <div className="queue-head">
              <span>Target</span>
              <span>Depth</span>
              <span>Last run</span>
              <span>Active</span>
            </div>
            {queue.map((row) => {
              const pageNum = Math.floor(row.next_page_offset / 20) + 1;
              return (
                <div className="queue-row" key={row.id}>
                  <div>
                    <strong>{row.city}</strong>
                    <span>{row.industry}</span>
                  </div>
                  <span>
                    Page {pageNum} · {row.total_leads_found} found
                  </span>
                  <time>{formatLastRun(row.last_scraped_at)}</time>
                  <button
                    className={`toggle ${row.enabled ? "on" : ""}`}
                    onClick={() =>
                      isOwner ? onToggleTarget(row.id, !row.enabled) : onRequireAuth()
                    }
                    aria-label={`Toggle ${row.city} ${row.industry}`}
                  >
                    <i />
                  </button>
                </div>
              );
            })}
          </div>
        </article>
      </section>

      <article className="panel jobs-card">
        <div className="panel-title">
          <div>
            <h2>Scrape job execution history</h2>
            <p>Latest worker runs and enrichment yield (Realtime enabled)</p>
          </div>
        </div>
        {jobs.length === 0 ? (
          <div className="empty-state">
            <strong>No scrape jobs yet</strong>
            Dispatch a manual run above or trigger the workflow in GitHub Actions.
          </div>
        ) : (
          <div className="jobs-table">
            <div className="jobs-head">
              <span>Job ID</span>
              <span>Trigger</span>
              <span>Status</span>
              <span>Targets</span>
              <span>Found / inserted / dupes / email</span>
              <span>Duration</span>
              <span />
            </div>
            {jobs.map((job) => (
              <div className="job-row" key={job.id}>
                <strong className="mono">{job.id.slice(0, 8).toUpperCase()}</strong>
                <span>{job.trigger_source}</span>
                <span className={`status-pill ${job.status.toLowerCase()}`}>
                  {job.status === "COMPLETED" && <Check size={11} />}
                  {job.status}
                </span>
                <span>
                  {(job.cities || []).join(", ") || "Queue"} ×{" "}
                  {(job.niches || []).join(", ") || "All"}
                </span>
                <span className="mono">
                  {job.leads_discovered} / {job.leads_inserted} / {job.leads_skipped_dup} /{" "}
                  {job.emails_found}
                </span>
                <time className="mono">{formatDuration(job.started_at, job.finished_at)}</time>
                <button
                  disabled={!job.github_run_url}
                  onClick={() =>
                    job.github_run_url &&
                    window.open(job.github_run_url, "_blank", "noopener,noreferrer")
                  }
                  title="Open GitHub Actions run logs"
                >
                  <ExternalLink size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </article>
    </div>
  );
}
