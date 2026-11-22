# ProspectIQ v3.0 — Design System, Component Architecture & Figma Pro Prompt (`design.md`)

> **Visual Positioning:** High-craft B2B Revenue Intelligence SaaS (Linear × Clay × Vercel aesthetic).  
> **Dual Identity:** Daily agency client-acquisition command center for Muhammad Kamal + impressive live portfolio showcase in read-only mode.

---

## 1. Visual Design System & Tokens

### Theme & Color Palette (Dark-Mode Default)
| Token | Hex | Usage |
| :--- | :--- | :--- |
| `--bg-canvas` | `#09090B` | Main application background (deep obsidian) |
| `--bg-surface` | `#111114` | Sidebar, cards, table header, drawer surface |
| `--bg-elevated` | `#18181B` | Hover rows, input fields, modal/popover surfaces |
| `--border-subtle` | `#27272A` | 1px hairline borders on cards, dividers, tables |
| `--border-active` | `#3F3F46` | Focused inputs, active segmented tabs |
| `--text-primary` | `#FAFAFA` | Headings, business names, primary KPI figures |
| `--text-secondary` | `#A1A1AA` | Metadata, table sub-labels, descriptions |
| `--text-muted` | `#71717A` | Placeholders, timestamps, inactive icons |
| `--accent-primary` | `#6366F1` | Primary CTA ("Run Scrape"), active nav, focus rings |
| `--accent-hover` | `#818CF8` | Primary CTA hover & link highlights |
| `--status-hot` | `#10B981` | Hot Lead (80–100 score), MX Verified, LIVE site, Completed |
| `--status-warm` | `#F59E0B` | Warm Lead (50–79), Redesign Pitch, WAF Protected, Quota Warning |
| `--status-alert` | `#F43F5E` | No Website / Broken / Failed Job / Quota Exhausted |
| `--status-info` | `#38BDF8` | Running Job pulse, Social-Only Pitch, Info badges |

### Typography
- **UI Font:** `Inter` (Regular 400, Medium 500, SemiBold 600, Bold 700)
- **Data / Monospace Font:** `JetBrains Mono` (Opportunity Scores, HTTP status codes, phone numbers, verified emails, quota fractions `42/250`, timestamps)

### Layout & Surface Rules
- **Hairline Precision:** Use crisp `1px solid #27272A` borders rather than heavy shadows.
- **Border Radius:** `10px` cards/panels, `8px` buttons/inputs, `9999px` status badges & filter pills.
- **Density:** High information density with generous horizontal breathing room (`24px` page padding, `16px` grid gaps, `48px`–`56px` table row height).

---

## 2. Information Architecture (5 Core Views + Global Shell)

1. **Global App Shell:**
   - **Left Collapsible Sidebar (`240px`):** ProspectIQ brand mark, navigation (`Command Center`, `Lead Explorer`, `Auto-Scraper`, `Target Queue`, `Quota & Settings`), Live Scraper Status Pill (green idle / pulsing blue active job), and bottom **Auth Card** (shows *"Interactive Demo Data · Owner Sign In"* when logged out — zero public sign-up, 100% static dummy data — or *"Muhammad Kamal · Live Agency Data"* when authenticated as Owner UUID).
   - **Top Header Bar (`64px`):** Breadcrumb page title, `⌘K` Quick Search input, active workspace badge, and primary electric-indigo **"Run Scrape"** CTA button.
2. **View 1 — Command Center (Overview Dashboard):**
   - 4 KPI Stat Cards (`Total Verified Leads`, `Hot Agency Pitches (80+)`, `MX-Verified Emails`, `Active Outreach Pipeline`) with mini trend sparklines.
   - 2-Column Analytics Row: **Prospecting Funnel Chart** (Discovered -> Audited -> Contact Ready -> Contacted -> Won) + **Pitch Angle Breakdown Donut** (`No Website`, `Social Only`, `Redesign / No SSL`, `Missing Analytics`).
   - Bottom Row: **Live API Quota Health** (SerpApi, Brave Search, Hunter.io progress bars with reset date) + **Recent Automated Scrape Jobs** live timeline.
