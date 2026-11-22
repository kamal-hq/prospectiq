import { Check, ChevronDown, CirclePlus, ExternalLink, Play, X } from "lucide-react";
import { useState } from "react";

const queue = [["Houston, TX", "Plumbing", "Page 3 · 30 found", "18m ago"], ["Austin, TX", "HVAC", "Page 2 · 20 found", "1h ago"], ["Miami, FL", "Landscaping", "Page 4 · 40 found", "4h ago"], ["Atlanta, GA", "Auto Detailing", "Page 2 · 20 found", "Yesterday"]];
const jobs = [["JOB-84D2", "CRON", "RUNNING", "Houston × Plumbing", "142 / 87 / 31 / 42", "06:18"], ["JOB-83FE", "MANUAL_UI", "COMPLETED", "Austin × HVAC", "126 / 82 / 39 / 34", "12:44"], ["JOB-82AC", "CRON", "PARTIAL", "Miami × Landscaping", "183 / 116 / 58 / 51", "18:09"]];

export default function ScraperView({ onToast, autoRun = false }: { onToast: (message: string) => void; autoRun?: boolean }) {
  const [cities, setCities] = useState(["Houston, TX", "Austin, TX"]);
  const [niches, setNiches] = useState(["Plumbing", "HVAC"]);
  const [max, setMax] = useState(15);
  const [running, setRunning] = useState(autoRun);
  const dispatch = () => { setRunning(true); onToast("GitHub Action dispatched successfully"); window.setTimeout(() => setRunning(false), 3500); };
  return <div className="view-stack">
    <section className="scrape-grid">
      <article className="panel launcher">
        <div className="panel-title"><div><h2>Launch on-demand scrape</h2><p>Dispatch a targeted discovery run</p></div><span className="signal">Worker ready</span></div>
        <label className="field-label">Cities</label><div className="tag-input">{cities.map((city) => <span key={city}>{city}<X size={12} onClick={() => setCities(cities.filter((x) => x !== city))} /></span>)}<button onClick={() => setCities([...cities, "Dallas, TX"])}>Add city</button></div>
        <label className="field-label">Service niches</label><div className="tag-input">{niches.map((niche) => <span key={niche}>{niche}<X size={12} onClick={() => setNiches(niches.filter((x) => x !== niche))} /></span>)}<button onClick={() => setNiches([...niches, "Roofing"])}>Add niche</button></div>
        <div className="range-head"><label>Max results per query</label><strong className="mono">{max}</strong></div><input type="range" min="5" max="20" value={max} onChange={(e) => setMax(Number(e.target.value))} />
        <div className="estimator"><div><span>Estimated cost</span><strong>4 SerpApi credits</strong></div><p>Hunter fallback only · ~8 min runtime</p></div>
        <button className="dispatch-button" disabled={running} onClick={dispatch}><Play size={16} fill="currentColor" />{running ? "Action running..." : "Dispatch GitHub Action"}</button>
      </article>
      <article className="panel queue-card"><div className="panel-title"><div><h2>Automated target queue</h2><p>Daily 08:00 UTC schedule</p></div><button><CirclePlus size={15} />Add target</button></div>
        <div className="queue-table"><div className="queue-head"><span>Target</span><span>Depth</span><span>Last run</span><span>Active</span></div>{queue.map((row, i) => <div className="queue-row" key={row[0]}><div><strong>{row[0]}</strong><span>{row[1]}</span></div><span>{row[2]}</span><time>{row[3]}</time><button className={`toggle ${i === 3 ? "" : "on"}`}><i /></button></div>)}</div>
      </article>
    </section>
    <article className="panel jobs-card"><div className="panel-title"><div><h2>Scrape job execution history</h2><p>Latest worker runs and enrichment yield</p></div><button>All history<ChevronDown size={14} /></button></div>
      <div className="jobs-table"><div className="jobs-head"><span>Job ID</span><span>Trigger</span><span>Status</span><span>Targets</span><span>Found / inserted / dupes / email</span><span>Duration</span><span /></div>{jobs.map((job) => <div className="job-row" key={job[0]}><strong className="mono">{job[0]}</strong><span>{job[1]}</span><span className={`status-pill ${job[2].toLowerCase()}`}>{job[2] === "COMPLETED" && <Check size={11} />}{job[2]}</span><span>{job[3]}</span><span className="mono">{job[4]}</span><time className="mono">{job[5]}</time><button><ExternalLink size={14} /></button></div>)}</div>
    </article>
  </div>;
}
