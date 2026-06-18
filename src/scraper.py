"""Scrapling fetcher + Claude (LLM) extraction, with per-site search URLs.

The page is fetched locally with Scrapling (free, TLS-impersonating HTTP, with an
optional stealth-browser fallback for JS/anti-bot sites). The fetched HTML is then
handed to Claude, which extracts structured job listings using the schema below —
one schema for every site, no per-site selectors. This replaces Firecrawl, whose
hosted scrape+LLM-extract API required paid credits (HTTP 402 when exhausted).
"""

import os
import time
from typing import Optional
from urllib.parse import quote_plus

import lxml.html

from src import profile as _profile
from src.models import JobListing

# Cheap, fast model for structured extraction; overridable via env.
EXTRACT_MODEL = os.getenv("SOLLICITATIES_EXTRACT_MODEL", "claude-haiku-4-5")
RATE_LIMIT_DELAY = 1.5   # seconds between requests; be polite to sites + LLM rate limits
MAX_CONTEXT_CHARS = 18000  # cap page text sent to the LLM to control token cost
MIN_CONTEXT_CHARS = 200    # below this the page has no usable content; skip the LLM call

# Shared extraction schema (LLM tool input). Field descriptions guide the model.
_JOBS_SCHEMA = {
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
                        "description": "Direct link to the job detail/application page. Use the URL shown in parentheses next to the listing.",
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
}

_EXTRACT_TOOL = {
    "name": "record_jobs",
    "description": "Record every job listing found on the job-search results page.",
    "input_schema": _JOBS_SCHEMA,
}

_EXTRACT_PROMPT = (
    "You are given the visible text of a job-search results page from the Belgian job board "
    "'{site}'. Extract every distinct job listing into the record_jobs tool. Links appear in "
    "parentheses right after the listing they belong to — use them for apply_url. Only include "
    "real job vacancies (skip navigation, filters, cookie banners, ads). If the employer is not "
    "named (e.g. hidden by a recruitment agency), use the agency or the job board name '{site}' "
    "as the company — never leave company blank or 'unknown'. If another field is unknown, omit "
    "it or use an empty value. Page content follows:\n\n"
)


class ScanAbort(RuntimeError):
    """Raised on a fatal, non-recoverable API error (bad key, no credit, no access)."""


def _is_fatal_api_error(exc: Exception) -> bool:
    """True for errors where retrying other sites is pointless (auth/credit/access)."""
    if type(exc).__name__ in ("AuthenticationError", "PermissionDeniedError"):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in ("credit balance", "too low", "billing", "invalid x-api-key", "authentication"))

# ---------------------------------------------------------------------------
# Search URLs per site — Belgian job market only (see .claude/skills/belgische-jobsites/SKILL.md)
# The keyword-searchable sites below are rewritten from the uploaded CV's target
# titles at import time (see _refresh_search_urls), and LinkedIn is added via its
# guest jobs endpoint. The static URLs here are just placeholders/defaults.
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
        "https://www.robertwalters.be/nl/expertise/sales-and-marketing/marketing-communicatie-jobs.html",
    ],
    "hudson": [
        "https://www.hudsonsolutions.com/nl-be",
    ],

    # ── 3. Interim Management & Freelance Opdrachten ────────────────────
    "mindsandmore": [
        "https://mindsandmore.biz/nl/bij-ons-werken/",
    ],
    "roberthalf": [
        "https://www.roberthalf.com/be/en/jobs?query=marketing+manager",
    ],
    "randstad": [
        "https://www.randstad.be/werknemers/jobs/?q=marketing",
        "https://www.randstad.be/werknemers/jobs/",
    ],
    "adecco": [
        "https://www.adecco.be/nl-be/vacatures/resultaten?k=marketing+manager",
    ],
    "hays": [
        "https://www.hays.be/en/job-search?query=marketing+manager&location=belgium",
    ],

    # ── 4. Marketing, Communicatie & Digitale Profielen ──────────────────
    "bloovi": [
        "https://werkenbij.bloovi.be/nl/vacatures",
    ],
    "brightplus": [
        "https://www.brightplus.be/nl/vind-een-job/jobs-in-marketing-en-communicatie/",
    ],

    # ── 5. Sport, Sponsoring, Events & Entertainment ────────────────────
    "sportcareers": [
        "https://www.sportcareers.be/nl/vacatures",
    ],
    "golazo": [
        "https://www.golazo.com/jobs",
    ],

    # ── 6. Overheid & Semi-Overheid ─────────────────────────────────────
    "werkenvoor": [
        "https://werkenvoor.be/nl/jobs",
    ],
    "vlaamseoverheid": [
        "https://www.vlaanderen.be/vacatures-bij-de-vlaamse-overheid",
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
        "https://www.kbc.com/en/working-at-kbc/joining-us.html",
    ],
}


