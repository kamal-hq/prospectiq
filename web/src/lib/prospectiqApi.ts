import type { RealtimeChannel, User } from "@supabase/supabase-js";
import { getSupabaseClient, getSupabaseSchema } from "./supabase";
import type {
  ApiProvider,
  ApiQuotaRow,
  BusinessLead,
  ExclusionPatternType,
  ExclusionRule,
  OutreachStatus,
  OwnerProfile,
  ScrapeJob,
  TargetQueueItem,
  WorkspaceSnapshot,
} from "./types";

const DEFAULT_LIMITS: Record<ApiProvider, number> = {
  serpapi: 250,
  brave: 1000,
  hunter: 50,
};

function currentUtcMonthKey(): string {
  const now = new Date();
  const year = now.getUTCFullYear();
  const month = String(now.getUTCMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

/**
 * Lazily and idempotently provision the Owner's `prospectiq.profiles` row on first
 * authenticated visit (ZERO triggers on shared `auth.users`).
 * Also acts as an Owner-RLS gate: non-owner `shared-apps` users (e.g. Cadence users)
 * are rejected by `prospectiq.is_owner()` RLS before any workspace data is loaded.
 */
export async function ensureOwnerProfile(user: User): Promise<OwnerProfile> {
  const supabase = getSupabaseClient();
  const fullName =
    typeof user.user_metadata?.full_name === "string" && user.user_metadata.full_name.trim()
      ? user.user_metadata.full_name.trim()
      : "Muhammad Kamal";

  const { data, error } = await supabase
    .from("profiles")
    .upsert(
      {
        id: user.id,
        email: user.email ?? null,
        full_name: fullName,
        role: "owner",
        updated_at: new Date().toISOString(),
      },
      { onConflict: "id" },
    )
    .select("id, email, full_name, role")
    .single();

  if (error || !data) {
    throw new Error(
      "Access denied: this private workspace is restricted to the ProspectIQ Owner account.",
    );
  }
  return data as OwnerProfile;
}

/**
 * Load the full live `prospectiq.*` workspace snapshot for the authenticated Owner.
 * NEVER called when logged out (unauthenticated visitors render static dummy data only).
 */
export async function loadWorkspaceSnapshot(user: User): Promise<WorkspaceSnapshot> {
  const profile = await ensureOwnerProfile(user);
  const supabase = getSupabaseClient();
  const monthKey = currentUtcMonthKey();

  const [leadsRes, jobsRes, queueRes, quotasRes, exclusionsRes] = await Promise.all([
    supabase
      .from("leads")
      .select("*")
      .order("opportunity_score", { ascending: false })
      .order("discovered_at", { ascending: false })
      .limit(500),
    supabase
      .from("scrape_jobs")
      .select("*")
      .order("started_at", { ascending: false })
      .limit(25),
    supabase
      .from("target_queue")
      .select("*")
      .order("priority", { ascending: true })
      .order("last_scraped_at", { ascending: true, nullsFirst: true }),
    supabase.from("api_quotas").select("*").eq("month_key", monthKey),
    supabase.from("exclusions").select("*").order("created_at", { ascending: false }),
  ]);

  if (leadsRes.error) throw leadsRes.error;
  if (jobsRes.error) throw jobsRes.error;
  if (queueRes.error) throw queueRes.error;
  if (quotasRes.error) throw quotasRes.error;
  if (exclusionsRes.error) throw exclusionsRes.error;

  const rawQuotas = (quotasRes.data ?? []) as ApiQuotaRow[];
  const quotaByProvider = new Map<ApiProvider, ApiQuotaRow>(
    rawQuotas.map((row) => [row.provider, row]),
  );
  const normalizedQuotas: ApiQuotaRow[] = (["serpapi", "brave", "hunter"] as ApiProvider[]).map(
    (provider) =>
      quotaByProvider.get(provider) ?? {
        month_key: monthKey,
        provider,
        calls_used: 0,
        monthly_limit: DEFAULT_LIMITS[provider],
      },
  );

  return {
    profile,
    leads: (leadsRes.data ?? []) as BusinessLead[],
    jobs: (jobsRes.data ?? []) as ScrapeJob[],
    queue: (queueRes.data ?? []) as TargetQueueItem[],
    quotas: normalizedQuotas,
    exclusions: (exclusionsRes.data ?? []) as ExclusionRule[],
  };
}

export async function updateLeadOutreachStatus(
  id: string,
  outreachStatus: OutreachStatus,
): Promise<void> {
  const supabase = getSupabaseClient();
  const { error } = await supabase
    .from("leads")
    .update({ outreach_status: outreachStatus })
    .eq("id", id);
  if (error) throw error;
}

export async function bulkUpdateOutreachStatus(
  ids: string[],
  outreachStatus: OutreachStatus,
): Promise<void> {
  if (!ids.length) return;
  const supabase = getSupabaseClient();
  const { error } = await supabase
    .from("leads")
    .update({ outreach_status: outreachStatus })
    .in("id", ids);
  if (error) throw error;
}

export async function updateLeadNotes(id: string, outreachNotes: string): Promise<void> {
  const supabase = getSupabaseClient();
  const { error } = await supabase
    .from("leads")
    .update({ outreach_notes: outreachNotes })
    .eq("id", id);
  if (error) throw error;
}

export async function toggleTargetQueueEnabled(id: string, enabled: boolean): Promise<void> {
  const supabase = getSupabaseClient();
  const { error } = await supabase
    .from("target_queue")
    .update({ enabled })
    .eq("id", id);
  if (error) throw error;
}

export async function addTargetQueueItem(
  city: string,
  industry: string,
  maxResultsPerRun = 10,
): Promise<TargetQueueItem> {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from("target_queue")
    .upsert(
      {
        city: city.trim(),
        industry: industry.trim(),
        enabled: true,
        priority: 5,
        max_results_per_run: maxResultsPerRun,
      },
      { onConflict: "city,industry" },
    )
    .select("*")
    .single();
  if (error || !data) throw error ?? new Error("Failed to save target queue item");
  return data as TargetQueueItem;
}

export async function addExclusionRule(
  patternType: ExclusionPatternType,
  patternValue: string,
  reason = "Added from ProspectIQ Settings",
): Promise<ExclusionRule> {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from("exclusions")
    .upsert(
      {
        pattern_type: patternType,
        pattern_value: patternValue.trim().toLowerCase(),
        reason,
      },
      { onConflict: "pattern_type,pattern_value" },
    )
    .select("*")
    .single();
  if (error || !data) throw error ?? new Error("Failed to add exclusion rule");
  return data as ExclusionRule;
}

export async function deleteExclusionRule(id: string): Promise<void> {
  const supabase = getSupabaseClient();
  const { error } = await supabase.from("exclusions").delete().eq("id", id);
  if (error) throw error;
}

export interface TriggerScrapeInput {
  cities: string[];
  niches: string[];
  max_results: number;
  start?: number;
  mode?: "live" | "mock";
}

export async function triggerRemoteScrape(
  accessToken: string,
  payload: TriggerScrapeInput,
): Promise<{ job: ScrapeJob }> {
  const response = await fetch("/api/scrape-trigger", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
  });

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error(
      "On-demand GitHub Action dispatch runs via Vercel Serverless (/api/scrape-trigger). Deploy `web/` to Vercel or trigger directly from GitHub Actions.",
    );
  }

  const body = (await response.json()) as { error?: string; job?: ScrapeJob };
  if (!response.ok || !body.job) {
    throw new Error(body.error || `Scrape trigger failed (HTTP ${response.status})`);
  }
  return { job: body.job };
}

