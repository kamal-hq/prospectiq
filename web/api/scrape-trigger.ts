import { createClient } from "@supabase/supabase-js";

interface ApiRequest {
  method?: string;
  headers: Record<string, string | string[] | undefined>;
  body?: unknown;
}

interface ApiResponse {
  status: (code: number) => ApiResponse;
  json: (payload: unknown) => void;
  setHeader: (name: string, value: string) => void;
}

interface TriggerBody {
  cities?: unknown;
  niches?: unknown;
  max_results?: unknown;
  start?: unknown;
  mode?: unknown;
}

function getHeader(req: ApiRequest, name: string): string {
  const raw = req.headers[name] ?? req.headers[name.toLowerCase()];
  if (Array.isArray(raw)) return raw[0] ?? "";
  return typeof raw === "string" ? raw : "";
}

function parseStringArray(value: unknown, maxItems = 10): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0 && item.length <= 80)
    .slice(0, maxItems);
}

/**
 * Vercel Serverless Route: POST /api/scrape-trigger
 *
 * Shared-Supabase Security Contract (ZERO `service_role` key!):
 *   1. Uses ONLY the publishable key (`NEXT_PUBLIC_SUPABASE_ANON_KEY`) + caller's Bearer JWT.
 *   2. Verifies `user.id === process.env.OWNER_SUPABASE_USER_ID` before touching anything.
 *   3. Inserts `QUEUED` row into `prospectiq.scrape_jobs` under the Owner's JWT (RLS enforced).
 *   4. Dispatches `.github/workflows/auto-scrape.yml` via server-only `GITHUB_DISPATCH_TOKEN`.
 */
export default async function handler(req: ApiRequest, res: ApiResponse): Promise<void> {
  res.setHeader("Content-Type", "application/json; charset=utf-8");

  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed. Use POST." });
    return;
  }

  const supabaseUrl = (
    process.env.NEXT_PUBLIC_SUPABASE_URL ||
    process.env.SUPABASE_URL ||
    ""
  ).trim();
  const supabaseAnonKey = (
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    ""
  ).trim();
  const supabaseSchema = (
    process.env.NEXT_PUBLIC_SUPABASE_SCHEMA ||
    process.env.SUPABASE_SCHEMA ||
    "prospectiq"
  ).trim();
  const ownerUserId = (process.env.OWNER_SUPABASE_USER_ID || "").trim();
  const githubToken = (process.env.GITHUB_DISPATCH_TOKEN || "").trim();
  const githubOwner = (process.env.GITHUB_REPO_OWNER || "kamal-hq").trim();
  const githubRepo = (process.env.GITHUB_REPO_NAME || "prospectiq").trim();

  if (!supabaseUrl || !supabaseAnonKey || !ownerUserId) {
    res.status(500).json({
      error: "Server misconfiguration: missing Supabase URL, publishable key, or OWNER_SUPABASE_USER_ID.",
    });
    return;
  }

  if (!githubToken) {
    res.status(500).json({
      error: "Server misconfiguration: missing GITHUB_DISPATCH_TOKEN in Vercel environment variables.",
    });
    return;
  }

  // 1. Extract & verify Owner JWT using ONLY the publishable key
  const authHeader = getHeader(req, "authorization");
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
  if (!token) {
    res.status(401).json({ error: "Authentication required." });
    return;
  }

  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    db: { schema: supabaseSchema as "public" },
    global: {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });

  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser(token);

  if (authError || !user) {
    res.status(401).json({ error: "Invalid or expired Supabase session." });
    return;
  }

  if (user.id !== ownerUserId) {
    res.status(403).json({
      error: "Forbidden: only the ProspectIQ Owner account can dispatch live scrapes.",
    });
    return;
  }

  // 2. Validate request payload
  const body = (typeof req.body === "string" ? JSON.parse(req.body) : req.body || {}) as TriggerBody;
  const cities = parseStringArray(body.cities, 6);
  const niches = parseStringArray(body.niches, 6);
  const maxResults = Math.min(20, Math.max(1, Number(body.max_results) || 10));
  const start = Math.max(0, Number(body.start) || 0);
  const mode = body.mode === "mock" ? "mock" : "live";

  if (!cities.length || !niches.length) {
    res.status(400).json({ error: "Select at least one city and one industry niche." });
    return;
  }

  // 3. Create QUEUED job row in `prospectiq.scrape_jobs` using Owner's RLS-checked JWT
  const { data: createdJob, error: insertError } = await supabase
    .from("scrape_jobs")
    .insert({
      trigger_source: "MANUAL_UI",
      status: "QUEUED",
      cities,
      niches,
      max_results_per_query: maxResults,
    })
    .select("*")
    .single();

  if (insertError || !createdJob) {
    res.status(500).json({
      error: `Failed to queue scrape job in ${supabaseSchema}.scrape_jobs: ${insertError?.message ?? "unknown error"}`,
    });
    return;
  }

  // 4. Dispatch GitHub Actions workflow (`auto-scrape.yml`)
  const dispatchUrl = `https://api.github.com/repos/${encodeURIComponent(githubOwner)}/${encodeURIComponent(githubRepo)}/actions/workflows/auto-scrape.yml/dispatches`;

  const ghResp = await fetch(dispatchUrl, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${githubToken}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: {
        mode,
        cities: JSON.stringify(cities),
        niches: JSON.stringify(niches),
        max_results: String(maxResults),
        start: String(start),
        job_id: String(createdJob.id),
        trigger_source: "MANUAL_UI",
      },
    }),
  });

  if (!ghResp.ok) {
    const ghErrorText = await ghResp.text().catch(() => "");
    await supabase
      .from("scrape_jobs")
      .update({
        status: "FAILED",
        error_summary: `GitHub dispatch failed (HTTP ${ghResp.status}): ${ghErrorText.slice(0, 300)}`,
        finished_at: new Date().toISOString(),
      })
      .eq("id", createdJob.id);

    res.status(502).json({
      error: `GitHub Actions dispatch rejected (HTTP ${ghResp.status}). Check GITHUB_DISPATCH_TOKEN permissions (actions:write).`,
    });
    return;
  }

  res.status(202).json({ ok: true, job: createdJob });
}
