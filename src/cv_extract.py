"""Extract a job-search profile from an uploaded CV (PDF) using Claude.

Claude reads the PDF natively (document content block), so no PDF-parsing library is
needed. The result is written to ``config/profile.json`` and becomes the active
candidate profile used by the scorer (src/profile.py) and cover letters (api.py).
"""

import base64
import json
import os
from pathlib import Path

from src.profile import ACTIVE_PROFILE_PATH, EMPTY_PROFILE

# CV understanding benefits from a stronger model than the haiku used for listing
# extraction; overridable via env.
CV_MODEL = os.getenv("SOLLICITATIES_CV_MODEL", "claude-sonnet-4-6")

_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The candidate's full name, exactly as written in the CV."},
        "location": {"type": "string", "description": "The candidate's city/region and country, as written in the CV."},
        "email": {"type": "string", "description": "The candidate's email address from the CV (empty string if none)."},
        "phone": {"type": "string", "description": "The candidate's phone number from the CV (empty string if none)."},
        "target_titles": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "10-20 realistic job titles this candidate should apply for, inferred from their "
                "experience and seniority. Lowercase. Include common variants (e.g. 'operations manager', "
                "'plant manager', 'production manager', 'plant director')."
            ),
        },
        "core_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "15-25 core professional skills and competencies from the CV (lowercase), e.g. "
                "'lean manufacturing', 'cost reduction', 'erp', 'production planning', 'team management'."
            ),
        },
        "languages": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Every language the candidate speaks, lowercase English names, e.g. 'dutch', 'french', 'english', 'german'.",
        },
        "preferred_languages": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Native or near-native languages only (lowercase), used to flag roles requiring them.",
        },
    },
    "required": ["name", "target_titles", "core_skills", "languages", "preferred_languages"],
}

_PROFILE_TOOL = {
    "name": "record_profile",
    "description": "Record the candidate's job-search profile extracted from their CV.",
    "input_schema": _PROFILE_SCHEMA,
}

_PROMPT = (
    "The attached PDF is a candidate's CV / resume. Read it and build a job-search profile by "
    "calling record_profile. Pull the identity fields (name, location, email, phone) directly "
    "from the document — do not invent them. Infer realistic target job titles and core skills "
    "from the candidate's actual experience and seniority level. The candidate is looking for "
    "jobs in Belgium, so favour titles and skills relevant to their field."
)


def extract_profile_from_pdf(pdf_bytes: bytes, api_key: str) -> dict:
    """Send the CV PDF to Claude and return a profile dict matching EMPTY_PROFILE's shape."""
    from anthropic import Anthropic  # lazy import; only needed when a CV is uploaded

    client = Anthropic(api_key=api_key)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    msg = client.messages.create(
        model=CV_MODEL,
        max_tokens=2048,
        tools=[_PROFILE_TOOL],
        tool_choice={"type": "tool", "name": "record_profile"},
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                },
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )

    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            raw = block.input if isinstance(block.input, dict) else {}
            return _normalise(raw)
    raise RuntimeError("Claude did not return a structured profile from the CV.")


def _normalise(raw: dict) -> dict:
    """Coerce the model output into the full EMPTY_PROFILE shape."""
    profile = dict(EMPTY_PROFILE)
    for key in ("name", "location", "email", "phone"):
        val = raw.get(key, "")
        profile[key] = val.strip() if isinstance(val, str) else ""
    for key in ("target_titles", "core_skills", "languages", "preferred_languages"):
        val = raw.get(key, [])
        if isinstance(val, list):
            profile[key] = [str(x).strip().lower() for x in val if str(x).strip()]
    return profile


def save_active_profile(profile: dict) -> Path:
    """Write the profile to config/profile.json and return its path."""
    ACTIVE_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACTIVE_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    return ACTIVE_PROFILE_PATH


def extract_and_save(pdf_bytes: bytes, api_key: str) -> dict:
    """Convenience: extract a profile from CV bytes and persist it as the active profile."""
    profile = extract_profile_from_pdf(pdf_bytes, api_key)
    save_active_profile(profile)
    return profile
