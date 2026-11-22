"""
CLI & GitHub Actions Orchestrator — main.py

Central pipeline orchestrator and CLI interface for ProspectIQ v3.0.
Single responsibility: Parse CLI/CI arguments, manage cloud scrape_jobs & target_queue
lifecycle when Supabase is configured, orchestrate sequential typed data flow across
modules (discovery -> pre-scrape dedup -> validator -> extractor -> scorer -> models ->
database), render ASCII-safe progress, and print summary metrics.
Contains NO business logic, NO direct HTTP calls, and NO HTML parsing.
"""

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from colorama import Fore, Style, init as colorama_init

from engine import config, database, discovery, extractor, scorer, validator
from engine.logger import setup_logger
from engine.models import BusinessLead, RawCandidate

colorama_init(autoreset=True)
log = setup_logger("main")

BANNER = f"""
{Fore.CYAN}+==================================================================+
|                                                                  |
|   {Fore.WHITE}*  ProspectIQ v3.0 -- Agency Lead Intelligence Engine  *{Fore.CYAN}         |
|   {Fore.YELLOW}   Muhammad Kamal -- Automated Prospecting Pipeline{Fore.CYAN}            |
|                                                                  |
+==================================================================+{Style.RESET_ALL}
"""


def _parse_multi_value_arg(raw_values: List[str]) -> List[str]:
    """
    Parse CLI or GitHub Actions workflow_dispatch list inputs without splitting
    city names containing commas (e.g. 'Houston, TX').

    Supported formats:
      - Standard CLI tokens:  ['Houston, TX', 'Austin, TX']
      - JSON array string:    ['["Houston, TX", "Austin, TX"]']
      - Pipe/semicolon list:  ['Houston, TX | Austin, TX'] or ['Houston, TX; Austin, TX']
    """
    parsed: List[str] = []
    for item in raw_values:
        text = (item or "").strip()
        if not text:
            continue
        if text.startswith("[") and text.endswith("]"):
            try:
                loaded = json.loads(text)
                if isinstance(loaded, list):
                    for entry in loaded:
                        val = str(entry).strip()
                        if val:
                            parsed.append(val)
                    continue
            except Exception:
                pass
        if "|" in text:
            parsed.extend(part.strip() for part in text.split("|") if part.strip())
        elif ";" in text:
            parsed.extend(part.strip() for part in text.split(";") if part.strip())
        else:
            parsed.append(text)
    return parsed


def _get_github_run_url() -> Optional[str]:
    """Construct the GitHub Actions run URL when executing inside GitHub Actions CI."""
    server = os.getenv("GITHUB_SERVER_URL", "").strip().rstrip("/")
    repo = os.getenv("GITHUB_REPOSITORY", "").strip().strip("/")
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def _build_mock_candidates() -> List[RawCandidate]:
    """
    Offline mock dataset exercising all v3.0 anti-garbage paths:
    live site, no-website hot lead, Facebook-only social split, broken 404, and franchise flag.
    """
    raw_items = [
        {
            "place_id": "mock_place_001",
            "business_name": "Bayou City Rooter",
            "city": "Houston, TX",
            "industry": "Plumbing",
            "phone": "(713) 555-0184",
            "address": "1919 N Loop W, Houston, TX 77008",
            "rating": 4.9,
            "reviews_count": 214,
            "raw_url": None,
        },
        {
            "place_id": "mock_place_002",
            "business_name": "Plumb Masters TX",
            "city": "Austin, TX",
            "industry": "Plumbing",
            "phone": "(512) 555-0147",
            "address": "4401 Freidrich Ln, Austin, TX 78744",
            "rating": 4.8,
            "reviews_count": 162,
            "raw_url": "https://m.facebook.com/plumb.masters/?utm_source=gmb",
        },
        {
            "place_id": "mock_place_003",
            "business_name": "Apex Plumbing Pros",
            "city": "Dallas, TX",
            "industry": "Plumbing",
            "phone": "(214) 555-0192",
            "address": "2727 Irving Blvd, Dallas, TX 75207",
            "rating": 4.7,
            "reviews_count": 95,
            "raw_url": "https://example.com/?utm_source=google&utm_medium=gmb",
        },
        {
            "place_id": "mock_place_004",
            "business_name": "GreenLeaf Lawn Care",
            "city": "San Antonio, TX",
            "industry": "Landscaping",
            "phone": "(210) 555-0133",
            "address": "1040 Broadway, San Antonio, TX 78215",
            "rating": 4.6,
            "reviews_count": 78,
            "raw_url": "https://httpbin.org/status/404",
        },
        {
            "place_id": "mock_place_005",
            "business_name": "Service Experts Heating & Air",
            "city": "Miami, FL",
            "industry": "HVAC",
            "phone": "(305) 555-0199",
            "address": "8325 NW 64th St, Miami, FL 33166",
            "rating": 4.5,
            "reviews_count": 410,
            "raw_url": "https://example.org",
        },
    ]

    candidates: List[RawCandidate] = []
    for item in raw_items:
        clean_url, prefilled_socials, is_agg = discovery.classify_candidate_url(item["raw_url"])
        if is_agg:
            clean_url = None
        domain = discovery.extract_root_domain(clean_url)
        candidates.append(
            RawCandidate(
                place_id=item["place_id"],
                business_name=item["business_name"],
                city=item["city"],
                industry=item["industry"],
                phone=item["phone"],
                address=item["address"],
                rating=item["rating"],
                reviews_count=item["reviews_count"],
                is_franchise=discovery._is_franchise(item["business_name"], domain),
                website_url=clean_url,
                prefilled_socials=prefilled_socials,
            )
        )
    return candidates


