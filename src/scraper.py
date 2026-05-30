"""Firecrawl API client and per-site search URL builders."""

import time
from typing import Optional

import httpx

from src.models import JobListing

FIRECRAWL_BASE = "https://api.firecrawl.dev/v2"
RATE_LIMIT_DELAY = 2.5   # seconds between requests; respects Firecrawl free-tier limits
MAX_RETRIES = 2

# Firecrawl v2: formats is an array of objects; 'json' type with schema does LLM extraction.
# No separate extract key or systemPrompt — descriptions in the schema guide the LLM.
_JSON_FORMAT = {
    "type": "json",
    "schema": {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "description": "All job listings visible on this job search results page",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Job title"},
                        "company": {"type": "string", "description": "Employer name"},
                        "location": {"type": "string", "description": "City and/or country"},
                        "remote": {
                            "type": "string",
                            "enum": ["remote", "hybrid", "onsite", "unknown"],
                            "description": "remote=fully remote, hybrid=flexible, onsite=office-only, unknown=not stated",
                        },
                        "experience_level": {
                            "type": "string",
                            "description": "e.g. senior, mid-level, junior, director",
                        },
                        "languages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Every language explicitly required or preferred",
                        },
                        "skills": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key skills and competencies mentioned",
                        },
                        "posted_date": {
                            "type": "string",
                            "description": "When the role was posted, as written on the page",
                        },
                        "apply_url": {
                            "type": "string",
                            "description": "Direct link to the job detail or application page",
                        },
                        "description_summary": {
                            "type": "string",
                            "description": "2-3 sentence summary of the role responsibilities",
                        },
                    },
                    "required": ["title", "company"],
                },
            }
        },
        "required": ["jobs"],
    },
}

# ---------------------------------------------------------------------------
# Search URLs per site — Belgian job market only (see .claude/skills/belgische-jobsites/SKILL.md)
# LinkedIn blocks all scrapers (403); use manually via browser.
# ---------------------------------------------------------------------------

# Categorised site groups for selective scanning
CATEGORY_MUST_HAVE = ["jobat", "indeed", "vdab", "stepstone"]
CATEGORY_SENIOR = ["michaelpage", "robertwalters", "hudson", "hays"]
CATEGORY_INTERIM = ["mindsandmore", "roberthalf", "randstad", "adecco"]
CATEGORY_MARKETING = ["bloovi", "brightplus"]
CATEGORY_SPORT = ["sportcareers", "golazo"]
CATEGORY_OVERHEID = ["werkenvoor", "vlaamseoverheid", "stadgent"]
CATEGORY_BEDRIJVEN = ["belfius", "telenet", "proximus", "colruyt", "kbc"]

ALL_CATEGORIES: dict[str, list[str]] = {
    "must_have": CATEGORY_MUST_HAVE,
    "senior": CATEGORY_SENIOR,
    "interim": CATEGORY_INTERIM,
    "marketing": CATEGORY_MARKETING,
    "sport": CATEGORY_SPORT,
    "overheid": CATEGORY_OVERHEID,
    "bedrijven": CATEGORY_BEDRIJVEN,
}

SITE_URLS: dict[str, list[str]] = {
    # ── 1. Must-Have Platforms (dagelijks monitoren) ──────────────────────
    "jobat": [
        "https://www.jobat.be/nl/jobs/marketing-manager?location=belgie",
        "https://www.jobat.be/nl/jobs/brand-manager?location=belgie",
        "https://www.jobat.be/nl/jobs/hoofd-marketing?location=belgie",
        "https://www.jobat.be/nl/jobs/marketing-director?location=belgie",
        "https://www.jobat.be/nl/jobs/sponsorship-manager?location=belgie",
    ],
    "indeed": [
        "https://be.indeed.com/jobs?q=marketing+manager&l=Belgium",
        "https://be.indeed.com/jobs?q=brand+manager&l=Belgium",
        "https://be.indeed.com/jobs?q=head+of+marketing&l=Belgium",
        "https://be.indeed.com/jobs?q=sponsorship+manager&l=Belgium",
        "https://be.indeed.com/jobs?q=marketing+director&l=Belgium",
    ],
    "vdab": [
        "https://www.vdab.be/jobs?q=marketing+manager&regio=_belgie",
        "https://www.vdab.be/jobs?q=brand+manager&regio=_belgie",
        "https://www.vdab.be/jobs?q=marketing+director&regio=_belgie",
        "https://www.vdab.be/jobs?q=hoofd+marketing&regio=_belgie",
    ],
    "stepstone": [
        "https://www.stepstone.be/nl/vacature-zoeken/marketing-manager/",
        "https://www.stepstone.be/nl/vacature-zoeken/brand-manager/",
        "https://www.stepstone.be/nl/vacature-zoeken/hoofd-marketing/",
        "https://www.stepstone.be/nl/vacature-zoeken/marketing-director/",
    ],

    # ── 2. Senior, Management & Directiefuncties ────────────────────────
    "michaelpage": [
        "https://www.michaelpage.be/jobs/marketing-manager",
        "https://www.michaelpage.be/jobs/marketing-director",
        "https://www.michaelpage.be/jobs/head-of-marketing",
    ],
    "robertwalters": [
        "https://www.robertwalters.be/marketing-jobs.html",
    ],
    "hudson": [
        "https://www.hudsonsolutions.com/be-nl/jobs?q=marketing",
    ],

    # ── 3. Interim Management & Freelance Opdrachten ────────────────────
    "mindsandmore": [
        "https://www.mindsandmore.be/nl/opdrachten?q=marketing",
    ],
    "roberthalf": [
        "https://www.roberthalf.com/be/en/jobs?query=marketing+manager",
    ],
    "randstad": [
        "https://www.randstad.be/nl/jobs/q-marketing+manager/",
        "https://www.randstad.be/nl/jobs/q-marketing+director/",
    ],
    "adecco": [
        "https://www.adecco.be/nl-be/vacatures/resultaten?k=marketing+manager",
    ],
    "hays": [
        "https://www.hays.be/en/job-search?query=marketing+manager&location=belgium",
    ],

    # ── 4. Marketing, Communicatie & Digitale Profielen ──────────────────
    "bloovi": [
        "https://www.bloovi.be/jobs?q=marketing",
    ],
    "brightplus": [
        "https://www.brightplus.be/vacatures?q=marketing",
    ],

    # ── 5. Sport, Sponsoring, Events & Entertainment ────────────────────
    "sportcareers": [
        "https://www.sportcareers.be/vacatures",
    ],
    "golazo": [
        "https://www.golazo.com/jobs",
    ],

    # ── 6. Overheid & Semi-Overheid ─────────────────────────────────────
    "werkenvoor": [
        "https://www.werkenvoor.be/nl/vacatures?q=marketing",
        "https://www.werkenvoor.be/nl/vacatures?q=communicatie",
    ],
    "vlaamseoverheid": [
        "https://www.vlaanderen.be/vacatures-bij-de-vlaamse-overheid?trefwoord=marketing",
    ],
    "stadgent": [
        "https://jobs.stad.gent",
    ],

    # ── 8. Bedrijven Rechtstreeks ───────────────────────────────────────
    "belfius": [
        "https://jobs.belfius.be",
    ],
    "telenet": [
        "https://jobs.telenet.be",
    ],
    "proximus": [
        "https://jobs.proximus.com",
    ],
    "colruyt": [
        "https://jobs.colruytgroup.com",
    ],
    "kbc": [
        "https://www.kbc.com/en/careers.html",
    ],
}


