"""Candidate profile — loaded from an uploaded CV, single source of truth for scoring.

The active candidate is whoever's CV was last uploaded. It is stored as JSON at
``config/profile.json`` (written by ``src.cv_extract``). Until a CV is uploaded the
profile is empty and the scan matches nothing candidate-specific.

The candidate-specific fields below (titles, skills, languages, identity) are read
from that JSON. The geographic / junior-filter keyword sets are generic defaults that
apply to any Belgium-based candidate, so they stay static.
"""

import json
from pathlib import Path

# Stored under docs/ so it lives on the persistent disk on Render (mountPath
# /app/docs) and survives restarts/redeploys, alongside scans and applied jobs.
ACTIVE_PROFILE_PATH = Path("docs/profile.json")

# Empty/neutral profile used until a CV has been uploaded.
EMPTY_PROFILE: dict = {
    "name": "",
    "location": "",
    "email": "",
    "phone": "",
    "summary": "",
    "about": "",
    "target_titles": [],
    "core_skills": [],
    "languages": [],
    "preferred_languages": [],
    "experience": [],
    "education": [],
}


def load_profile() -> dict:
    """Return the active candidate profile (from the uploaded CV), or an empty profile."""
    if ACTIVE_PROFILE_PATH.exists():
        try:
            with open(ACTIVE_PROFILE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            # Fill any missing keys so callers can rely on the full shape.
            return {**EMPTY_PROFILE, **data}
        except (json.JSONDecodeError, OSError):
            return dict(EMPTY_PROFILE)
    return dict(EMPTY_PROFILE)


def has_profile() -> bool:
    """True once a CV has been uploaded and a non-empty profile exists."""
    p = load_profile()
    return bool(p.get("name") or p.get("target_titles") or p.get("core_skills"))


# ---------------------------------------------------------------------------
# Module-level names derived from the active profile.
#
# These are read once at import. The web scan runs in a *fresh subprocess*
# (api.py spawns `python main.py run`), so each scan re-imports this module and
# picks up the latest uploaded profile automatically. The long-running API
# server re-reads via load_profile() per request instead of these constants.
# ---------------------------------------------------------------------------

_active = load_profile()

CANDIDATE_NAME: str = _active["name"]
CANDIDATE_LOCATION: str = _active["location"]
CANDIDATE_EMAIL: str = _active["email"]
CANDIDATE_PHONE: str = _active["phone"]

TARGET_TITLES: frozenset[str] = frozenset(t.lower() for t in _active["target_titles"])
CORE_SKILLS: frozenset[str] = frozenset(s.lower() for s in _active["core_skills"])
LANGUAGES: frozenset[str] = frozenset(la.lower() for la in _active["languages"])
PREFERRED_LANGUAGES: frozenset[str] = frozenset(
    la.lower() for la in _active["preferred_languages"]
)

# ---------------------------------------------------------------------------
# Generic, candidate-independent keyword sets (Belgian job market).
# ---------------------------------------------------------------------------

# Any listing containing these words gets a heavy penalty (junior/entry-level).
EXCLUDE_KEYWORDS: frozenset[str] = frozenset({
    "junior",
    "entry level",
    "entry-level",
    "stage",
    "stagaire",
    "stagiaire",
    "internship",
    "intern",
    "trainee",
    "graduate",
    "starter",
    "0-2 years",
    "0-3 years",
    "1-2 years",
    "1-3 years",
    "student",
})

BELGIUM_INDICATORS: frozenset[str] = frozenset({
    "belgium", "belgique", "belgië", "belgie",
    "brussels", "bruxelles", "brussel",
    "antwerp", "anvers", "antwerpen",
    "ghent", "gent",
    "liège", "liege", "luik",
    "bruges", "brugge",
    "leuven", "louvain",
    "hasselt", "kortrijk", "mechelen",
    "namur", "namen",
    "west flanders", "west-vlaanderen",
    "east flanders", "oost-vlaanderen",
    "flemish", "vlaanderen",
    "wallonia", "wallonie",
    "charleroi", "mons", "bergen",
    "aalst", "sint-niklaas", "roeselare",
})

REMOTE_INDICATORS: frozenset[str] = frozenset({
    "remote", "télétravail", "teletravail",
    "thuiswerk", "hybrid", "hybride",
    "work from home", "wfh", "flexible",
})
