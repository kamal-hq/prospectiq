export type View = "dashboard" | "leads" | "scraper" | "settings";

export type WebsiteStatus = "LIVE" | "WAF_PROTECTED" | "PARKED" | "BROKEN" | "NO_WEBSITE";
export type PitchTier = "HOT" | "WARM" | "COLD";
export type PitchAngle =
  | "NO_WEBSITE"
  | "SOCIAL_ONLY"
  | "REDESIGN_SSL"
  | "SEO_ANALYTICS"
  | "ESTABLISHED";
export type OutreachStatus =
  | "NEW"
  | "CONTACTED"
  | "FOLLOW_UP"
  | "REPLIED"
  | "QUALIFIED"
  | "WON"
  | "DISQUALIFIED";

export interface BusinessLead {
  id: string;
  place_id?: string | null;
  business_name: string;
  city: string;
  industry: string;
  phone: string | null;
  address: string | null;
  rating: number | null;
  reviews_count: number;
  business_status?: string;
  is_franchise: boolean;
  website_status: WebsiteStatus;
  website_url: string | null;
  root_domain?: string | null;
  http_status?: string | null;
  has_ssl: boolean | null;
  is_mobile_friendly: boolean | null;
  cms_platform: string | null;
  has_analytics: boolean | null;
  has_meta_pixel: boolean | null;
  load_time_ms: number | null;
  email: string | null;
  email_status: string;
  email_mx_valid: boolean | null;
  secondary_emails?: string[];
  linkedin: string | null;
  instagram: string | null;
  facebook: string | null;
  twitter: string | null;
  social_status?: string;
  opportunity_score: number;
  pitch_tier: PitchTier;
  pitch_angle: PitchAngle;
  pitch_summary: string | null;
  outreach_status: OutreachStatus;
  outreach_notes: string;
  scrape_job_id?: string | null;
  discovered_at: string;
  last_enriched_at?: string;
}

export type ScrapeTriggerSource = "CRON" | "MANUAL_UI" | "CLI";
export type ScrapeJobStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED";

export interface ScrapeJob {
  id: string;
  trigger_source: ScrapeTriggerSource;
  status: ScrapeJobStatus;
  cities: string[];
  niches: string[];
  max_results_per_query: number;
  leads_discovered: number;
  leads_inserted: number;
  leads_updated: number;
  leads_skipped_dup: number;
  emails_found: number;
  blocked_count: number;
  quota_exhausted_count: number;
  github_run_url: string | null;
  error_summary: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface TargetQueueItem {
  id: string;
  city: string;
  industry: string;
  enabled: boolean;
  priority: number;
  next_page_offset: number;
  max_results_per_run: number;
  last_scraped_at: string | null;
  total_leads_found: number;
}

export type ApiProvider = "serpapi" | "brave" | "hunter";

export interface ApiQuotaRow {
  month_key: string;
  provider: ApiProvider;
  calls_used: number;
  monthly_limit: number;
  updated_at?: string;
}

export type ExclusionPatternType = "DOMAIN" | "FRANCHISE" | "EMAIL_DOMAIN";

export interface ExclusionRule {
  id: string;
  pattern_type: ExclusionPatternType;
  pattern_value: string;
  reason: string | null;
  created_at?: string;
}

export interface OwnerProfile {
  id: string;
  email: string | null;
  full_name: string | null;
  role: "owner";
}

export interface WorkspaceSnapshot {
  profile: OwnerProfile | null;
  leads: BusinessLead[];
  jobs: ScrapeJob[];
  queue: TargetQueueItem[];
  quotas: ApiQuotaRow[];
  exclusions: ExclusionRule[];
}