3. **View 2 — Lead Explorer (Primary Agency CRM Workspace):**
   - Quick-Segment Pill Bar: `All Leads`, `🔥 Hot: No Website`, `📱 Social-Only`, `🛠️ Redesign / No SSL`, `✅ MX-Verified Email`, `📞 Phone Ready`.
   - Multi-Filter Toolbar: Search input, City dropdown, Niche dropdown, Min Score selector, Outreach Stage filter, and **Export Filtered CSV** button.
   - High-Density Data Table:
     - Checkbox | **Business & City** (Name, Industry badge, Google Rating `4.8 ★ (214)`) | **Score** (Circular progress badge `94`) | **Pitch Angle** (Color-coded pill) | **Digital Audit** (Compact icon strip: SSL, Mobile, CMS, Pixel) | **Contacts** (Email + MX tick, Phone, Social icons) | **Outreach Stage** (Inline colored status pill dropdown) | Quick Inspect arrow.
   - Floating Sticky Bulk Action Bar when rows are selected (`Export CSV`, `Mark Contacted`, `Archive`).
4. **View 3 — Lead Intelligence Slide-Over Drawer (`520px` right panel):**
   - Opens smoothly over Lead Explorer on row click.
   - Header: Business Name, City/Address, Google Rating + Review count, Opportunity Score Gauge (`94/100 · HOT`), and **Recommended Agency Pitch Callout Card** (auto-generated summary like *"4.9★ plumber with 186 reviews operating solely on Facebook — strong website + SEO pitch"*).
   - **Digital Footprint Audit Grid (2×3 cards):** Website Status (`NO_WEBSITE` / `LIVE` / `WAF_PROTECTED` / `PARKED`), SSL Security, Mobile Friendly, Detected CMS, Tracking Pixels (GA4 / Meta), Load Speed (`ms`).
   - **Verified Contact Stack:** Copyable Primary Email (with `MX VERIFIED` badge & source tag `On-Site` / `Hunter`), Copyable Phone Number, clickable Social Profile chips (LinkedIn, Instagram, Facebook, X).
   - **Outreach CRM Panel:** Status selector (`New -> Contacted -> Follow-Up -> Replied -> Qualified -> Won`) + editable Agency Notes textarea with auto-save indicator.
   - Sticky Footer: `Open Website`, `Copy Pitch Summary`, `Re-Enrich Lead`.
5. **View 4 — Auto-Scraper & Target Queue:**
   - **Manual Scrape Launcher Card:** Multi-tag inputs for Cities (`Houston, TX`, `Austin, TX`) & Niches (`Plumbing`, `HVAC`), Max Leads slider, Estimated Quota Cost badge (`~2 SerpApi credits`), and **"Dispatch GitHub Action"** button.
   - **Automated Cron Target Queue Table:** City, Niche, Schedule status toggle (`Enabled/Paused`), Pagination Depth (`Page 3 · 30 leads`), Last Scraped timestamp, Add Target button.
   - **Live Job Runs & Telemetry Feed:** Expandable run history showing Trigger (`CRON` / `MANUAL`), Status badge, Leads Inserted vs Duplicates Skipped, Emails Found, Blocked count, Duration, and GitHub Actions Log link.
6. **View 5 — Quota Guard & Settings:**
   - Monthly Quota Meters (SerpApi `42/250`, Brave `18/1000`, Hunter `11/50`) with warning threshold indicators.
   - Exclusion List Manager (add/remove Franchises, Aggregator Domains, Junk Email Domains).
   - Opportunity Scoring Weights Preview (read-only/configurable cards showing how 0–100 scores are calculated).

---

## 3. Target Next.js Component Tree (`web/src/`)

