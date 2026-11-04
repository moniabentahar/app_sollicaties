"""Fill in the vacancy text for listings whose results page had none.

LinkedIn, Randstad, Werkenvoor, Wyre, ... only show title/company/location on
their results pages, so those listings had no summary and could only be read on
the source site (LinkedIn often blocks that behind a login wall). Here we fetch
each vacancy's own page — LinkedIn via its public guest API, no login — and:

1. ``fetch_descriptions``: put the clean vacancy text on the listing, so
   scoring sees the required languages and skills;
2. ``summarize_listings``: replace that text by a short Dutch summary (Claude
   Haiku) for listings worth reading (strong/consider), and by a trimmed
   snippet for the rest.
"""

from __future__ import annotations

import html as _html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Callable

import lxml.html

from src.filters import TIER_LOW
from src.models import JobListing, ScoredListing

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
_TIMEOUT = 20
_WORKERS = 4
_RETRY_WAITS = (3.0, 8.0, 20.0)  # back-off after HTTP 429 (LinkedIn rate-limits bursts)
_CLEAN_TEXT_CHARS = 20000  # whole vacancy text for scoring: language requirements are often at the end
_SUMMARY_INPUT_CHARS = 12000  # text sent to the summarizer
_PAGE_TEXT_CHARS = 6000    # raw page text sent to the summarizer when no clean text exists
_SNIPPET_CHARS = 300       # summary for low-tier listings (no LLM call)
_SUMMARY_MODEL = "claude-haiku-4-5"
_SUMMARY_MAX_TOKENS = 300

_LINKEDIN_ID = re.compile(r"(\d{8,})/?$")
_ORACLE_JOB = re.compile(r"https://([^/]+)/hcmUI/CandidateExperience/[^/]+/sites/([^/]+)/job/(\d+)")