def render_progress_bar(current: int, total: int, business_name: str) -> None:
    """Render a dynamic pure-ASCII progress bar in stdout."""
    bar_width = 30
    filled = int(bar_width * current / total) if total > 0 else 0
    bar = "#" * filled + "-" * (bar_width - filled)
    pct = (current / total) * 100 if total > 0 else 0.0
    color = Fore.GREEN if pct >= 80 else Fore.YELLOW if pct >= 40 else Fore.CYAN

    sys.stdout.write(
        f"\r  {color}[{bar}] {pct:5.1f}%{Style.RESET_ALL}  "
        f"({current}/{total})  {Fore.WHITE}Evaluating:{Style.RESET_ALL} {business_name[:32]:<32}"
    )
    sys.stdout.flush()
    if current == total:
        sys.stdout.write("\n")


def print_summary_table(summary: Dict[str, Any], elapsed_seconds: float) -> None:
    """Render an ASCII execution summary table."""
    print(f"\n{Fore.CYAN}+-----------------------------------------------------------+")
    print("|               PROSPECTIQ v3.0 RUN SUMMARY                 |")
    print("+-----------------------------------------------+-----------+")
    print("| Metric                                        | Value     |")
    print("+-----------------------------------------------+-----------+")
    print(f"| Leads Discovered                              | {summary['leads_discovered']:<9} |")
    print(f"| Total Leads Processed                         | {summary['total_processed']:<9} |")
    ins_upd_cell = f"{summary['leads_inserted']}/{summary['leads_updated']}"
    print(f"| Leads Inserted / Updated                      | {ins_upd_cell:<9} |")
    print(f"| Hot Agency Pitches (80+ Score)                | {summary['hot_pitches']:<9} |")
    print(f"| Warm Agency Pitches (50-79 Score)             | {summary['warm_pitches']:<9} |")
    print(f"| Websites Live                                 | {summary['website_live']:<9} |")
    print(f"| Websites WAF Protected (403/CF)               | {summary['website_waf']:<9} |")
    print(f"| No Website / Broken / Parked                  | {summary['website_missing']:<9} |")
    email_cell = f"{summary['email_found']} ({summary['email_mx_valid']} MX)"
    print(f"| Emails Found (MX Verified)                    | {email_cell:<9} |")
    print(f"| Social Profiles Found                         | {summary['socials_found']:<9} |")
    print(f"| Blocked Extractions                           | {summary['blocked']:<9} |")
    print(f"| API Quota Exhausted Events                    | {summary['quota_exhausted']:<9} |")
    print(f"| Skipped Duplicates (Pre-Scrape)               | {summary['skipped_duplicates']:<9} |")
    print(f"| Total Elapsed Duration                        | {elapsed_seconds:>7.2f}s   |")
    print(f"+-----------------------------------------------+-----------+{Style.RESET_ALL}\n")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ProspectIQ v3.0 -- Automated Agency Lead Intelligence Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live search discovery via SerpApi / Brave Search APIs (default: offline mock mode)",
    )
    parser.add_argument(
        "--cities",
        nargs="+",
        default=config.TARGET_CITIES,
        help="Target city or cities for discovery (supports CLI tokens, JSON array, or '|'-delimited string)",
    )
    parser.add_argument(
        "--niches",
        nargs="+",
        default=config.TARGET_NICHES,
        help="Target industry niches (supports CLI tokens, JSON array, or '|'-delimited string)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum leads to fetch per city x niche query (default: 10)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Google Maps pagination offset (e.g. 0, 20, 40) to avoid re-fetching page 1",
    )
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Cloud cron mode: pull enabled targets from Supabase prospectiq.target_queue and advance pagination cursors",
    )
    parser.add_argument(
        "--queue-limit",
        type=int,
        default=2,
        help="Maximum target_queue rows to process per --queue run (default: 2)",
    )
    parser.add_argument(
        "--job-id",
        type=str,
        default=None,
        help="Optional UUID of a pre-created QUEUED prospectiq.scrape_jobs row",
    )
    parser.add_argument(
        "--trigger-source",
        choices=["CLI", "CRON", "MANUAL_UI"],
        default="CLI",
        help="Job execution trigger label recorded in prospectiq.scrape_jobs",
    )
    return parser.parse_args(argv)


