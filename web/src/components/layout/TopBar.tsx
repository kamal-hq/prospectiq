import { LockKeyhole, Menu, Plus, Search } from "lucide-react";
import type { View } from "@/lib/types";

const labels: Record<View, { eyebrow: string; title: string }> = {
  dashboard: { eyebrow: "Overview", title: "Command Center" },
  leads: { eyebrow: "Intelligence", title: "Lead Explorer" },
  scraper: { eyebrow: "Automation", title: "Auto-Scraper" },
  settings: { eyebrow: "Workspace", title: "Quota & Settings" },
};

export default function TopBar({ view, onRun, isAdmin, onMenu }: { view: View; onRun: () => void; isAdmin: boolean; onMenu: () => void }) {
  return <header className="topbar">
    <button className="mobile-menu" onClick={onMenu}><Menu size={20} /></button>
    <div className="title-block"><span>{labels[view].eyebrow}</span><h1>{labels[view].title}</h1></div>
    <div className="top-actions">
      <label className="global-search"><Search size={17} /><input placeholder="Search leads, cities, domains..." /><kbd>⌘ K</kbd></label>
      <button className="primary-button" onClick={onRun}>{isAdmin ? <Plus size={17} /> : <LockKeyhole size={15} />} Run scrape</button>
    </div>
  </header>;
}
