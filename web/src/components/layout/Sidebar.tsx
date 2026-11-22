import { BarChart3, Bot, ChevronLeft, Command, Radar, Settings2, UserRound } from "lucide-react";
import type { View } from "@/lib/types";

const items: { id: View; label: string; icon: typeof Command; badge?: string }[] = [
  { id: "dashboard", label: "Command Center", icon: Command },
  { id: "leads", label: "Lead Explorer", icon: BarChart3, badge: "7 hot" },
  { id: "scraper", label: "Auto-Scraper & Queue", icon: Bot, badge: "Live" },
  { id: "settings", label: "Quota & Settings", icon: Settings2 },
];

export default function Sidebar({ view, setView, collapsed, setCollapsed, isAdmin, setIsAdmin }: {
  view: View; setView: (view: View) => void; collapsed: boolean; setCollapsed: (value: boolean) => void;
  isAdmin: boolean; setIsAdmin: (value: boolean) => void;
}) {
  return <aside className={`sidebar ${collapsed ? "sidebar-collapsed" : ""}`}>
    <div className="brand">
      <div className="brand-mark"><Radar size={19} /></div>
      {!collapsed && <><span>ProspectIQ</span><b>v3.0</b></>}
    </div>
    <nav>
      <span className="nav-label">{collapsed ? "•••" : "Workspace"}</span>
      {items.map((item) => <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} onClick={() => setView(item.id)}>
        <item.icon size={18} />
        {!collapsed && <><span>{item.label}</span>{item.badge && <em className={item.badge === "Live" ? "live" : ""}>{item.badge}</em>}</>}
      </button>)}
    </nav>
    <div className="sidebar-bottom">
      {!collapsed && <div className="worker-card">
        <div className="worker-title"><span className="status-dot" /> Worker online</div>
        <p>Next auto-scrape</p><strong>Daily · 08:00 UTC</strong>
      </div>}
      <button className="profile-button" onClick={() => setIsAdmin(!isAdmin)}>
        <div className="avatar"><UserRound size={16} /></div>
        {!collapsed && <div><strong>{isAdmin ? "Admin mode" : "Portfolio mode"}</strong><span>{isAdmin ? "Full access" : "Read only"}</span></div>}
      </button>
      <button className="collapse-button" onClick={() => setCollapsed(!collapsed)}><ChevronLeft size={16} /><span>{!collapsed && "Collapse"}</span></button>
    </div>
  </aside>;
}