class FirecrawlClient:
    def __init__(self, api_key: str):
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._http = httpx.Client(timeout=90.0)

    def scrape_jobs(self, url: str, source_site: str) -> list[JobListing]:
        payload = {
            "url": url,
            "formats": [_JSON_FORMAT],
        }

        for attempt in range(MAX_RETRIES):
            try:
                resp = self._http.post(
                    f"{FIRECRAWL_BASE}/scrape",
                    headers=self._headers,
                    json=payload,
                )
                if resp.status_code == 429:
                    wait = 8 * (attempt + 1)
                    print(f"  [rate-limit] waiting {wait}s before retry...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return self._parse(resp.json(), source_site, url)
            except httpx.HTTPStatusError as exc:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(3)
                    continue
                print(f"  [warn] {source_site} HTTP {exc.response.status_code}: {url[:70]}")
                return []
            except Exception as exc:
                print(f"  [warn] {source_site} error: {exc}")
                return []
        return []

    def _parse(self, data: dict, source_site: str, fallback_url: str) -> list[JobListing]:
        try:
            raw_jobs: list[dict] = (
                data.get("data", {}).get("json", {}).get("jobs", [])
            )
        except AttributeError:
            return []

        results = []
        for job in raw_jobs:
            title = (job.get("title") or "").strip()
            company = (job.get("company") or "").strip()
            if not title or not company:
                continue
            results.append(
                JobListing(
                    title=title,
                    company=company,
                    location=(job.get("location") or "").strip(),
                    source_site=source_site,
                    remote=job.get("remote", "unknown"),
                    experience_level=job.get("experience_level", ""),
                    languages=job.get("languages") or [],
                    skills=job.get("skills") or [],
                    posted_date=job.get("posted_date", ""),
                    apply_url=job.get("apply_url") or fallback_url,
                    description_summary=job.get("description_summary", ""),
                )
            )
        return results

    def close(self) -> None:
        self._http.close()


def scrape_sites(
    api_key: str,
    sites: Optional[list[str]] = None,
    verbose: bool = False,
) -> list[JobListing]:
    """Scrape all (or a subset of) job sites. Returns deduplicated listings."""
    client = FirecrawlClient(api_key)
    target_sites = sites or list(SITE_URLS.keys())
    all_listings: list[JobListing] = []
    seen: set[str] = set()

    try:
        for site in target_sites:
            urls = SITE_URLS.get(site)
            if not urls:
                print(f"[warn] Unknown site key: '{site}'. Valid: {', '.join(SITE_URLS)}")
                continue

            print(f"\n[{site}] scraping {len(urls)} search URL(s)...")
            site_count = 0

            for url in urls:
                if verbose:
                    print(f"  -> {url}")
                listings = client.scrape_jobs(url, site)
                new = 0
                for listing in listings:
                    key = f"{listing.title.lower()}|||{listing.company.lower()}"
                    if key not in seen:
                        seen.add(key)
                        all_listings.append(listing)
                        new += 1
                if verbose:
                    print(f"    {len(listings)} found, {new} new (deduped)")
                site_count += new
                time.sleep(RATE_LIMIT_DELAY)

            print(f"  [{site}] total unique: {site_count}")
    finally:
        client.close()

    return all_listings