def _collect_live_candidates(
    args: argparse.Namespace,
    cities: List[str],
    niches: List[str],
) -> Tuple[List[RawCandidate], List[Tuple[str, int]], List[str], List[str], List[str]]:
    """
    Execute live discovery either from Supabase `target_queue` (`--queue`) or explicit
    `cities x niches`, returning:
      (candidates, queue_advances[(target_id, found_count)], resolved_cities, resolved_niches, errors)
    """
    candidates: List[RawCandidate] = []
    queue_advances: List[Tuple[str, int]] = []
    errors: List[str] = []

    if args.queue:
        if not database.is_cloud_enabled():
            log.warning("--queue requested without Supabase config; falling back to --cities x --niches.")
        else:
            targets = database.fetch_next_targets(limit=args.queue_limit)
            if not targets:
                log.info("No enabled rows found in prospectiq.target_queue.")
                return [], [], [], [], []

            resolved_cities = [str(t["city"]) for t in targets]
            resolved_niches = [str(t["industry"]) for t in targets]
            print(
                f"{Fore.GREEN}[MODE] Running CLOUD QUEUE MODE across {len(targets)} queued targets.{Style.RESET_ALL}"
            )
            for target in targets:
                t_city = str(target["city"])
                t_niche = str(target["industry"])
                t_offset = int(target.get("next_page_offset") or 0)
                t_max = int(target.get("max_results_per_run") or args.max_results)
                t_id = str(target["id"])
                try:
                    discovered = discovery.discover_leads(
                        city=t_city,
                        industry=t_niche,
                        max_results=t_max,
                        start=t_offset,
                    )
                    candidates.extend(discovered)
                    queue_advances.append((t_id, len(discovered)))
                except Exception as exc:
                    msg = f"Discovery error for queued {t_niche} in {t_city}: {exc}"
                    log.error(msg)
                    errors.append(msg)
            return candidates, queue_advances, resolved_cities, resolved_niches, errors

    print(
        f"{Fore.GREEN}[MODE] Running in LIVE DISCOVERY MODE across "
        f"{len(cities)} cities x {len(niches)} niches "
        f"(max={args.max_results}, start={args.start}).{Style.RESET_ALL}"
    )
    for city in cities:
        for niche in niches:
            try:
                discovered = discovery.discover_leads(
                    city=city,
                    industry=niche,
                    max_results=args.max_results,
                    start=args.start,
                )
                candidates.extend(discovered)
            except Exception as exc:
                msg = f"Discovery error for {niche} in {city}: {exc}"
                log.error(msg)
                errors.append(msg)

    return candidates, queue_advances, cities, niches, errors


