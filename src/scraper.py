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
MAX_CONTEXT_CHARS = int(os.getenv("SOLLICITATIES_MAX_CONTEXT", "40000"))  # cap page text to the LLM; big boards (Indeed) need more to reach the listings
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
CATEGORY_MUST_HAVE = ["michaelpage", "roberthalf", "hays"]
CATEGORY_SENIOR = ["robertwalters", "hudson"]
CATEGORY_INTERIM = ["mindsandmore"]
CATEGORY_OVERHEID = ["werkenvoor", "stadgent"]
CATEGORY_BEDRIJVEN = ["belfius", "telenet", "proximus", "colruyt", "kbc"]
# KMO's met een eigen vacaturepagina in platte HTML (scanbaar via gewone HTTP).
CATEGORY_KMO = ["dsmkeukens"]

ALL_CATEGORIES: dict[str, list[str]] = {
    "must_have": CATEGORY_MUST_HAVE,
    "senior": CATEGORY_SENIOR,
    "interim": CATEGORY_INTERIM,
    "overheid": CATEGORY_OVERHEID,
    "bedrijven": CATEGORY_BEDRIJVEN,
    "kmo": CATEGORY_KMO,
}

SITE_URLS: dict[str, list[str]] = {
    # ── 1. Must-Have: Headhunters (keyword-driven, rebuilt from profile) ─
    # Placeholders — overwritten at startup by _refresh_search_urls()
    "michaelpage": [
        "https://www.michaelpage.be/jobs/operations-manager",
        "https://www.michaelpage.be/jobs/plant-manager",
        "https://www.michaelpage.be/jobs/general-manager",
    ],
    "roberthalf": [
        "https://www.roberthalf.com/be/en/jobs?query=operations+manager",
    ],
    "hays": [
        "https://www.hays.be/en/job-search?query=operations+manager&location=belgium",
    ],

    # ── 2. Senior & Executive Search ────────────────────────────────────
    "robertwalters": [
        "https://www.robertwalters.be/nl/expertise/supply-chain-operations/supply-chain-jobs.html",
        "https://www.robertwalters.be/nl/expertise/engineering-manufacturing/engineering-jobs.html",
    ],
    "hudson": [
        "https://www.hudsonsolutions.com/nl-be",
    ],

    # ── 3. Interim Management ───────────────────────────────────────────
    "mindsandmore": [
        "https://mindsandmore.biz/nl/bij-ons-werken/",
    ],

    # ── 4. Overheid & Semi-Overheid ─────────────────────────────────────
    "werkenvoor": [
        "https://werkenvoor.be/nl/jobs",
    ],
    "stadgent": [
        "https://jobs.gent.be/",
    ],

    # ── 5. Bedrijven Rechtstreeks ───────────────────────────────────────
    "belfius": [
        "https://jobs.belfius.be",
    ],
    "telenet": [
        "https://www2.telenet.be/corporate/nl/careers.html",
    ],
    "proximus": [
        "https://jobs.proximus.com/be/en",
    ],
    "colruyt": [
        "https://jobs.colruytgroup.com/nl",
    ],
    "kbc": [
        "https://www.kbc.com/en/working-at-kbc/joining-us.html",
    ],

    # ── 6. KMO's Rechtstreeks (eigen vacaturepagina, platte HTML) ───────
    "dsmkeukens": [
        "https://www.dsmkeukens.be/vacatures/",
    ],
    # careersite.be platform (platte HTML) — gebruikt door veel BE werkgevers/vzw's
    "ebergiste": [
        "https://ebergiste.careersite.be/nl",
    ],
    "yust": [
        "https://yust.com/jobs/",
    ],

    # ── 7. Oracle Recruiting Cloud sites (JS careers pages → JSON API) ──
    # The careers page is a JS SPA (no extractable HTML), but its requisitions
    # are served as clean JSON. We parse that directly (no LLM) — see
    # _ORACLE_ORC_SITES and _fetch_oracle_orc.
    "wyre": [
        "https://ebza.fa.em2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        "?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values"
        "&finder=findReqs;siteNumber=CX_3001,limit=200,sortBy=POSTING_DATES_DESC",
    ],
}

