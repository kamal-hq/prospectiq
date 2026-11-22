import { useState } from "react";
import Dashboard from "@/components/dashboard/Dashboard";
import AuthModal from "@/components/layout/AuthModal";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import LeadDrawer from "@/components/leads/LeadDrawer";
import LeadTable from "@/components/leads/LeadTable";
import ScraperView from "@/components/scraper/ScraperView";
import SettingsView from "@/components/settings/SettingsView";
import { leads as initialLeads } from "@/data/mockLeads";
import type { BusinessLead, View } from "@/lib/types";

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [activeLead, setActiveLead] = useState<BusinessLead | null>(null);
  const [leadData, setLeadData] = useState(initialLeads);
  const [toast, setToast] = useState("");
  const showToast = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 2600); };
  const runScrape = () => isAdmin ? setView("scraper") : setAuthOpen(true);

  return <div className={`app-shell ${collapsed ? "is-collapsed" : ""}`}>
    {!isAdmin && <div className="portfolio-banner"><span>Portfolio live preview · Read only</span><b>Built by Muhammad Kamal</b><button onClick={() => setAuthOpen(true)}>Sign in as admin</button></div>}
    <Sidebar view={view} setView={setView} collapsed={collapsed} setCollapsed={setCollapsed} isAdmin={isAdmin} setIsAdmin={setIsAdmin} />
    <div className="app-main">
      <TopBar view={view} onRun={runScrape} isAdmin={isAdmin} onMenu={() => setCollapsed(!collapsed)} />
      <main>
        {view === "dashboard" && <Dashboard />}
        {view === "leads" && <LeadTable leads={leadData} onLead={setActiveLead} onStatus={(id, status) => setLeadData((items) => items.map((lead) => lead.id === id ? { ...lead, outreach_status: status } : lead))} />}
        {view === "scraper" && <ScraperView onToast={showToast} />}
        {view === "settings" && <SettingsView />}
      </main>
    </div>
    <LeadDrawer lead={activeLead} onClose={() => setActiveLead(null)} onToast={showToast} />
    <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} onAdmin={() => { setIsAdmin(true); setAuthOpen(false); showToast("Demo admin mode enabled"); }} />
    {toast && <div className="toast">{toast}</div>}
  </div>;
}