def main(argv: Optional[List[str]] = None) -> None:
    print(BANNER)
    args = parse_args(argv)
    cities = _parse_multi_value_arg(args.cities)
    niches = _parse_multi_value_arg(args.niches)

    database.init_db()
    backend_label = (
        f"Supabase ({config.SUPABASE_SCHEMA})" if database.is_cloud_enabled() else "Local SQLite"
    )
    log.info(f"Database initialized successfully (backend={backend_label}).")

    summary: Dict[str, int] = {
        "leads_discovered": 0,
        "total_processed": 0,
        "leads_inserted": 0,
        "leads_updated": 0,
        "hot_pitches": 0,
        "warm_pitches": 0,
        "website_live": 0,
        "website_waf": 0,
        "website_missing": 0,
        "email_found": 0,
        "email_mx_valid": 0,
        "socials_found": 0,
        "blocked": 0,
        "quota_exhausted": 0,
        "skipped_duplicates": 0,
    }

    start_time = time.time()
    candidates: List[RawCandidate] = []
    queue_advances: List[Tuple[str, int]] = []
    errors: List[str] = []
    job_id: Optional[str] = None
    final_status = "COMPLETED"

    try:
        if not args.live:
            candidates = _build_mock_candidates()
            job_cities = sorted({c.city for c in candidates})
            job_niches = sorted({c.industry for c in candidates})
            print(
                f"{Fore.YELLOW}[MODE] Running in OFFLINE MOCK MODE ({len(candidates)} test records).{Style.RESET_ALL}"
            )
            if database.is_cloud_enabled() and args.job_id:
                job_id = database.create_scrape_job(
                    trigger_source=args.trigger_source,
                    cities=job_cities,
                    niches=job_niches,
                    max_results_per_query=args.max_results,
                    github_run_url=_get_github_run_url(),
                    job_id=args.job_id,
                )
        else:
            candidates, queue_advances, job_cities, job_niches, errors = _collect_live_candidates(
                args, cities, niches
            )
            if database.is_cloud_enabled():
                job_id = database.create_scrape_job(
                    trigger_source=args.trigger_source,
                    cities=job_cities,
                    niches=job_niches,
                    max_results_per_query=args.max_results,
                    github_run_url=_get_github_run_url(),
                    job_id=args.job_id,
                )

        total_candidates = len(candidates)
        summary["leads_discovered"] = total_candidates
        database.update_scrape_job_progress(job_id, summary)
        print(
            f"{Fore.CYAN}[QUEUE] {total_candidates} lead candidates queued for evaluation.{Style.RESET_ALL}\n"
        )

        for idx, candidate in enumerate(candidates, start=1):
            render_progress_bar(idx, total_candidates, candidate.business_name)

            # 1. Pre-Scrape Deduplication across place_id, (name, city), AND root_domain
            if database.is_duplicate(
                business_name=candidate.business_name,
                city=candidate.city,
                place_id=candidate.place_id,
                website_url=candidate.website_url,
            ):
                log.info(
                    f"Pre-scrape duplicate skipped: '{candidate.business_name}' in '{candidate.city}'."
                )
                summary["skipped_duplicates"] += 1
                database.update_scrape_job_progress(job_id, summary)
                continue

            summary["total_processed"] += 1

            # 2. Web Presence Validation + Digital Health Audit (returns HTML body)
            audit = validator.validate_url(candidate.website_url)
            if audit.website_status == "LIVE":
                summary["website_live"] += 1
            elif audit.website_status == "WAF_PROTECTED":
                summary["website_waf"] += 1
            else:
                summary["website_missing"] += 1

            # 3. Free-First Contact & Social Extraction (reuses audit.html_body!)
            contacts = extractor.extract_contacts(
                audit=audit,
                business_name=candidate.business_name,
                city=candidate.city,
                prefilled_socials=candidate.prefilled_socials,
            )

            # 4. Deterministic Agency Opportunity Scoring & Pitch Angle
            score_result = scorer.score_lead(candidate, audit, contacts)

            if score_result.pitch_tier == "HOT":
                summary["hot_pitches"] += 1
            elif score_result.pitch_tier == "WARM":
                summary["warm_pitches"] += 1
            if contacts.email:
                summary["email_found"] += 1
                if contacts.email_mx_valid:
                    summary["email_mx_valid"] += 1
            if any([contacts.linkedin, contacts.instagram, contacts.facebook, contacts.twitter]):
                summary["socials_found"] += 1
            if contacts.email_status == "BLOCKED" or contacts.social_status == "BLOCKED":
                summary["blocked"] += 1
            if contacts.email_status == "QUOTA_EXHAUSTED":
                summary["quota_exhausted"] += 1

            # 5. Assemble Strict BusinessLead Data Contract
            best_phone = candidate.phone or contacts.extracted_phone
            lead = BusinessLead(
                place_id=candidate.place_id,
                business_name=candidate.business_name,
                city=candidate.city,
                industry=candidate.industry,
                phone=best_phone,
                address=candidate.address,
                rating=candidate.rating,
                reviews_count=candidate.reviews_count,
                business_status=candidate.business_status,
                is_franchise=candidate.is_franchise,
                timestamp=datetime.now(timezone.utc).isoformat(),
                website_found=audit.website_found,
                website_status=audit.website_status,
                website_url=audit.website_url,
                root_domain=audit.root_domain,
                http_status=audit.http_status,
                has_ssl=audit.has_ssl,
                is_mobile_friendly=audit.is_mobile_friendly,
                cms_platform=audit.cms_platform,
                has_analytics=audit.has_analytics,
                has_meta_pixel=audit.has_meta_pixel,
                load_time_ms=audit.load_time_ms,
                email=contacts.email,
                email_status=contacts.email_status,
                email_mx_valid=contacts.email_mx_valid,
                secondary_emails=contacts.secondary_emails,
                linkedin=contacts.linkedin,
                instagram=contacts.instagram,
                facebook=contacts.facebook,
                twitter=contacts.twitter,
                social_status=contacts.social_status,
                opportunity_score=score_result.opportunity_score,
                pitch_tier=score_result.pitch_tier,
                pitch_angle=score_result.pitch_angle,
                pitch_summary=score_result.pitch_summary,
            )

            # 6. Persist via True UPSERT (Supabase RPC or SQLite)
            outcome = database.upsert_lead_with_status(lead, scrape_job_id=job_id)
            if outcome == "inserted":
                summary["leads_inserted"] += 1
            elif outcome == "updated":
                summary["leads_updated"] += 1
            else:
                summary["skipped_duplicates"] += 1

            database.update_scrape_job_progress(job_id, summary)

        # Advance pagination cursors for processed target_queue rows
        for target_id, found_count in queue_advances:
            try:
                database.advance_target_cursor(target_id, leads_found=found_count, page_step=20)
            except Exception as exc:
                msg = f"Failed advancing target_queue cursor {target_id}: {exc}"
                log.error(msg)
                errors.append(msg)

        if errors or summary["quota_exhausted"] > 0:
            final_status = "PARTIAL"

    except KeyboardInterrupt:
        final_status = "PARTIAL"
        errors.append("Execution halted by user (KeyboardInterrupt).")
        print(
            f"\n{Fore.RED}[INTERRUPT] Execution halted by user (Ctrl+C). Summarizing...{Style.RESET_ALL}"
        )
    except Exception as exc:
        final_status = "FAILED"
        errors.append(str(exc))
        log.error(f"Fatal orchestrator error: {exc}")
        raise
    finally:
        database.finish_scrape_job(
            job_id=job_id,
            status=final_status,
            stats=summary,
            error_summary="; ".join(errors) if errors else None,
        )
        elapsed = time.time() - start_time
        print_summary_table(summary, elapsed)


if __name__ == "__main__":
    main()
