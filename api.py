"""Sollicitaties2026 — FastAPI server for the web dashboard."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.cv_extract import extract_and_save
from src.profile import load_profile

_BRUSSELS = ZoneInfo("Europe/Brussels")

_ENV_CANDIDATES = [Path("config/.env"), Path(".env")]


def _load_api_key() -> str:
    """Load ANTHROPIC_API_KEY from config/.env or .env (same convention as main.py)."""
    for p in _ENV_CANDIDATES:
        if p.exists():
            load_dotenv(p)
            break
    return os.getenv("ANTHROPIC_API_KEY", "").strip()
_scheduler = AsyncIOScheduler(timezone=_BRUSSELS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _scheduler.add_job(
        _trigger_auto_scan,
        CronTrigger(day_of_week="tue,thu", hour=8, minute=0, timezone=_BRUSSELS),
        id="auto_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(title="Sollicitaties2026 API", lifespan=lifespan)

# Allow the hosted frontend (e.g. Lovable) to call this backend cross-origin.
# Set ALLOWED_ORIGINS to a comma-separated list of URLs, or "*" (default).
_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
_allow_origins = ["*"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOCS_DIR = Path("docs/vacatures")
FRONTEND_DIR = Path("frontend")
APPLIED_DB = Path("docs/applied_jobs.json")

# Optional shared secret that protects the (expensive) scan trigger.
# When set, /api/scan/run requires the matching X-Scan-Token header.
SCAN_TOKEN = os.getenv("SCAN_TOKEN", "").strip()

# Hard cap on a single scan run so a hanging site can't block scans forever.
SCAN_TIMEOUT_SECONDS = int(os.getenv("SCAN_TIMEOUT_SECONDS", "300"))

_scan_running = False


# ---------------------------------------------------------------------------
# Helpers: applied jobs persistence
# ---------------------------------------------------------------------------

def _load_applied() -> list[dict]:
    if APPLIED_DB.exists():
        try:
            with open(APPLIED_DB, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_applied(data: list[dict]) -> None:
    APPLIED_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(APPLIED_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _job_id(job: dict) -> str:
    key = f"{job.get('title', '')}{job.get('company', '')}{job.get('apply_url', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Helpers: cover letter generation
# ---------------------------------------------------------------------------

def _detect_letter_language(job: dict) -> str:
    langs = job.get("languages", [])
    if isinstance(langs, str):
        langs = [la.strip() for la in langs.split("|") if la.strip()]
    langs_lower = [la.lower() for la in langs]
    if any(la in ("nl", "dutch", "nederlands") for la in langs_lower):
        return "nl"
    if any(la in ("fr", "french", "français", "francais") for la in langs_lower):
        return "fr"
    if any(la in ("en", "english", "anglais") for la in langs_lower):
        return "en"
    return "nl"


def _normalise_skills(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [s.strip() for s in raw.split("|") if s.strip()]
    if isinstance(raw, list):
        return [s for s in raw if s]
    return []


def _candidate_block(profile: dict) -> str:
    """Header lines (name / location / contact) built from the uploaded CV's profile."""
    lines = [profile.get("name") or "Candidate"]
    if profile.get("location"):
        lines.append(profile["location"])
    contact = " | ".join(c for c in (profile.get("email"), profile.get("phone")) if c)
    if contact:
        lines.append(contact)
    return "\n".join(lines)


