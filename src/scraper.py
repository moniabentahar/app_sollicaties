"""Firecrawl API client and per-site search URL builders."""

import time
from typing import Optional

import httpx

from src.models import JobListing

FIRECRAWL_BASE = "https://api.firecrawl.dev/v2"
RATE_LIMIT_DELAY = 2.5   # seconds between requests; respects Firecrawl free-tier limits
MAX_RETRIES = 2

# JSON schema sent to Firecrawl's LLM extract — no HTML parsing needed.
_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "remote": {
                        "type": "string",
                        "enum": ["remote", "hybrid", "onsite", "unknown"],
                    },
                    "experience_level": {"type": "string"},
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "All language requirements mentioned in the listing",
                    },
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key skills and competencies listed",
                    },
                    "posted_date": {
                        "type": "string",
                        "description": "When the role was posted, as written on the page",
                    },
                    "apply_url": {
                        "type": "string",
                        "description": "Direct URL to apply or to the job detail page",
                    },
                    "description_summary": {
                        "type": "string",
                        "description": "2-3 sentence summary of the role responsibilities",
                    },
                },
                "required": ["title", "company", "location"],
            },
        }
    },
    "required": ["jobs"],
}

_EXTRACT_SYSTEM_PROMPT = (
    "You are extracting job listings from a job board search results page. "
    "Extract every visible job listing on the page. "
    "For the 'remote' field: use 'remote' if fully remote, 'hybrid' if hybrid/flexible, "
    "'onsite' if office-only, 'unknown' if not stated. "
    "For 'languages': list every language explicitly required or preferred. "
    "For 'apply_url': prefer the direct job-detail link over the search page URL."
)

# Search URLs per site — one entry per query variant.
# LinkedIn experience filter: 4=Associate, 5=Mid-Senior, 6=Director
SITE_URLS: dict[str, list[str]] = {
    "linkedin": [
        "https://www.linkedin.com/jobs/search/?keywords=marketing+manager&location=Belgium&f_E=4%2C5%2C6",
        "https://www.linkedin.com/jobs/search/?keywords=brand+manager&location=Belgium&f_E=4%2C5%2C6",
        "https://www.linkedin.com/jobs/search/?keywords=head+of+marketing&location=Belgium&f_E=5%2C6",
        "https://www.linkedin.com/jobs/search/?keywords=sponsorship+manager&location=Belgium",
        "https://www.linkedin.com/jobs/search/?keywords=CMO+Belgium",
        "https://www.linkedin.com/jobs/search/?keywords=marketing+director&location=Belgium&f_E=5%2C6",
    ],
    "indeed": [
        "https://be.indeed.com/jobs?q=marketing+manager&l=Belgium&sc=0kf%3Aexplvl%28SENIOR_LEVEL%29%3B",
        "https://be.indeed.com/jobs?q=brand+manager&l=Belgium&sc=0kf%3Aexplvl%28SENIOR_LEVEL%29%3B",
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
        "https://www.stepstone.be/nl/jobs/marketing-manager/?radius=100&location=Belgium",
        "https://www.stepstone.be/nl/jobs/brand-manager/?radius=100&location=Belgium",
        "https://www.stepstone.be/nl/jobs/head-of-marketing/?radius=100",
        "https://www.stepstone.be/nl/jobs/sponsorship-manager/?radius=100",
        "https://www.stepstone.be/nl/jobs/marketing-director/?radius=100",
    ],
    "wtj": [
        "https://www.welcometothejungle.com/en/jobs?refinementList%5Boffice_country_codes%5D%5B%5D=BE&query=marketing+manager",
        "https://www.welcometothejungle.com/en/jobs?refinementList%5Boffice_country_codes%5D%5B%5D=BE&query=brand+manager",
        "https://www.welcometothejungle.com/en/jobs?refinementList%5Boffice_country_codes%5D%5B%5D=BE&query=head+of+marketing",
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
            "formats": ["extract"],
            "extract": {
                "schema": _EXTRACT_SCHEMA,
                "systemPrompt": _EXTRACT_SYSTEM_PROMPT,
            },
            "actions": [
                # Accept cookie banners that would otherwise block content
                {"type": "wait", "milliseconds": 2000},
            ],
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
                data.get("data", {}).get("extract", {}).get("jobs", [])
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
                    print(f"  → {url}")
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