def _get(url: str, accept: str = "text/html") -> str:
    """GET a URL, backing off and retrying on HTTP 429. Returns '' on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": accept, "Accept-Language": "nl,fr;q=0.8,en;q=0.6"})
    for attempt in range(len(_RETRY_WAITS) + 1):
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < len(_RETRY_WAITS):
                time.sleep(_RETRY_WAITS[attempt])
                continue
            print(f"  [warn] detail HTTP {exc.code}: {url[:80]}")
            return ""
        except Exception as exc:
            print(f"  [warn] detail error {type(exc).__name__}: {url[:80]}")
            return ""
    return ""


def _html_text(fragment: str) -> str:
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", fragment, flags=re.I)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def _linkedin_text(url: str) -> str:
    m = _LINKEDIN_ID.search(url.split("?", 1)[0])
    if not m:
        return ""
    page = _get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}")
    found = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', page, re.S)
    return _html_text(found.group(1)) if found else ""


def _oracle_text(url: str) -> str:
    m = _ORACLE_JOB.match(url)
    if not m:
        return ""
    host, site, job_id = m.groups()
    api = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
           f"?expand=all&onlyData=true&finder=ById;Id=%22{job_id}%22,siteNumber={site}")
    try:
        item = (json.loads(_get(api, "application/json") or "{}").get("items") or [{}])[0]
    except ValueError:
        return ""
    parts = (item.get(k) or "" for k in ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"))
    return _html_text("\n".join(parts))


def _jsonld_text(page: str) -> str:
    for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting" and item.get("description"):
                return _html_text(_html.unescape(str(item["description"])))
    return ""


def _page_text(page: str) -> str:
    """Visible main text of a page — noisy (menus etc.), so only for the summarizer."""
    try:
        doc = lxml.html.fromstring(page)
    except (ValueError, lxml.etree.ParserError):
        return ""
    for bad in doc.xpath("//script|//style|//noscript|//svg|//nav|//header|//footer|//form"):
        if bad.getparent() is not None:
            bad.getparent().remove(bad)
    main = (doc.xpath("//main") or doc.xpath("//article") or [doc])[0]
    lines = (ln.strip() for ln in main.text_content().splitlines())
    return "\n".join(ln for ln in lines if ln)


def _fetch_detail(listing: JobListing) -> tuple[str, bool]:
    """(vacancy text, is_clean). Clean text is the vacancy itself and may be used
    for scoring; unclean text is a whole page, only fit for the summarizer."""
    url = listing.apply_url or ""
    if not url.startswith("http"):
        return "", False
    if listing.source_site == "linkedin" or "linkedin.com/jobs" in url:
        return _linkedin_text(url), True
    if _ORACLE_JOB.match(url):
        return _oracle_text(url), True
    page = _get(url)
    if not page:
        return "", False
    clean = _jsonld_text(page)
    return (clean, True) if clean else (_page_text(page), False)


def fetch_descriptions(listings: list[JobListing]) -> tuple[list[JobListing], dict[str, str]]:
    """Return new listings with the clean vacancy text filled in where it was
    missing, plus {apply_url: text} of every fetched text for the summarizer."""
    todo = [l for l in listings if not l.description_summary.strip() and l.apply_url]
    if not todo:
        return listings, {}
    print(f"  Vacaturetekst ophalen voor {len(todo)} vacatures zonder samenvatting...")
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        results = dict(zip((l.apply_url for l in todo), pool.map(_fetch_detail, todo)))
    texts: dict[str, str] = {}
    out: list[JobListing] = []
    for l in listings:
        text, clean = ("", False) if l.description_summary.strip() else results.get(l.apply_url, ("", False))
        if text:
            texts[l.apply_url] = text[: _CLEAN_TEXT_CHARS if clean else _PAGE_TEXT_CHARS]
        out.append(replace(l, description_summary=text[:_CLEAN_TEXT_CHARS]) if text and clean else l)
    print(f"  Vacaturetekst gevonden voor {len(texts)} van {len(todo)}.")
    return out, texts


def _snippet(text: str) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= _SNIPPET_CHARS:
        return flat
    cut = flat[:_SNIPPET_CHARS]
    end = cut.rfind(". ")
    return cut[: end + 1] if end > _SNIPPET_CHARS // 2 else cut.rsplit(" ", 1)[0] + "…"


def _summarize_one(client, listing: JobListing, text: str) -> str:
    prompt = (
        "Vat deze vacature samen in 2-3 korte zinnen in het Nederlands: wat de functie inhoudt, "
        "het niveau/de verantwoordelijkheden en de belangrijkste vereisten (talen, ervaring). "
        "Gebruik alleen informatie uit de tekst. Geef enkel de samenvatting, zonder inleiding. "
        "Bevat de tekst geen vacature, antwoord dan exact: GEEN\n\n"
        f"Functie: {listing.title} — {listing.company}\n\nTekst:\n{text}"
    )
    try:
        msg = client.messages.create(
            model=_SUMMARY_MODEL, max_tokens=_SUMMARY_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        print(f"  [warn] samenvatting mislukt ({type(exc).__name__}): {listing.title[:50]}")
        return ""
    answer = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    return "" if answer.upper().startswith("GEEN") else answer


def summarize_listings(
    scored: list[ScoredListing], texts: dict[str, str], api_key: str,
    make_client: Callable[[str], object] | None = None,
) -> list[ScoredListing]:
    """Short summaries for listings whose text was fetched: Claude for the
    strong/consider ones, a trimmed snippet (free) for the low ones."""
    if not texts:
        return scored
    relevant = [s for s in scored if s.listing.apply_url in texts and s.tier != TIER_LOW]
    summaries: dict[str, str] = {}
    if relevant and api_key:
        if make_client is None:
            from anthropic import Anthropic
            make_client = lambda key: Anthropic(api_key=key)  # noqa: E731
        client = make_client(api_key)
        print(f"  Samenvattingen maken voor {len(relevant)} relevante vacatures...")
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            done = pool.map(lambda s: _summarize_one(client, s.listing, texts[s.listing.apply_url]), relevant)
            summaries = dict(zip((s.listing.apply_url for s in relevant), done))
    out: list[ScoredListing] = []
    for s in scored:
        url = s.listing.apply_url
        if url not in texts:
            out.append(s)
            continue
        summary = summaries.get(url) or (_snippet(s.listing.description_summary) if s.listing.description_summary else "")
        out.append(replace(s, listing=replace(s.listing, description_summary=summary)))
    return out
