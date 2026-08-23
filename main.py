"""
CLI Orchestrator — main.py

Central pipeline orchestrator and CLI interface for the Lead Generation & Web Presence Validation Engine.
Single responsibility: Parse CLI arguments, orchestrate sequential execution across pipeline modules
(discovery -> validator -> extractor -> models -> database), render progress in terminal,
and display execution summary metrics.
Contains NO business logic, NO direct HTTP calls, and NO data processing.
"""

import argparse
from datetime import datetime, timezone
import sys
import time
from typing import Any, Dict, List, Optional

from colorama import Fore, Style, init as colorama_init

import config
from logger import setup_logger
import discovery
import validator
import extractor
from models import BusinessLead
import database

# Initialize colorama for ANSI terminal output formatting
colorama_init(autoreset=True)

# Logger for CLI orchestration
log = setup_logger("main")

# ASCII Banner
BANNER = f"""
{Fore.CYAN}+==================================================================+
|                                                                  |
|   {Fore.WHITE}*  Lead Generation & Web Presence Validation Engine  *{Fore.CYAN}         |
|   {Fore.YELLOW}   Muhammad Kamal -- Automated Prospecting Pipeline{Fore.CYAN}            |
|                                                                  |
+==================================================================+{Style.RESET_ALL}
"""

# Default mock businesses used when running offline without --live flag
MOCK_BUSINESSES: List[Dict[str, Optional[str]]] = [
    {
        "business_name": "Apex Plumbing Pros",
        "city": "Houston, TX",
        "industry": "Plumbing",
        "website_url": "https://example.com",
    },
    {
        "business_name": "CoolBreeze AC & Heating",
        "city": "Dallas, TX",
        "industry": "HVAC",
        "website_url": None,
    },
    {
        "business_name": "TopShield Roofing LLC",
        "city": "Austin, TX",
        "industry": "Roofing",
        "website_url": "https://httpbin.org/status/200",
    },
    {
        "business_name": "GreenLeaf Lawn Care",
        "city": "San Antonio, TX",
        "industry": "Landscaping",
        "website_url": "https://httpbin.org/status/404",
    },
    {
        "business_name": "Elite Auto Spa",
        "city": "Miami, FL",
        "industry": "Auto Detailing",
        "website_url": "https://example.org",
    },
]


def render_progress_bar(current: int, total: int, business_name: str) -> None:
    """
    Render a dynamic progress bar in stdout using pure ASCII characters.
    """
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
    """
    Render a clean, formatted ASCII table of pipeline execution summary metrics.
    """
    print(f"\n{Fore.CYAN}+-----------------------------------------------------------+")
    print(f"|                  PIPELINE EXECUTION SUMMARY               |")
    print(f"+-----------------------------------------------+-----------+")
    print(f"| Metric                                        | Value     |")
    print(f"+-----------------------------------------------+-----------+")
    print(f"| Total Leads Processed                         | {summary['total_processed']:<9} |")
    print(f"| Websites Live (200-399)                       | {summary['website_found']:<9} |")
    print(f"| Websites Dead / No URL                        | {summary['website_dead']:<9} |")
    print(f"| Email Addresses Found                         | {summary['email_found']:<9} |")
    print(f"| Social Profiles Found                         | {summary['socials_found']:<9} |")
    print(f"| Blocked Extractions (403/Cloudflare)          | {summary['blocked']:<9} |")
    print(f"| API Quota Exhausted Events                    | {summary['quota_exhausted']:<9} |")
    print(f"| Skipped Duplicate Records                     | {summary['skipped_duplicates']:<9} |")
    print(f"| Total Elapsed Duration                        | {elapsed_seconds:>7.2f}s   |")
    print(f"+-----------------------------------------------+-----------+{Style.RESET_ALL}\n")


def parse_args() -> argparse.Namespace:
    """
    Parse command line interface arguments.
    """
    parser = argparse.ArgumentParser(
        description="Lead Generation & Web Presence Validation Engine",
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
        help="Target city or cities for discovery (e.g. 'Houston, TX' 'Dallas, TX')",
    )
    parser.add_argument(
        "--niches",
        nargs="+",
        default=config.TARGET_NICHES,
        help="Target industry niches (e.g. 'Plumbing' 'HVAC' 'Roofing')",
    )
    return parser.parse_args()


