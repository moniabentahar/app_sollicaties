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

    # --- Title match ---
    if _has(_norm(listing.title), TARGET_TITLES):
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

    # --- Tier ---
    if score >= _TIER_THRESHOLDS[TIER_STRONG]:
        tier = TIER_STRONG
    elif score >= _TIER_THRESHOLDS[TIER_CONSIDER]:
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