/**
 * Subscribe to Supabase Realtime updates on `prospectiq.leads` and `prospectiq.scrape_jobs`.
 */
export function subscribeToWorkspaceRealtime(handlers: {
  onLeadChange: () => void;
  onJobChange: () => void;
}): () => void {
  const supabase = getSupabaseClient();
  const schema = getSupabaseSchema();

  const channel: RealtimeChannel = supabase
    .channel(`prospectiq-realtime-${Date.now()}`)
    .on(
      "postgres_changes",
      { event: "*", schema, table: "leads" },
      () => handlers.onLeadChange(),
    )
    .on(
      "postgres_changes",
      { event: "*", schema, table: "scrape_jobs" },
      () => handlers.onJobChange(),
    )
    .subscribe();

  return () => {
    void supabase.removeChannel(channel);
  };
}

/**
 * RFC-4180 safe CSV export of the current filtered/selected leads.
 */
export function exportLeadsToCsv(leads: BusinessLead[], filenamePrefix = "prospectiq-leads"): void {
  const headers = [
    "Business Name",
    "City",
    "Industry",
    "Opportunity Score",
    "Pitch Tier",
    "Pitch Angle",
    "Website Status",
    "Website URL",
    "SSL",
    "Mobile Friendly",
    "CMS",
    "Email",
    "MX Valid",
    "Phone",
    "Google Rating",
    "Reviews",
    "Outreach Status",
    "Outreach Notes",
    "Discovered At",
  ];

  const escapeCell = (value: unknown): string => {
    const str = value === null || value === undefined ? "" : String(value);
    if (/[",\n\r]/.test(str)) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const rows = leads.map((lead) =>
    [
      lead.business_name,
      lead.city,
      lead.industry,
      lead.opportunity_score,
      lead.pitch_tier,
      lead.pitch_angle,
      lead.website_status,
      lead.website_url ?? "",
      lead.has_ssl === null ? "" : lead.has_ssl ? "Yes" : "No",
      lead.is_mobile_friendly === null ? "" : lead.is_mobile_friendly ? "Yes" : "No",
      lead.cms_platform ?? "",
      lead.email ?? "",
      lead.email_mx_valid === null ? "" : lead.email_mx_valid ? "Yes" : "No",
      lead.phone ?? "",
      lead.rating ?? "",
      lead.reviews_count,
      lead.outreach_status,
      lead.outreach_notes,
      lead.discovered_at,
    ]
      .map(escapeCell)
      .join(","),
  );

  const csvContent = [headers.join(","), ...rows].join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 10);
  link.href = url;
  link.download = `${filenamePrefix}-${stamp}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