def main() -> None:
    """
    Pipeline orchestrator execution entrypoint.
    """
    print(BANNER)
    args = parse_args()

    # Step 1: Initialize database schema at startup before processing
    database.init_db()
    log.info("Database initialized successfully.")

    summary = {
        "total_processed": 0,
        "website_found": 0,
        "website_dead": 0,
        "email_found": 0,
        "socials_found": 0,
        "blocked": 0,
        "quota_exhausted": 0,
        "skipped_duplicates": 0,
    }

    start_time = time.time()

    # Gather lead candidates
    candidates: List[Dict[str, Optional[str]]] = []

    if not args.live:
        print(f"{Fore.YELLOW}[MODE] Running in OFFLINE MOCK MODE ({len(MOCK_BUSINESSES)} test records).{Style.RESET_ALL}")
        candidates = MOCK_BUSINESSES.copy()
    else:
        print(f"{Fore.GREEN}[MODE] Running in LIVE DISCOVERY MODE across {len(args.cities)} cities and {len(args.niches)} niches.{Style.RESET_ALL}")
        for city in args.cities:
            for niche in args.niches:
                try:
                    discovered = discovery.discover_leads(city=city, industry=niche)
                    candidates.extend(discovered)
                except Exception as exc:
                    log.error(f"Discovery error for {niche} in {city}: {exc}")

    total_candidates = len(candidates)
    print(f"{Fore.CYAN}[QUEUE] {total_candidates} lead candidates queued for evaluation.{Style.RESET_ALL}\n")

    try:
        for idx, item in enumerate(candidates, start=1):
            biz_name = item.get("business_name") or "Unknown Business"
            city = item.get("city") or "Unknown City"
            industry = item.get("industry") or "General Service"
            raw_url = item.get("website_url")

            render_progress_bar(idx, total_candidates, biz_name)

            # 1. Early Deduplication Check via database.py
            if database.is_duplicate(biz_name, city):
                log.info(f"Duplicate lead detected: '{biz_name}' in '{city}'. Skipping.")
                summary["skipped_duplicates"] += 1
                continue

            summary["total_processed"] += 1

            # 2. Web Presence Validation via validator.py
            val_result = validator.validate_url(raw_url)
            is_live = val_result.get("website_found", False)
            resolved_url = val_result.get("website_url")
            http_status = val_result.get("http_status")

            if is_live:
                summary["website_found"] += 1
            else:
                summary["website_dead"] += 1

            # 3. Contact Extraction via extractor.py
            if is_live and resolved_url:
                ext_result = extractor.extract_contacts(
                    website_url=resolved_url,
                    business_name=biz_name,
                    city=city,
                )
            else:
                # Extractor is not reached if website is dead/not found
                ext_result = {
                    "email": None,
                    "email_status": "NOT_ATTEMPTED",
                    "linkedin": None,
                    "instagram": None,
                    "facebook": None,
                    "twitter": None,
                    "social_status": "NOT_ATTEMPTED",
                }

            email = ext_result.get("email")
            email_status = ext_result.get("email_status", "NOT_ATTEMPTED")
            linkedin = ext_result.get("linkedin")
            instagram = ext_result.get("instagram")
            facebook = ext_result.get("facebook")
            twitter = ext_result.get("twitter")
            social_status = ext_result.get("social_status", "NOT_ATTEMPTED")

            # Update metrics
            if email:
                summary["email_found"] += 1
            if any([linkedin, instagram, facebook, twitter]):
                summary["socials_found"] += 1
            if email_status == "BLOCKED" or social_status == "BLOCKED":
                summary["blocked"] += 1
            if email_status == "QUOTA_EXHAUSTED" or social_status == "QUOTA_EXHAUSTED":
                summary["quota_exhausted"] += 1

            # 4. Assemble strict BusinessLead model via models.py
            current_timestamp = datetime.now(timezone.utc).isoformat()
            lead = BusinessLead(
                business_name=biz_name,
                city=city,
                industry=industry,
                timestamp=current_timestamp,
                website_found=is_live,
                website_url=resolved_url if resolved_url else None,
                http_status=http_status,
                email=email,
                email_status=email_status,
                linkedin=linkedin,
                instagram=instagram,
                facebook=facebook,
                twitter=twitter,
                social_status=social_status,
            )

            # 5. Persist to SQLite via database.py
            database.upsert_lead(lead)

    except KeyboardInterrupt:
        print(f"\n{Fore.RED}[INTERRUPT] Execution halted by user (Ctrl+C). Flushing pending data and summarizing...{Style.RESET_ALL}")
    finally:
        elapsed = time.time() - start_time
        print_summary_table(summary, elapsed)


if __name__ == "__main__":
    main()
