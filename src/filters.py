"""Scoring engine — ranks each JobListing against the candidate's profile."""

from src.models import JobListing, ScoredListing
from src.profile import (
    TARGET_TITLES,
    CORE_SKILLS,
    PREFERRED_LANGUAGES,
    EXCLUDE_KEYWORDS,
    BELGIUM_INDICATORS,
    REMOTE_INDICATORS,
)

# Score weights
_TITLE_MATCH = 3
_BELGIUM = 2
_PREFERRED_LANG = 2
_SKILL_EACH = 1
_SKILL_CAP = 4      # max bonus from skills
_REMOTE = 1
_PENALTY_JUNIOR = -3
_PENALTY_OFFSITE = -2

TIER_STRONG = "strong"
TIER_CONSIDER = "consider"
TIER_LOW = "low"

_TIER_THRESHOLDS = {
    TIER_STRONG: 5,
    TIER_CONSIDER: 4,
}

# Marketing / sponsorship / partnership domain. A listing only counts as a real
# match — and can only be tiered strong/consider — if its TITLE contains one of
# these (or one of the CV's target titles). This keeps non-marketing Belgian/
# French roles (payroll "gestionnaire paie", office manager, HR business partner)
# out of the strong list, and pulls the explicitly-wanted sponsorship/partnership
# roles in by giving them the title-match bonus.
_DOMAIN_TITLE_TERMS = frozenset({
    "marketing", "brand", "merk", "communicat", "campaign", "campagne",
    "content", "social media", "seo", "sea", "growth marketing",
    "sponsor", "sponsoring", "partnership", "partnerships", "partner manager",
    # PR / public relations
    "public relations", "pr manager", "pr officer", "pr & ", "persrelaties",
    "woordvoerder", "press officer", "press relations",
})

# Non-marketing roles are capped at this score (below the consider threshold of
# 4) so they always rank — and display — as low, on any client.
_NON_DOMAIN_SCORE_CAP = 3


def _norm(text: str) -> str:
    return text.lower().strip()


def _has(haystack: str, needles: frozenset[str]) -> bool:
    return any(needle in haystack for needle in needles)


def score_listing(listing: JobListing) -> ScoredListing:
    score = 0
    flags: list[str] = []

    # Single normalised blob for keyword checks
    blob = _norm(
        f"{listing.title} {listing.company} {listing.location} "
        f"{listing.experience_level} {listing.description_summary} "
        f"{' '.join(listing.skills)} {' '.join(listing.languages)}"
    )

    # --- Exclusions (applied first so they can't be cancelled out) ---
    if _has(blob, EXCLUDE_KEYWORDS):
        score += _PENALTY_JUNIOR
        flags.append("[!] junior/entry-level")

    # --- Title / domain match (marketing, sponsorship, partnership) ---
    title_norm = _norm(listing.title)
    is_domain = _has(title_norm, TARGET_TITLES) or _has(title_norm, _DOMAIN_TITLE_TERMS)
    if is_domain:
        score += _TITLE_MATCH
        flags.append("[+] title match")

    # --- Geography ---
    is_belgium = _has(blob, BELGIUM_INDICATORS)
    is_remote = _has(blob, REMOTE_INDICATORS) or listing.remote in ("remote", "hybrid")

    if is_belgium:
        score += _BELGIUM
        flags.append("[+] Belgium")
    elif not is_remote:
        score += _PENALTY_OFFSITE
        flags.append("[!] outside Belgium / not remote")

    if is_remote:
        score += _REMOTE
        flags.append("[+] remote/hybrid")

    # --- Language fit (Dutch or French native) ---
    lang_blob = _norm(" ".join(listing.languages) + " " + listing.description_summary)
    if _has(lang_blob, PREFERRED_LANGUAGES):
        score += _PREFERRED_LANG
        flags.append("[+] Dutch/French required")

    # --- Skill overlap ---
    matched = sum(1 for skill in CORE_SKILLS if skill in blob)
    capped = min(matched, _SKILL_CAP)
    if capped:
        score += capped * _SKILL_EACH
        flags.append(f"[+] {capped} skill(s) matched")

    # --- Domain cap --- a non-marketing role (payroll, office manager, HR) is
    # irrelevant to this candidate, so it must never read as a match. We cap its
    # *score* below the consider threshold too — not just its tier — so even a
    # score-only client (an older frontend that recomputes the badge from score)
    # still shows it as low without any redeploy.
    if not is_domain:
        score = min(score, _NON_DOMAIN_SCORE_CAP)

    # --- Tier --- only marketing/sponsorship/partnership roles can be strong or
    # consider; everything else is low no matter how high the raw score was.
    if is_domain and score >= _TIER_THRESHOLDS[TIER_STRONG]:
        tier = TIER_STRONG
    elif is_domain and score >= _TIER_THRESHOLDS[TIER_CONSIDER]:
        tier = TIER_CONSIDER
    else:
        tier = TIER_LOW

    return ScoredListing(listing=listing, score=score, flags=flags, tier=tier)


def filter_and_score(listings: list[JobListing]) -> list[ScoredListing]:
    """Score every listing and return them sorted highest first."""
    return sorted(
        (score_listing(l) for l in listings),
        key=lambda s: s.score,
        reverse=True,
    )