# ---------------------------------------------------------------------------
# Profile-driven search URLs.
# The sites below can be searched by keyword/title. We rebuild their URLs from
# the *uploaded CV's* target titles (src.profile) so the scan looks for the
# candidate's actual roles instead of the old hard-coded marketing terms.
# LinkedIn is added here too, via its guest jobs endpoint (HTML job cards, no
# login). LinkedIn often blocks datacenter IPs (403/429) — best effort.
# ---------------------------------------------------------------------------

# site -> (kind, url template). kind "q" = URL-encoded query, "slug" = hyphenated.
_KEYWORD_SITES: dict[str, tuple[str, str]] = {
    "indeed":      ("q",    "https://be.indeed.com/jobs?q={kw}&l=Belgium"),
    "vdab":        ("q",    "https://www.vdab.be/jobs?q={kw}&regio=_belgie"),
    "jobat":       ("slug", "https://www.jobat.be/nl/jobs/{slug}?location=belgie"),
    "stepstone":   ("slug", "https://www.stepstone.be/nl/vacature-zoeken/{slug}/"),
    "michaelpage": ("slug", "https://www.michaelpage.be/jobs/{slug}"),
    "roberthalf":  ("q",    "https://www.roberthalf.com/be/en/jobs?query={kw}"),
    "hays":        ("q",    "https://www.hays.be/en/job-search?query={kw}&location=belgium"),
    "adecco":      ("q",    "https://www.adecco.be/nl-be/vacatures/resultaten?k={kw}"),
    "randstad":    ("q",    "https://www.randstad.be/werknemers/jobs/?q={kw}"),
    "linkedin":    ("q",    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/"
                            "search?keywords={kw}&location=Belgium&start=0"),
}


# How many of the candidate's titles to search per site. Lower = faster scan
# (fewer URLs); tune live via the Space env var without a rebuild.
_TITLES_PER_SITE = int(os.getenv("SOLLICITATIES_TITLES_PER_SITE", "3"))


def _profile_search_titles(limit: int = _TITLES_PER_SITE) -> list[str]:
    """Top target titles from the active (uploaded-CV) profile."""
    titles = sorted(_profile.TARGET_TITLES)
    return titles[:limit] if titles else ["manager"]


def _refresh_search_urls() -> None:
    """Rewrite keyword-site URLs from the active profile and register LinkedIn."""
    titles = _profile_search_titles()
    for site, (kind, tmpl) in _KEYWORD_SITES.items():
        SITE_URLS[site] = [
            tmpl.format(slug=t.replace(" ", "-")) if kind == "slug" else tmpl.format(kw=quote_plus(t))
            for t in titles
        ]
    if "linkedin" not in CATEGORY_MUST_HAVE:
        CATEGORY_MUST_HAVE.append("linkedin")


_refresh_search_urls()


def _html_to_context(html: str, base_url: str) -> str:
    """Reduce a fetched HTML page to clean, link-annotated text for the LLM.

    Scripts/styles/nav-chrome are dropped; <a> hrefs are made absolute and
    appended inline as "(url)" so the model can map each listing to its
    apply_url. Output is capped to bound token cost.
    """
    try:
        doc = lxml.html.fromstring(html)
    except (ValueError, lxml.etree.ParserError):
        return ""

    doc.make_links_absolute(base_url, resolve_base_href=True)
    for bad in doc.xpath("//script | //style | //noscript | //svg | //head | //iframe"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)

    # Inline each link's href right after the anchor so locality is preserved.
    for anchor in doc.xpath("//a[@href]"):
        href = (anchor.get("href") or "").strip()
        if href and not href.lower().startswith(("javascript:", "#", "mailto:")):
            anchor.tail = f" ({href}) " + (anchor.tail or "")

    text = doc.text_content()
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)
    return cleaned[:MAX_CONTEXT_CHARS]