```text
web/src/
├── app/
│   ├── layout.tsx                   # AppShell (Sidebar + Header + Theme + AuthProvider)
│   ├── page.tsx                     # Command Center (Dashboard Overview)
│   ├── leads/page.tsx               # Lead Explorer + Slide-Over Drawer
│   ├── scraper/page.tsx             # Auto-Scraper Launcher + Target Queue + Job Logs
│   ├── settings/page.tsx            # Quota Guard + Exclusions + Scoring Rules
│   └── api/
│       ├── scrape/trigger/route.ts  # Authenticated GitHub Actions workflow_dispatch
│       └── leads/export/route.ts    # Filtered CSV download
├── components/
│   ├── layout/ (Sidebar.tsx, TopBar.tsx, PortfolioBanner.tsx, AuthModal.tsx)
│   ├── dashboard/ (KpiCard.tsx, FunnelChart.tsx, PitchDonut.tsx, QuotaBars.tsx, RecentJobs.tsx)
│   ├── leads/ (LeadTable.tsx, LeadFilters.tsx, ScoreBadge.tsx, AuditIcons.tsx, LeadDrawer.tsx, BulkActionBar.tsx)
│   ├── scraper/ (ScrapeLauncher.tsx, TargetQueueTable.tsx, JobHistoryTable.tsx)
│   └── ui/ (Badge.tsx, Button.tsx, Card.tsx, Drawer.tsx, Modal.tsx, Select.tsx)
└── lib/ (supabase/client.ts, supabase/server.ts, types.ts, csv.ts)
```

---

## 4. Exact Figma Pro / Figma Make Generation Prompt

> Copy everything inside the fenced block below and paste it directly into **Figma Pro / Figma Make**. It is structured to produce clean, modular **React / Next.js + Tailwind CSS + TypeScript + Lucide Icons + Recharts** code that drops straight into `web/`.