def _build_cover_letter(job: dict) -> str:
    profile = load_profile()
    if not (profile.get("name") or profile.get("core_skills")):
        return "Upload a CV first to generate a personalised cover letter."

    candidate_name = profile.get("name") or "Candidate"
    header = _candidate_block(profile)

    lang = _detect_letter_language(job)
    title = job.get("title", "")
    company = job.get("company", "")

    raw_skills = _normalise_skills(job.get("skills", []))
    core_lower = {s.lower() for s in profile.get("core_skills", [])}
    matched = [s for s in raw_skills if s.lower() in core_lower]
    # Prefer skills shared by the job and the candidate; fall back to the candidate's own.
    skills_to_use = (matched[:3] or raw_skills[:3] or list(profile.get("core_skills", []))[:3])

    now = datetime.now()

    if lang == "fr":
        months = ["janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        date_str = f"{now.day} {months[now.month - 1]} {now.year}"
        skills_str = ", ".join(skills_to_use) if skills_to_use else "mes domaines d'expertise"
        return (
            f"{header}\n\n"
            f"{date_str}\n\n"
            f"{company}\n\n"
            f"Objet : Candidature — {title}\n\n"
            f"Madame, Monsieur,\n\n"
            f"C'est avec un vif intérêt que je vous soumets ma candidature pour le poste "
            f"de {title} au sein de {company}.\n\n"
            f"Fort(e) d'une solide expérience professionnelle, j'ai développé une expertise "
            f"approfondie en {skills_str}. Mon parcours m'a permis de mener à bien des projets "
            f"exigeants, en Belgique comme à l'international.\n\n"
            f"Ma maîtrise de {skills_str} me permet d'apporter une vision à la fois stratégique "
            f"et opérationnelle, en alignant les objectifs sur des résultats concrets et "
            f"mesurables.\n\n"
            f"Ce qui m'attire dans ce poste, c'est l'opportunité de mettre mon expertise au "
            f"service de vos équipes. Je suis convaincu(e) que mon profil correspond à vos "
            f"attentes.\n\n"
            f"Je serais ravi(e) de vous rencontrer pour vous présenter mon parcours en détail.\n\n"
            f"Dans l'attente de votre retour, je vous adresse mes sincères salutations,\n\n"
            f"{candidate_name}"
        )

    if lang == "en":
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        date_str = f"{months[now.month - 1]} {now.day}, {now.year}"
        skills_str = ", ".join(skills_to_use) if skills_to_use else "my areas of expertise"
        return (
            f"{header}\n\n"
            f"{date_str}\n\n"
            f"{company}\n\n"
            f"Re: Application — {title}\n\n"
            f"Dear Hiring Manager,\n\n"
            f"I am writing to express my strong interest in the {title} position at {company}.\n\n"
            f"With an extensive professional background, I bring a proven track record of "
            f"translating objectives into concrete results across demanding projects, both in "
            f"Belgium and internationally.\n\n"
            f"My expertise in {skills_str} enables me to deliver both strategic direction and "
            f"hands-on execution.\n\n"
            f"I am particularly drawn to this role for the opportunity to bring meaningful impact "
            f"to your team. I am confident that my profile would be a strong addition.\n\n"
            f"I would welcome the opportunity to discuss how my background aligns with your needs.\n\n"
            f"Kind regards,\n\n"
            f"{candidate_name}"
        )

    # nl (default)
    months = ["januari", "februari", "maart", "april", "mei", "juni",
              "juli", "augustus", "september", "oktober", "november", "december"]
    date_str = f"{now.day} {months[now.month - 1]} {now.year}"
    skills_str = ", ".join(skills_to_use) if skills_to_use else "mijn vakgebied"
    return (
        f"{header}\n\n"
        f"{date_str}\n\n"
        f"{company}\n\n"
        f"Betreft: Kandidatuur — {title}\n\n"
        f"Geachte heer / mevrouw,\n\n"
        f"Met oprechte interesse stel ik mijn kandidatuur voor de functie van {title} bij {company}.\n\n"
        f"Met een brede professionele achtergrond ben ik ervan overtuigd dat mijn profiel een "
        f"sterke match is met wat u zoekt.\n\n"
        f"Mijn ervaring in {skills_str} stelt me in staat zowel strategisch als operationeel te "
        f"denken en te handelen, en doelstellingen te vertalen naar meetbare resultaten.\n\n"
        f"Wat mij aantrekt in deze functie, is de kans om mijn expertise in te zetten voor uw "
        f"team. Ik werk graag in een dynamische omgeving waar visie en uitvoering hand in hand "
        f"gaan.\n\n"
        f"Graag licht ik mijn motivatie verder toe tijdens een persoonlijk gesprek.\n\n"
        f"Met vriendelijke groeten,\n\n"
        f"{candidate_name}"
    )


def _build_cv(job: dict) -> str:
    """A tailored one-page CV draft built from the uploaded profile, in the job's
    language, with skills that match the vacancy listed first. Editable by the user."""
    profile = load_profile()
    if not (profile.get("name") or profile.get("core_skills")):
        return "Upload eerst een CV om een CV-voorstel te genereren."

    name = profile.get("name") or "Kandidaat"
    contact = " | ".join(
        c for c in (profile.get("location"), profile.get("email"), profile.get("phone")) if c
    )
    lang = _detect_letter_language(job)
    title = job.get("title", "")
    company = job.get("company", "")

    skills = list(profile.get("core_skills", []))
    raw = _normalise_skills(job.get("skills", []))
    core_lower = {s.lower(): s for s in skills}
    matched = [core_lower[s.lower()] for s in raw if s.lower() in core_lower]
    ordered = matched + [s for s in skills if s not in matched]
    skills_block = "\n".join(f"• {s}" for s in ordered[:10]) or "•"
    langs = ", ".join(profile.get("languages", [])) or "—"
    titles = ", ".join(sorted(profile.get("target_titles", []))[:6]) or title

    labels = {
        "nl": ("Gericht op", "PROFIEL", "WERKERVARING", "OPLEIDING", "KERNCOMPETENTIES",
               "TALEN", "GEWENSTE FUNCTIES",
               f"Gemotiveerde, resultaatgerichte professional met ervaring in marketing, "
               f"communicatie en sponsoring. Klaar om bij te dragen aan {company} als {title}."),
        "fr": ("Pour le poste de", "PROFIL", "EXPÉRIENCE", "FORMATION", "COMPÉTENCES CLÉS",
               "LANGUES", "FONCTIONS VISÉES",
               f"Professionnel(le) motivé(e) et orienté(e) résultats, expérimenté(e) en marketing, "
               f"communication et sponsoring. Prêt(e) à contribuer à {company} en tant que {title}."),
        "en": ("Applying for", "PROFILE", "EXPERIENCE", "EDUCATION", "KEY SKILLS",
               "LANGUAGES", "TARGET ROLES",
               f"Motivated, results-driven professional experienced in marketing, communication "
               f"and sponsorship. Ready to contribute to {company} as {title}."),
    }[lang]
    aim, p_lbl, exp_lbl, edu_lbl, s_lbl, l_lbl, t_lbl, fallback_summary = labels

    summary = profile.get("summary") or fallback_summary

    exp_lines = []
    for e in profile.get("experience", []):
        head = " — ".join(p for p in (e.get("role"), e.get("company")) if p)
        period = e.get("period")
        exp_lines.append(f"{head}{f'  ({period})' if period else ''}")
        for h in (e.get("highlights") or [])[:4]:
            exp_lines.append(f"  • {h}")
    exp_block = "\n".join(exp_lines)

    edu_lines = []
    for e in profile.get("education", []):
        head = " — ".join(p for p in (e.get("degree"), e.get("school")) if p)
        period = e.get("period")
        edu_lines.append(f"{head}{f'  ({period})' if period else ''}")
    edu_block = "\n".join(edu_lines)

    parts = [
        f"{name}\n{contact}\n{aim}: {title} — {company}",
        f"{p_lbl}\n{summary}",
    ]
    if exp_block:
        parts.append(f"{exp_lbl}\n{exp_block}")
    if edu_block:
        parts.append(f"{edu_lbl}\n{edu_block}")
    parts.append(f"{s_lbl}\n{skills_block}")
    parts.append(f"{l_lbl}\n{langs}")
    parts.append(f"{t_lbl}\n{titles}")
    return "\n\n".join(parts) + "\n"


_ANALYZE_MODEL = os.getenv("SOLLICITATIES_ANALYZE_MODEL", "claude-haiku-4-5")

_ANALYZE_TOOL = {
    "name": "record_advice",
    "description": "Record a short fit analysis and recommendation for this vacancy.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fit": {
                "type": "string",
                "enum": ["sterk", "overweeg", "zwak"],
                "description": "Overall fit of this vacancy to the candidate.",
            },
            "analysis": {
                "type": "string",
                "description": "2-3 concise Dutch sentences: why this role does or doesn't fit her background.",
            },
            "recommendation": {
                "type": "string",
                "description": "One concise Dutch sentence with the concrete recommendation/next step.",
            },
        },
        "required": ["fit", "analysis", "recommendation"],
    },
}