class ScraplingExtractor:
    """Fetch a page with Scrapling, extract job listings with Claude."""

    def __init__(self, anthropic_key: str, use_browser: bool = False):
        from anthropic import Anthropic  # imported lazily so --list etc. need no key

        self._llm = Anthropic(api_key=anthropic_key)
        self._use_browser = use_browser
        self._fetch = self._make_fetcher(use_browser)

    @staticmethod
    def _make_fetcher(use_browser: bool):
        """Pick a fetcher. Override with SOLLICITATIES_FETCHER=http|dynamic|stealth.

        - http:    fast TLS-impersonating HTTP, no browser (works on tiny servers)
        - dynamic: Playwright Chromium — reliable in Docker (recommended when hosted)
        - stealth: camoufox stealth browser — best anti-bot, heavier (local default)
        """
        from scrapling.fetchers import Fetcher

        choice = os.getenv("SOLLICITATIES_FETCHER", "").strip().lower()
        if not choice:
            choice = "stealth" if use_browser else "http"

        if choice == "http":
            return lambda url: Fetcher.get(url, timeout=30)

        if choice == "dynamic":
            try:
                from scrapling.fetchers import DynamicFetcher

                return lambda url: DynamicFetcher.fetch(url, headless=True, network_idle=True)
            except Exception:
                print("  [warn] DynamicFetcher unavailable; using HTTP fetcher.")
                return lambda url: Fetcher.get(url, timeout=30)

        try:
            from scrapling.fetchers import StealthyFetcher

            return lambda url: StealthyFetcher.fetch(url, headless=True, network_idle=True)
        except Exception:
            print("  [warn] StealthyFetcher unavailable; run `scrapling install`. Using HTTP fetcher.")
            return lambda url: Fetcher.get(url, timeout=30)

    def _fetch_html(self, url: str, source_site: str) -> Optional[str]:
        try:
            page = self._fetch(url)
        except Exception as exc:
            print(f"  [warn] {source_site} fetch error: {type(exc).__name__}: {str(exc)[:80]}")
            return None
        status = getattr(page, "status", 200)
        if status and status >= 400:
            print(f"  [warn] {source_site} HTTP {status}: {url[:70]}")
            return None
        return getattr(page, "html_content", None) or str(page)

    def _extract(self, context: str, source_site: str) -> list[dict]:
        try:
            msg = self._llm.messages.create(
                model=EXTRACT_MODEL,
                max_tokens=4096,
                tools=[_EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "record_jobs"},
                system=[{
                    "type": "text",
                    "text": "You extract structured job vacancies from raw page text. Be precise and exhaustive.",
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(site=source_site) + context}],
            )
        except Exception as exc:
            if _is_fatal_api_error(exc):
                raise ScanAbort(str(exc)[:200]) from exc
            print(f"  [warn] {source_site} LLM error: {type(exc).__name__}: {str(exc)[:90]}")
            return []
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                jobs = block.input.get("jobs", [])
                return jobs if isinstance(jobs, list) else []
        return []

    def scrape_jobs(self, url: str, source_site: str) -> list[JobListing]:
        html = self._fetch_html(url, source_site)
        if not html:
            return []
        context = _html_to_context(html, base_url=url)
        if len(context) < MIN_CONTEXT_CHARS:
            return []

        results = []
        for job in self._extract(context, source_site):
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
                    apply_url=job.get("apply_url") or url,
                    description_summary=job.get("description_summary", ""),
                )
            )
        return results

    def close(self) -> None:
        pass  # Scrapling/Anthropic clients need no explicit teardown here.


def scrape_sites(
    api_key: str,
    sites: Optional[list[str]] = None,
    verbose: bool = False,
    use_browser: bool = False,
) -> list[JobListing]:
    """Scrape all (or a subset of) job sites. Returns deduplicated listings.

    ``api_key`` is the Anthropic API key used for extraction.
    """
    client = ScraplingExtractor(api_key, use_browser=use_browser)
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
    except ScanAbort as exc:
        print(
            f"\n[FOUT] Scan afgebroken — Anthropic API niet bruikbaar:\n  {exc}\n"
            "  Voeg tegoed toe op https://console.anthropic.com (Settings -> Billing) "
            "en probeer opnieuw."
        )
    finally:
        client.close()

    return all_listings