```text
Build a complete, high-craft dark-mode B2B SaaS web application called "ProspectIQ" — an Automated Agency Lead Prospecting & Web Presence Intelligence Platform built by Muhammad Kamal.

TECHNICAL & CODE REQUIREMENTS (CRITICAL FOR EXPORT):
- Build with clean, modular React + TypeScript + Tailwind CSS (compatible with Next.js App Router).
- Use `lucide-react` for all icons and `recharts` for charts.
- Separate components cleanly into logical files (Sidebar, TopBar, KpiCard, LeadTable, LeadDrawer, ScrapeLauncher, TargetQueueTable, JobHistoryTable, QuotaGuard, AuthModal).
- Use a strict TypeScript `BusinessLead` interface matching our Supabase Postgres schema:
  id, business_name, city, industry, phone, address, rating, reviews_count, is_franchise, website_status ('LIVE' | 'WAF_PROTECTED' | 'PARKED' | 'BROKEN' | 'NO_WEBSITE'), website_url, has_ssl, is_mobile_friendly, cms_platform, has_analytics, has_meta_pixel, load_time_ms, email, email_status, email_mx_valid, linkedin, instagram, facebook, twitter, opportunity_score (0-100), pitch_tier ('HOT' | 'WARM' | 'COLD'), pitch_angle ('NO_WEBSITE' | 'SOCIAL_ONLY' | 'REDESIGN_SSL' | 'SEO_ANALYTICS' | 'ESTABLISHED'), pitch_summary, outreach_status ('NEW' | 'CONTACTED' | 'FOLLOW_UP' | 'REPLIED' | 'QUALIFIED' | 'WON' | 'DISQUALIFIED'), outreach_notes, discovered_at.
- Populate with 14 highly realistic US local service business mock leads (Plumbing, HVAC, Roofing, Landscaping, Auto Detailing across Houston TX, Austin TX, Dallas TX, Miami FL, Atlanta GA) — including hot no-website leads with 4.8★ ratings & phone numbers, Facebook-only leads, outdated HTTP-only Wix sites, WAF-protected sites, and MX-verified email leads.

VISUAL DESIGN SYSTEM (Linear × Clay × Vercel Aesthetic):
- Default Dark Mode: Canvas #09090B, Surface/Cards #111114, Elevated Hover #18181B, Hairline Borders 1px solid #27272A.
- Accent & Semantic Colors: Primary Electric Indigo #6366F1 (hover #818CF8), Hot/Verified Emerald #10B981, Warm/Redesign Amber #F59E0B, Alert/No-Site Rose #F43F5E, Active Job Sky #38BDF8.
- Typography: Inter for UI, JetBrains Mono for Opportunity Scores, ratings, phone numbers, email addresses, quota fractions, and timestamps.
- Crisp 1px borders, subtle hover states, zero clutter, generous spacing, high executive readability, fully responsive.

GLOBAL LAYOUT SHELL:
1. Top Portfolio Preview Banner (toggleable via a demo "Switch to Admin / Portfolio Mode" button in the sidebar footer so I can preview both states):
   - In Portfolio (Read-Only) mode: Subtle indigo-tinted slim bar stating "Portfolio Live Preview (Read-Only) · Built by Muhammad Kamal" with a "Sign In as Admin" button. Mutation actions show a lock icon tooltip.
   - In Admin mode: Full interactive access to launch scrapes, edit outreach status, save notes, and manage the cron queue.
2. Collapsible Left Sidebar (240px):
   - ProspectIQ logo mark (geometric radar/spark icon in indigo gradient) + "v3.0" pill.
   - Navigation tabs with counts/badges:
     1) Command Center (Dashboard)
     2) Lead Explorer (with badge showing Hot Lead count)
     3) Auto-Scraper & Queue (with pulsing green/blue dot when job active)
     4) Quota & Settings
   - Bottom Sidebar Card: Live GitHub Actions Worker status ("Next Auto-Scrape: Daily 08:00 UTC") + User/Mode switcher.
3. Top Sticky Header (64px):
   - Active view title, interactive search bar ("Search leads, cities, domains... ⌘K"), and a prominent Electric Indigo "+ Run Scrape" button that opens the Scrape Launcher modal or navigates to Auto-Scraper.

VIEWS & INTERACTIVE FEATURES TO BUILD:

VIEW 1 — COMMAND CENTER (Overview Dashboard):
- 4 KPI Cards in a 4-column grid with trend badges and subtle sparklines:
  1) Total Verified Leads (e.g., 1,284 · +142 this week)
  2) Hot Agency Pitches (80+ Score) (e.g., 318 · 24.7% of pool)
  3) MX-Verified Emails (e.g., 692 · 94% deliverability)
  4) Active Outreach Deals (e.g., 47 Contacted · 11 Replied)
- 2-Column Charts Row:
  - Left (8 cols): Prospecting Conversion Funnel Bar/Area Chart (Discovered -> Audited -> Contact Ready -> Contacted -> Replied -> Won).
  - Right (4 cols): Lead Opportunity Breakdown Donut Chart (No Website, Social Only, Redesign/No SSL, Missing Analytics, Established) with clean legend.
- 2-Column Operational Row:
  - Left (5 cols): Live API Quota Guard card with horizontal progress bars & monospace counters for SerpApi (42/250), Brave Search (18/1,000), and Hunter.io (11/50 — "Free-First Protected").
  - Right (7 cols): Recent Automated Scrape Runs list showing City × Niche, trigger tag (CRON / MANUAL), live status pill (COMPLETED / RUNNING), leads added, duplicates skipped, and timestamp.

VIEW 2 — LEAD EXPLORER (Primary Agency Prospecting Table + Slide-Over Drawer):
- Quick Filter Segment Pills above the table:
  "All Leads", "🔥 Hot: No Website", "📱 Social Only", "🛠️ Redesign / No SSL", "✅ MX-Verified Email", "📞 Phone Ready"
- Filter Bar: Search input, City select, Industry select, Min Score dropdown (Any / 70+ / 85+), Outreach Status filter, and "Export CSV" button.
- Interactive Sortable Data Table:
  - Columns:
    1) Checkbox (for bulk actions)
    2) Business (Business Name, City + Industry subtle sub-label, Google Rating star + review count e.g. "4.9 ★ (214)")
    3) Score (Color-coded circular ring / pill in JetBrains Mono: 80-100 Emerald, 50-79 Amber, <50 Slate)
    4) Pitch Angle (Distinct pill: "No Website" Rose, "Social Only" Sky, "Redesign / No SSL" Amber, "SEO / No Pixel" Indigo)
    5) Digital Health (Compact 4-icon status row with hover tooltips: Globe/Status, Lock/SSL, Smartphone/Mobile, Activity/Analytics + CMS tag like "Wix" or "WP")
    6) Contacts (Primary Email with green MX-verified checkmark + Phone number + clickable subtle social icons for FB/IG/LI/X)
    7) Outreach Stage (Interactive inline status pill dropdown: New, Contacted, Follow-Up, Replied, Qualified, Won, Disqualified)
- Floating Bottom Bulk Action Bar when 1+ rows checked: "X selected · Export CSV · Set Outreach Status · Disqualify".
- CLICKING ANY LEAD ROW OPENS THE RIGHT SLIDE-OVER INTELLIGENCE DRAWER (520px wide, backdrop dim, smooth slide animation):
  - Header: Business Name, City & Full Address, Google Rating & Review Count, Opportunity Score badge (e.g., 94/100 · HOT), Close button.
  - Highlighted "Recommended Agency Pitch" Card with border-left indigo/emerald accent explaining *why* this business is a prime client target.
  - "Digital Footprint Audit" 2×3 mini-card grid: Website Status, SSL/HTTPS, Mobile Viewport, CMS Platform, Analytics/Meta Pixel, Load Time (ms).
  - "Verified Contact Stack": Primary Email with MX Verified green pill + extraction source tag ("On-Site JSON-LD" or "Hunter Fallback") + one-click Copy button; Direct Phone with Copy button; Social Links row (LinkedIn, Instagram, Facebook, X).
  - "Outreach CRM": Stage selector dropdown + persistent Agency Notes textarea + "Save Notes" button.
  - Sticky Drawer Footer: "Visit Website" (if live), "Copy Pitch Brief", and "Re-Enrich Lead".

VIEW 3 — AUTO-SCRAPER & TARGET QUEUE:
- Top Split Grid:
  - Left Card (5 cols): "Launch On-Demand Scrape" form — interactive tag selector for Cities and Niches, Max Results per Query slider (5–20), Live Credit Estimator box ("Est. cost: 2 SerpApi credits · Hunter fallback only"), and primary "Dispatch GitHub Action" button with simulated live running feedback!
  - Right Card (7 cols): "Automated Cron Target Queue" table — columns: City, Industry, Pagination Depth ("Page 3 · 30 found"), Last Run, Enabled toggle switch, "+ Add Target" inline form.
- Bottom Full-Width Card: "Scrape Job Execution History" table showing Job ID, Trigger (CRON / MANUAL_UI), Status pill (RUNNING pulsing blue / COMPLETED green / PARTIAL amber), Targets, Discovered / Inserted / Duplicates Skipped / Emails Found / Blocked metrics, Duration, and "View GitHub Logs" external link.

VIEW 4 — QUOTA GUARD & SETTINGS:
- 3 Visual Monthly Quota Cards (SerpApi, Brave Search, Hunter.io) with large monospace usage meters, percentage bars, and monthly reset date.
- "Anti-Garbage Exclusion List" Manager with tabs (Aggregator Domains, Franchises, Junk Email Domains), removable chips, and an input to add new exclusions.
- "Agency Opportunity Scoring Formula" transparent breakdown card showing point weights (e.g., No Website +35, High Google Reviews +20, Phone/Email Ready +20, Missing SSL/Analytics +15, Franchise Penalty -40).

Make all navigation tabs, table filters, search, sorting, bulk selection, inline outreach status changes, slide-over lead drawer, copy-to-clipboard toasts, demo Admin/Portfolio mode switcher, and simulated scrape dispatch fully interactive in the preview!
```