# Oracle Recruiting Cloud sites: slug -> employer label. Their SITE_URLS entry is
# the JSON requisitions API; jobs are parsed directly from JSON (no LLM call).
_ORACLE_ORC_SITES: dict[str, str] = {
    "wyre": "Wyre (Joint Venture Telenet x Fluvius)",
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
# Only sites confirmed to return job-listing HTML via plain HTTP GET are listed here.
_KEYWORD_SITES: dict[str, tuple[str, str]] = {
    "michaelpage": ("slug", "https://www.michaelpage.be/jobs/{slug}"),
    "roberthalf":  ("q",    "https://www.roberthalf.com/be/en/jobs?query={kw}"),
    "hays":        ("q",    "https://www.hays.be/en/job-search?query={kw}&location=belgium"),
    # LinkedIn guest API: unauthenticated, returns structured HTML job cards; needs stealth fetcher.
    "linkedin":    ("q",    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={kw}&location=Belgium&start=0"),
    # indeed/vdab/jobat: page loads (200) but the jobs live in JavaScript/JSON,
    # not in extractable text — generic extraction yields 0. Would need per-site
    # JSON parsing. Excluded for now.
    # stepstone: ERR_HTTP2 / connection reset (blocked)
    # adecco: .be domain redirects all search queries to .com homepage
    # randstad: JS-rendered listings — context shows navigation only
}

# Sites that need a specific fetcher regardless of the global SOLLICITATIES_FETCHER.
_SITE_FETCHER_OVERRIDES: dict[str, str] = {
    "linkedin": "stealth",  # guest API passes bot checks with browser fingerprint
}


# How many of the candidate's titles to search per site. Lower = faster scan
# (fewer URLs); tune live via the Space env var without a rebuild.
_TITLES_PER_SITE = int(os.getenv("SOLLICITATIES_TITLES_PER_SITE", "3"))


# Broad, high-yield titles searched first. Alphabetical order would push the
# most important roles (e.g. "marketing manager", "marketing director") out of
# the top-N and miss most jobs — these terms pull them to the front instead.
_PRIORITY_TERMS = (
    "marketing manager",
    "marketing director",
    "head of marketing",
    "brand manager",
    "marketing communication",
    "communication manager",
    "marketing",
    "brand",
    "head of",
    "manager",
)


def _title_priority(title: str) -> int:
    t = title.lower()
    for i, term in enumerate(_PRIORITY_TERMS):
        if term in t:
            return i
    return len(_PRIORITY_TERMS)


# Always searched, even if not in the top-N profile titles — the candidate
# explicitly wants sponsorship and partnership roles covered.
_ALWAYS_INCLUDE = ("sponsorship manager", "partnership manager")

# LinkedIn is searched on this broad marketing/communication/sponsoring field
# (not just the CV's exact titles) so we surface everything interesting around
# the domain, even when a title isn't a 100% match. Each term is one guest-API
# query; the domain gate in filters.py then keeps the results on-topic.
_LINKEDIN_FIELD_TERMS = (
    "marketing manager", "marketing director", "head of marketing",
    "brand manager", "product marketing manager", "trade marketing",
    "communicatie manager", "communications manager", "content manager",
    "social media manager", "digital marketing", "growth manager",
    "campaign manager", "event manager", "employer branding",
    "sponsorship manager", "partnership manager", "pr manager",
)

# Executive-search / recruitment firms the candidate wants covered. Most have
# JS-rendered sites that don't list publicly, but their postings appear on
# LinkedIn — so we search LinkedIn by firm name and let the marketing domain
# gate keep only the relevant roles. (Robert Half/Walters/Michael Page/Hays are
# already direct sources.)
_LINKEDIN_FIRM_TERMS = (
    "Batenborch", "Stanton Chase", "SpenglerFox", "Russell Reynolds",
    "Korn Ferry", "Ingenium Executive Search", "Altior", "Embark",
)

# Specific employers the candidate wants covered. Their jobs (incl. sponsoring/
# marketing) appear on LinkedIn; we search by company name and let the domain
# gate keep the relevant ones. Add new ones here as requested.
_LINKEDIN_COMPANY_TERMS = (
    "Leonidas", "Herbalife", "Vlerick", "Baloise",
)


def _profile_search_titles(limit: int = _TITLES_PER_SITE) -> list[str]:
    """Most relevant target titles from the active (uploaded-CV) profile.

    Sorted by marketing relevance (not alphabetically) so the broad, high-yield
    titles like 'marketing manager' / 'marketing director' are always searched,
    plus guaranteed sponsorship/partnership coverage.
    """
    titles = sorted(_profile.TARGET_TITLES, key=lambda t: (_title_priority(t), t))
    chosen = titles[:limit] if titles else ["marketing manager"]
    for extra in _ALWAYS_INCLUDE:
        keyword = extra.split()[0]  # "sponsorship" / "partnership"
        if not any(keyword in t.lower() for t in chosen):
            chosen.append(extra)
    return chosen


def _refresh_search_urls() -> None:
    """Rewrite keyword-site URLs. LinkedIn uses the broad marketing/communication
    field list; the other keyword sites use the active CV's target titles."""
    titles = _profile_search_titles()
    for site, (kind, tmpl) in _KEYWORD_SITES.items():
        terms = (_LINKEDIN_FIELD_TERMS + _LINKEDIN_FIRM_TERMS + _LINKEDIN_COMPANY_TERMS) if site == "linkedin" else titles
        SITE_URLS[site] = [
            tmpl.format(slug=t.replace(" ", "-")) if kind == "slug" else tmpl.format(kw=quote_plus(t))
            for t in terms
        ]


_refresh_search_urls()


def _clean_apply_url(u: str, source_site: str) -> str:
    """Strip tracking query params from LinkedIn job URLs — the long
    ?position=&trackingId= tails can trigger redirect/blocking issues."""
    if u and source_site == "linkedin" and "?" in u:
        return u.split("?", 1)[0]
    return u


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


def _fetch_oracle_orc(api_url: str, company: str, source_site: str) -> list[JobListing]:
    """Parse an Oracle Recruiting Cloud requisitions JSON API into listings.

    Oracle career sites render jobs via JavaScript (no extractable HTML), but the
    underlying ``recruitingCEJobRequisitions`` endpoint returns clean JSON. We read
    it directly — exact, fast, and free (no LLM call). The job-detail URL is rebuilt
    from the API host + the ``siteNumber`` embedded in the query.
    """
    import json
    import re
    import urllib.request
    from urllib.parse import urlparse

    host = urlparse(api_url).netloc
    m = re.search(r"siteNumber=([^,&;]+)", api_url)
    site_number = m.group(1) if m else ""
    detail_base = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site_number}/job/"

    req = urllib.request.Request(
        api_url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  [warn] {source_site} Oracle API error: {type(exc).__name__}: {str(exc)[:80]}")
        return []

    items = data.get("items") or []
    reqs = items[0].get("requisitionList", []) if items else []
    out: list[JobListing] = []
    for r in reqs:
        title = (r.get("Title") or "").strip()
        if not title:
            continue
        out.append(
            JobListing(
                title=title,
                company=company,
                location=(r.get("PrimaryLocation") or "").strip(),
                source_site=source_site,
                remote="unknown",
                experience_level="",
                languages=[],
                skills=[],
                posted_date=(r.get("PostedDate") or "").strip(),
                apply_url=f"{detail_base}{r.get('Id')}" if r.get("Id") else api_url,
                description_summary="",
            )
        )
    return out


class ScraplingExtractor:
    """Fetch a page with Scrapling, extract job listings with Claude."""

    def __init__(self, anthropic_key: str, use_browser: bool = False):
        from anthropic import Anthropic  # imported lazily so --list etc. need no key

        self._llm = Anthropic(api_key=anthropic_key)
        self._use_browser = use_browser
        self._fetch = self._make_fetcher(use_browser)
        self._site_fetchers: dict[str, object] = {
            site: self._make_fetcher(fetcher_name == "stealth")
            for site, fetcher_name in _SITE_FETCHER_OVERRIDES.items()
        }

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
        fetch = self._site_fetchers.get(source_site, self._fetch)
        try:
            page = fetch(url)
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
        # Oracle Recruiting Cloud sites are parsed straight from their JSON API.
        if source_site in _ORACLE_ORC_SITES:
            return _fetch_oracle_orc(url, _ORACLE_ORC_SITES[source_site], source_site)

        html = self._fetch_html(url, source_site)
        if not html:
            return []
        context = _html_to_context(html, base_url=url)
        print(f"    [ctx] html={len(html)}ch context={len(context)}ch url={url[:70]}")
        if len(context) < MIN_CONTEXT_CHARS:
            print(f"    [skip] context too short ({len(context)}<{MIN_CONTEXT_CHARS}) — blocked/empty page?")
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
                    apply_url=_clean_apply_url(job.get("apply_url") or url, source_site),
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
    """Scrape all (or a subset of) job sites concurrently. Returns deduplicated listings.

    Every (site, search-URL) pair is fetched + extracted in parallel via a bounded
    thread pool, which cuts wall-clock time several-fold versus scraping one by one.
    Tune the pool with SOLLICITATIES_CONCURRENCY (default 6). ``api_key`` is the
    Anthropic key used for extraction.
    """
    import concurrent.futures

    client = ScraplingExtractor(api_key, use_browser=use_browser)
    target_sites = sites or list(SITE_URLS.keys())

    # Flatten to (site, url) jobs.
    jobs: list[tuple[str, str]] = []
    for site in target_sites:
        urls = SITE_URLS.get(site)
        if not urls:
            print(f"[warn] Unknown site key: '{site}'. Valid: {', '.join(SITE_URLS)}")
            continue
        jobs.extend((site, url) for url in urls)

    workers = max(1, int(os.getenv("SOLLICITATIES_CONCURRENCY", "6")))
    print(f"[scan] {len(jobs)} URL(s) across {len(target_sites)} site(s), concurrency={workers}", flush=True)

    all_listings: list[JobListing] = []
    seen: set[str] = set()
    aborted: Optional[ScanAbort] = None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(client.scrape_jobs, url, site): (site, url) for site, url in jobs}
            for fut in concurrent.futures.as_completed(futures):
                site, url = futures[fut]
                try:
                    listings = fut.result()
                except ScanAbort as exc:
                    aborted = exc
                    break
                except Exception as exc:  # one bad URL must not sink the whole scan
                    print(f"  [warn] {site} task error: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
                    continue
                new = 0
                for listing in listings:
                    key = f"{listing.title.lower()}|||{listing.company.lower()}"
                    if key not in seen:
                        seen.add(key)
                        all_listings.append(listing)
                        new += 1
                if verbose:
                    print(f"  [{site}] {len(listings)} found, {new} new  <- {url[:60]}", flush=True)
    finally:
        client.close()

    if aborted is not None:
        print(
            f"\n[FOUT] Scan afgebroken — Anthropic API niet bruikbaar:\n  {aborted}\n"
            "  Voeg tegoed toe op https://console.anthropic.com (Settings -> Billing) "
            "en probeer opnieuw.",
            flush=True,
        )

    print(f"[scan] klaar: {len(all_listings)} unieke vacatures", flush=True)
    return all_listings