def _analyze_fit(job: dict) -> dict:
    """Short, honest fit analysis of a vacancy against the candidate's CV profile."""
    profile = load_profile()
    if not (profile.get("name") or profile.get("experience")):
        return {"fit": "", "analysis": "Upload eerst een CV voor een advies.", "recommendation": ""}
    api_key = _load_api_key()
    if not api_key:
        return {"fit": "", "analysis": "Geen API-sleutel ingesteld.", "recommendation": ""}

    from anthropic import Anthropic

    exp = "; ".join(
        f"{e.get('role', '')} @ {e.get('company', '')}" for e in profile.get("experience", [])[:6]
    )
    prof = (
        f"Naam: {profile.get('name')}\n"
        f"Samenvatting: {profile.get('summary', '')}\n"
        f"Ervaring: {exp}\n"
        f"Kerncompetenties: {', '.join(profile.get('core_skills', [])[:15])}\n"
        f"Talen: {', '.join(profile.get('languages', []))}"
    )
    jobtxt = (
        f"Functie: {job.get('title', '')}\n"
        f"Bedrijf: {job.get('company', '')}\n"
        f"Locatie: {job.get('location', '')}\n"
        f"Beschrijving: {job.get('description_summary', '')}\n"
        f"Skills: {', '.join(_normalise_skills(job.get('skills', [])))}"
    )
    try:
        msg = Anthropic(api_key=api_key).messages.create(
            model=_ANALYZE_MODEL,
            max_tokens=600,
            tools=[_ANALYZE_TOOL],
            tool_choice={"type": "tool", "name": "record_advice"},
            messages=[{
                "role": "user",
                "content": (
                    "Je bent een nuchtere, eerlijke loopbaanadviseur. Beoordeel kort en bondig in het "
                    "Nederlands hoe goed deze vacature past bij deze kandidate, op basis van haar CV/profiel. "
                    "Noem concreet welke ervaring relevant is (of net ontbreekt).\n\n"
                    f"KANDIDATE:\n{prof}\n\nVACATURE:\n{jobtxt}"
                ),
            }],
        )
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                d = block.input if isinstance(block.input, dict) else {}
                return {
                    "fit": d.get("fit", ""),
                    "analysis": d.get("analysis", ""),
                    "recommendation": d.get("recommendation", ""),
                }
    except Exception as exc:
        return {"fit": "", "analysis": f"Advies niet beschikbaar: {str(exc)[:90]}", "recommendation": ""}
    return {"fit": "", "analysis": "Geen advies gegenereerd.", "recommendation": ""}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.get("/api/profile")
