import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null = null;

/**
 * Resolve the isolated PostgreSQL schema for ProspectIQ inside `shared-apps`.
 * Defaults to `"prospectiq"` so sibling schemas (e.g. `cadence`) are never touched.
 */
export function getSupabaseSchema(): string {
  const configured =
    import.meta.env.NEXT_PUBLIC_SUPABASE_SCHEMA ||
    import.meta.env.VITE_SUPABASE_SCHEMA ||
    "prospectiq";
  return configured.trim() || "prospectiq";
}

export function getSupabaseUrl(): string {
  return (
    import.meta.env.NEXT_PUBLIC_SUPABASE_URL ||
    import.meta.env.VITE_SUPABASE_URL ||
    ""
  ).trim();
}

export function getSupabaseAnonKey(): string {
  return (
    import.meta.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    import.meta.env.VITE_SUPABASE_ANON_KEY ||
    ""
  ).trim();
}

export function isSupabaseConfigured(): boolean {
  return Boolean(getSupabaseUrl() && getSupabaseAnonKey());
}

/**
 * Explicit auth callback URL used for password-reset / OAuth redirects so
 * `shared-apps` routes users back to ProspectIQ cleanly alongside Cadence.
 */
export function getAuthCallbackUrl(): string {
  if (typeof window === "undefined") {
    return "/auth/callback";
  }
  return `${window.location.origin}/auth/callback`;
}

/**
 * Publishable-key-only browser Supabase client strictly scoped to `prospectiq.*`.
 * NEVER uses a Secret / `service_role` key.
 */
export function getSupabaseClient(): SupabaseClient {
  if (browserClient) {
    return browserClient;
  }
  const url = getSupabaseUrl();
  const anonKey = getSupabaseAnonKey();
  if (!url || !anonKey) {
    throw new Error(
      "Supabase environment variables (NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY) are not configured.",
    );
  }
  const schema = getSupabaseSchema();
  browserClient = createClient(url, anonKey, {
    db: {
      // Type assertion keeps strict TypeScript happy with untyped custom schemas
      schema: schema as "public",
    },
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
  return browserClient;
}
