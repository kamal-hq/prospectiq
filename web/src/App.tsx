import type { Session } from "@supabase/supabase-js";
import { useCallback, useEffect, useState } from "react";
import Dashboard from "@/components/dashboard/Dashboard";
import AuthModal from "@/components/layout/AuthModal";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import LeadDrawer from "@/components/leads/LeadDrawer";
import LeadTable from "@/components/leads/LeadTable";
import ScraperView from "@/components/scraper/ScraperView";
import SettingsView from "@/components/settings/SettingsView";
import { leads as staticDummyLeads } from "@/data/mockLeads";
import { mockExclusions, mockJobs, mockQueue, mockQuotas } from "@/data/mockWorkspace";
import {
  addExclusionRule,
  addTargetQueueItem,
  bulkUpdateOutreachStatus,
  deleteExclusionRule,
  exportLeadsToCsv,
  loadWorkspaceSnapshot,
  subscribeToWorkspaceRealtime,
  toggleTargetQueueEnabled,
  triggerRemoteScrape,
  updateLeadNotes,
  updateLeadOutreachStatus,
} from "@/lib/prospectiqApi";
import { getSupabaseClient, isSupabaseConfigured } from "@/lib/supabase";
import type {
  ApiQuotaRow,
  BusinessLead,
  ExclusionPatternType,
  ExclusionRule,
  OutreachStatus,
  OwnerProfile,
  ScrapeJob,
  TargetQueueItem,
  View,
} from "@/lib/types";

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof window === "undefined") return "light";
    const saved = window.localStorage.getItem("prospectiq-theme");
    return saved === "light" || saved === "dark" ? saved : "light";
  });
  const [authOpen, setAuthOpen] = useState(false);
  const [authError, setAuthError] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<OwnerProfile | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");

  // Active workspace data: 100% static dummy data when logged out; live `prospectiq.*` when Owner
  const [leadData, setLeadData] = useState<BusinessLead[]>(staticDummyLeads);
  const [jobs, setJobs] = useState<ScrapeJob[]>(mockJobs);
  const [queue, setQueue] = useState<TargetQueueItem[]>(mockQueue);
  const [quotas, setQuotas] = useState<ApiQuotaRow[]>(mockQuotas);
  const [exclusions, setExclusions] = useState<ExclusionRule[]>(mockExclusions);
  const [activeLead, setActiveLead] = useState<BusinessLead | null>(null);
  const [toast, setToast] = useState("");

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3200);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage.setItem("prospectiq-theme", theme);
    } catch {
      // Ignore storage quota / private mode restrictions
    }
  }, [theme]);

  const toggleTheme = () => setTheme((curr) => (curr === "dark" ? "light" : "dark"));

  const resetToDummyPortfolioMode = useCallback(() => {
    setIsOwner(false);
    setProfile(null);
    setSession(null);
    setLeadData(staticDummyLeads);
    setJobs(mockJobs);
    setQueue(mockQueue);
    setQuotas(mockQuotas);
    setExclusions(mockExclusions);
    setActiveLead(null);
  }, []);

  const hydrateOwnerWorkspace = useCallback(
    async (activeSession: Session, silent = false) => {
      try {
        const snapshot = await loadWorkspaceSnapshot(activeSession.user);
        setSession(activeSession);
        setProfile(snapshot.profile);
        setIsOwner(true);
        setLeadData(snapshot.leads);
        setJobs(snapshot.jobs);
        setQueue(snapshot.queue);
        setQuotas(snapshot.quotas);
        setExclusions(snapshot.exclusions);
        setAuthError("");
        setAuthOpen(false);
        if (!silent) {
          showToast("Live prospectiq.* workspace unlocked");
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Owner verification failed.";
        setAuthError(message);
        if (isSupabaseConfigured()) {
          await getSupabaseClient().auth.signOut();
        }
        resetToDummyPortfolioMode();
        setAuthOpen(true);
      }
    },
    [resetToDummyPortfolioMode, showToast],
  );

  // Restore existing session (if any) & handle /auth/callback cleanly without touching DB when logged out
  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    const supabase = getSupabaseClient();

    const initAuth = async () => {
      if (window.location.pathname === "/auth/callback") {
        window.history.replaceState({}, document.title, "/");
      }
      const { data } = await supabase.auth.getSession();
      if (data.session) {
        await hydrateOwnerWorkspace(data.session, true);
      }
    };

    void initAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (nextSession) {
        void hydrateOwnerWorkspace(nextSession, false);
      } else {
        resetToDummyPortfolioMode();
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [hydrateOwnerWorkspace, resetToDummyPortfolioMode]);

  // Subscribe to live Supabase Realtime updates ONLY while verified Owner is signed in
  useEffect(() => {
    if (!isOwner || !session) return;
    const unsubscribe = subscribeToWorkspaceRealtime({
      onLeadChange: () => {
        void hydrateOwnerWorkspace(session, true);
      },
      onJobChange: () => {
        void hydrateOwnerWorkspace(session, true);
      },
    });
    return unsubscribe;
  }, [isOwner, session, hydrateOwnerWorkspace]);

  const handleAuthAction = async () => {
    if (!isOwner) {
      setAuthError("");
      setAuthOpen(true);
      return;
    }
    if (isSupabaseConfigured()) {
      await getSupabaseClient().auth.signOut();
    }
    resetToDummyPortfolioMode();
    showToast("Signed out — returned to static portfolio preview");
  };

  const handleGlobalSearch = (value: string) => {
    setGlobalSearch(value);
    if (value.trim() && view !== "leads") {
      setView("leads");
    }
  };

  const handleUpdateStatus = async (id: string, status: OutreachStatus) => {
    setLeadData((items) =>
      items.map((lead) => (lead.id === id ? { ...lead, outreach_status: status } : lead)),
    );
    setActiveLead((curr) => (curr && curr.id === id ? { ...curr, outreach_status: status } : curr));

    if (!isOwner) {
      showToast("Demo preview updated locally (Owner sign-in required to persist)");
      return;
    }
    try {
      await updateLeadOutreachStatus(id, status);
      showToast(`Outreach status saved (${status})`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to save status");
    }
  };

  const handleBulkStatus = async (ids: string[], status: OutreachStatus) => {
    const idSet = new Set(ids);
    setLeadData((items) =>
      items.map((lead) => (idSet.has(lead.id) ? { ...lead, outreach_status: status } : lead)),
    );
    if (!isOwner) {
      showToast(`Demo preview updated ${ids.length} leads locally`);
      return;
    }
    try {
      await bulkUpdateOutreachStatus(ids, status);
      showToast(`Updated ${ids.length} leads to ${status}`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Bulk update failed");
    }
  };

  const handleSaveNotes = async (id: string, notes: string) => {
    setLeadData((items) =>
      items.map((lead) => (lead.id === id ? { ...lead, outreach_notes: notes } : lead)),
    );
    setActiveLead((curr) => (curr && curr.id === id ? { ...curr, outreach_notes: notes } : curr));

    if (!isOwner) {
      showToast("Demo note saved locally (sign in as Owner to persist)");
      return;
    }
    try {
      await updateLeadNotes(id, notes);
      showToast("Agency notes saved to prospectiq.leads");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to save notes");
    }
  };

  const handleDispatchScrape = async (payload: {
    cities: string[];
    niches: string[];
    max_results: number;
  }) => {
    if (!isOwner || !session?.access_token) {
      setAuthOpen(true);
      return;
    }
    try {
      const { job } = await triggerRemoteScrape(session.access_token, payload);
      setJobs((prev) => [job, ...prev]);
      showToast("GitHub Action dispatched — streaming live job telemetry");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to dispatch GitHub Action");
    }
  };

  const handleToggleTarget = async (id: string, enabled: boolean) => {
    setQueue((prev) => prev.map((row) => (row.id === id ? { ...row, enabled } : row)));
    if (!isOwner) return;
    try {
      await toggleTargetQueueEnabled(id, enabled);
      showToast(enabled ? "Target enabled in cron queue" : "Target paused");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed updating target queue");
    }
  };

  const handleAddTarget = async (city: string, industry: string) => {
    if (!isOwner) return;
    try {
      const created = await addTargetQueueItem(city, industry);
      setQueue((prev) => [created, ...prev.filter((r) => r.id !== created.id)]);
      showToast(`Added ${city} · ${industry} to cron queue`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed adding target");
    }
  };

  const handleAddExclusion = async (type: ExclusionPatternType, value: string) => {
    if (!isOwner) return;
    try {
      const created = await addExclusionRule(type, value);
      setExclusions((prev) => [created, ...prev.filter((r) => r.id !== created.id)]);
      showToast(`Added exclusion '${value}'`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed adding exclusion");
    }
  };

  const handleDeleteExclusion = async (id: string) => {
    setExclusions((prev) => prev.filter((r) => r.id !== id));
    if (!isOwner) return;
    try {
      await deleteExclusionRule(id);
      showToast("Exclusion removed");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed deleting exclusion");
    }
  };

  const handleExportCsv = (rows: BusinessLead[]) => {
    exportLeadsToCsv(rows, isOwner ? "prospectiq-leads" : "prospectiq-demo-leads");
    showToast(`Exported ${rows.length} leads to CSV`);
  };

  const hotCount = leadData.filter((l) => l.opportunity_score >= 80).length;
  const hasRunningJob = jobs.some((j) => j.status === "RUNNING" || j.status === "QUEUED");

  return (
    <div className={`app-shell ${collapsed ? "is-collapsed" : ""}`}>
      {!isOwner && (
        <div className="portfolio-banner">
          <span>Portfolio live preview · Static dummy data</span>
          <b>Built by Muhammad Kamal</b>
          <button onClick={() => setAuthOpen(true)}>Owner sign in</button>
        </div>
      )}
      <Sidebar
        view={view}
        setView={setView}
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        isOwner={isOwner}
        ownerName={profile?.full_name || "Muhammad Kamal"}
        hotCount={hotCount}
        hasRunningJob={hasRunningJob}
        onAuthAction={() => void handleAuthAction()}
      />
      <div className="app-main">
        <TopBar
          view={view}
          isOwner={isOwner}
          theme={theme}
          onToggleTheme={toggleTheme}
          searchQuery={globalSearch}
          onSearchChange={handleGlobalSearch}
          onRun={() => (isOwner ? setView("scraper") : setAuthOpen(true))}
          onMenu={() => setCollapsed(!collapsed)}
        />
        <main>
          {view === "dashboard" && (
            <Dashboard
              leads={leadData}
              jobs={jobs}
              quotas={quotas}
              isOwner={isOwner}
              theme={theme}
              onNavigate={setView}
            />
          )}
          {view === "leads" && (
            <LeadTable
              leads={leadData}
              globalQuery={globalSearch}
              onLead={setActiveLead}
              onStatus={(id, status) => void handleUpdateStatus(id, status)}
              onBulkStatus={(ids, status) => void handleBulkStatus(ids, status)}
              onExport={handleExportCsv}
            />
          )}
          {view === "scraper" && (
            <ScraperView
              isOwner={isOwner}
              queue={queue}
              jobs={jobs}
              onDispatch={handleDispatchScrape}
              onToggleTarget={(id, enabled) => void handleToggleTarget(id, enabled)}
              onAddTarget={(city, industry) => void handleAddTarget(city, industry)}
              onRequireAuth={() => setAuthOpen(true)}
            />
          )}
          {view === "settings" && (
            <SettingsView
              isOwner={isOwner}
              quotas={quotas}
              exclusions={exclusions}
              onAddExclusion={(type, value) => void handleAddExclusion(type, value)}
              onDeleteExclusion={(id) => void handleDeleteExclusion(id)}
              onRequireAuth={() => setAuthOpen(true)}
            />
          )}
        </main>
      </div>
      <LeadDrawer
        lead={activeLead}
        onClose={() => setActiveLead(null)}
        onSaveNotes={(id, notes) => void handleSaveNotes(id, notes)}
        onStatusChange={(id, status) => void handleUpdateStatus(id, status)}
        onToast={showToast}
      />
      <AuthModal
        open={authOpen}
        externalError={authError}
        onClose={() => setAuthOpen(false)}
        onSignedIn={() => setAuthOpen(false)}
      />
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