def get_profile() -> dict:
    """Return the active candidate profile (from the last uploaded CV)."""
    p = load_profile()
    return {
        "name": p.get("name", ""),
        "location": p.get("location", ""),
        "email": p.get("email", ""),
        "phone": p.get("phone", ""),
        "target_titles": sorted(p.get("target_titles", [])),
        "core_skills": sorted(p.get("core_skills", [])),
        "languages": sorted(p.get("languages", [])),
        "has_profile": bool(p.get("name") or p.get("target_titles") or p.get("core_skills")),
    }


@app.post("/api/profile/upload")
async def upload_cv(file: UploadFile = File(...)) -> dict:
    """Upload a CV (PDF); Claude extracts a job-search profile that becomes active."""
    api_key = _load_api_key()
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured (add it to config/.env).")

    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF CV.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(400, "The uploaded file is empty.")

    try:
        profile = await asyncio.to_thread(extract_and_save, pdf_bytes, api_key)
    except Exception as exc:  # noqa: BLE001 — surface a clean message to the UI
        raise HTTPException(502, f"Could not read the CV: {type(exc).__name__}: {str(exc)[:200]}")

    return {
        "name": profile.get("name", ""),
        "location": profile.get("location", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "target_titles": sorted(profile.get("target_titles", [])),
        "core_skills": sorted(profile.get("core_skills", [])),
        "languages": sorted(profile.get("languages", [])),
        "has_profile": True,
    }


# ---------------------------------------------------------------------------
# Scans — read CSV files written by the CLI
# ---------------------------------------------------------------------------

@app.get("/api/scans")
def list_scans() -> list[dict]:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS_DIR.glob("*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.name, "stem": f.stem} for f in files]


@app.get("/api/scan/latest")
def get_latest_scan() -> dict:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS_DIR.glob("*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return {"file": None, "listings": []}

    latest = files[0]
    listings: list[dict] = []
    with open(latest, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["languages"] = [la for la in row.get("languages", "").split("|") if la]
            row["skills"] = [s for s in row.get("skills", "").split("|") if s]
            row["flags"] = [f.strip() for f in row.get("flags", "").split("  ") if f.strip()]
            row["score"] = int(row.get("score", 0))
            listings.append(row)

    return {"file": latest.name, "listings": listings}


@app.get("/api/scan/status")
def scan_status() -> dict:
    return {"running": _scan_running}


# Must be declared before /api/scan/{filename}, otherwise "schedule" is treated
# as a scan filename and 404s.
@app.get("/api/scan/schedule")
def get_scan_schedule() -> dict:
    job = _scheduler.get_job("auto_scan")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {"next_run": next_run, "days": ["dinsdag", "donderdag"], "hour": 8}


@app.get("/api/scan/{filename}")
def get_scan(filename: str) -> dict:
    path = DOCS_DIR / filename
    if not path.exists() or path.suffix != ".csv":
        raise HTTPException(404, "Scan file not found")

    listings: list[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["languages"] = [la for la in row.get("languages", "").split("|") if la]
            row["skills"] = [s for s in row.get("skills", "").split("|") if s]
            row["flags"] = [f.strip() for f in row.get("flags", "").split("  ") if f.strip()]
            row["score"] = int(row.get("score", 0))
            listings.append(row)

    return {"file": filename, "listings": listings}


# ---------------------------------------------------------------------------
# Scan trigger
# ---------------------------------------------------------------------------

@app.post("/api/scan/run")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    request: Request,
    site: str | None = None,
    min_score: int = 1,
) -> dict:
    global _scan_running
    if SCAN_TOKEN and request.headers.get("X-Scan-Token", "") != SCAN_TOKEN:
        raise HTTPException(401, "Invalid or missing scan token")
    if _scan_running:
        raise HTTPException(409, "A scan is already running")
    background_tasks.add_task(_run_scan, site=site, min_score=min_score)
    return {"started": True}


async def _run_scan(site: str | None, min_score: int) -> None:
    global _scan_running
    _scan_running = True
    proc = None
    try:
        import sys
        args = [sys.executable, "main.py", "run", "--min-score", str(min_score),
                "--verbose"]
        if site:
            args += ["--site", site]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        # Inherit stdout/stderr so the scan's per-site progress streams live into
        # the Space logs (we can see exactly where it is / where it hangs).
        proc = await asyncio.create_subprocess_exec(*args, env=env)
        try:
            rc = await asyncio.wait_for(proc.wait(), timeout=SCAN_TIMEOUT_SECONDS)
            print(f"[scan] finished exit={rc}", flush=True)
        except asyncio.TimeoutError:
            # One hanging site must not block scans forever — kill and move on.
            print(f"[scan] TIMEOUT after {SCAN_TIMEOUT_SECONDS}s — killing scan", flush=True)
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
    finally:
        _scan_running = False


async def _trigger_auto_scan() -> None:
    """Called by the scheduler on Tuesday and Friday at 08:00 Brussels time."""
    if not _scan_running:
        await _run_scan(site=None, min_score=1)


# ---------------------------------------------------------------------------
# Applications (applied jobs)
# ---------------------------------------------------------------------------

@app.get("/api/applications")
def get_applications() -> list[dict]:
    return _load_applied()


@app.post("/api/applications")
async def save_application(request: Request) -> dict:
    job = await request.json()
    applied = _load_applied()
    job_id = _job_id(job)
    if any(a.get("job_id") == job_id for a in applied):
        return {"ok": True, "job_id": job_id, "duplicate": True}
    entry: dict[str, Any] = {
        "job_id": job_id,
        "applied_date": datetime.now().isoformat(),
        **{k: v for k, v in job.items()},
    }
    applied.append(entry)
    _save_applied(applied)
    return {"ok": True, "job_id": job_id}


@app.delete("/api/applications/{job_id}")
def delete_application(job_id: str) -> dict:
    applied = _load_applied()
    applied = [a for a in applied if a.get("job_id") != job_id]
    _save_applied(applied)
    return {"ok": True}


@app.post("/api/generate-letter")
async def generate_letter(request: Request) -> dict:
    job = await request.json()
    letter = _build_cover_letter(job)
    return {"letter": letter}


@app.post("/api/generate-cv")
async def generate_cv(request: Request) -> dict:
    job = await request.json()
    return {"cv": _build_cv(job)}


@app.post("/api/analyze")
async def analyze(request: Request) -> dict:
    job = await request.json()
    return await asyncio.to_thread(_analyze_fit, job)


# ---------------------------------------------------------------------------
# Serve frontend — must be last so API routes take priority
# ---------------------------------------------------------------------------

FRONTEND_DIR.mkdir(exist_ok=True)
DIST_DIR = FRONTEND_DIR / "dist"


def _index_file() -> Path:
    """Prefer the built React SPA; fall back to the raw frontend dir."""
    built = DIST_DIR / "index.html"
    return built if built.exists() else FRONTEND_DIR / "index.html"


@app.get("/")
def serve_index() -> FileResponse:
    # Never cache the HTML shell: it references hashed JS bundles, so a stale
    # cached index.html would keep loading an old app version after an update.
    return FileResponse(_index_file(), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# Vite emits hashed bundles under dist/assets/ referenced as /assets/*.
if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

# Static files (favicon, etc.) served from the build output when present.
app.mount("/static", StaticFiles(directory=str(DIST_DIR if DIST_DIR.exists() else FRONTEND_DIR)), name="static")
