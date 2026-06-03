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
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.profile import (
    CANDIDATE_LOCATION,
    CANDIDATE_NAME,
    CORE_SKILLS,
    LANGUAGES,
    TARGET_TITLES,
)

_BRUSSELS = ZoneInfo("Europe/Brussels")
_scheduler = AsyncIOScheduler(timezone=_BRUSSELS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _scheduler.add_job(
        _trigger_auto_scan,
        CronTrigger(day_of_week="tue,fri", hour=8, minute=0, timezone=_BRUSSELS),
        id="auto_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(title="Sollicitaties2026 API", lifespan=lifespan)

DOCS_DIR = Path("docs/vacatures")
FRONTEND_DIR = Path("frontend")
APPLIED_DB = Path("docs/applied_jobs.json")

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


def _build_cover_letter(job: dict) -> str:
    lang = _detect_letter_language(job)
    title = job.get("title", "Marketing Manager")
    company = job.get("company", "uw bedrijf")

    raw_skills = _normalise_skills(job.get("skills", []))
    core_lower = {s.lower() for s in CORE_SKILLS}
    matched = [s for s in raw_skills if s.lower() in core_lower]
    skills_to_use = matched[:3] if matched else raw_skills[:3]

    now = datetime.now()

    if lang == "fr":
        months = ["janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        date_str = f"{now.day} {months[now.month - 1]} {now.year}"
        skills_str = (", ".join(skills_to_use)
                      if skills_to_use else "gestion de marque et stratégie marketing")
        return (
            f"the candidate\n"
            f"Belgium, Flandre-Occidentale (Belgique)\n"
            f"candidate@example.com\n\n"
            f"{date_str}\n\n"
            f"{company}\n\n"
            f"Objet : Candidature — {title}\n\n"
            f"Madame, Monsieur,\n\n"
            f"C'est avec un vif intérêt que je vous soumets ma candidature pour le poste "
            f"de {title} au sein de {company}.\n\n"
            f"Forte d'une solide expérience en marketing et communication, j'ai développé "
            f"une expertise approfondie en brand management, sponsoring, gestion de campagnes "
            f"ATL/BTL et management d'équipes. Mon parcours couvre aussi bien les environnements "
            f"B2B que B2C, en Belgique et à l'international.\n\n"
            f"Ma maîtrise de {skills_str} me permet d'apporter une vision à la fois stratégique "
            f"et opérationnelle, en alignant les objectifs de marque avec des résultats business "
            f"concrets et mesurables.\n\n"
            f"Ce qui m'attire dans ce poste, c'est l'opportunité de contribuer activement au "
            f"développement de la marque et de mettre mon expertise au service de vos équipes "
            f"et de vos clients. Je suis convaincue que mon profil correspond à vos attentes.\n\n"
            f"Je serais ravie de vous rencontrer pour vous présenter mon parcours en détail.\n\n"
            f"Dans l'attente de votre retour, je vous adresse mes sincères salutations,\n\n"
            f"the candidate"
        )

    if lang == "en":
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        date_str = f"{months[now.month - 1]} {now.day}, {now.year}"
        skills_str = (", ".join(skills_to_use)
                      if skills_to_use else "brand management and marketing strategy")
        return (
            f"the candidate\n"
            f"Belgium, West Flanders, Belgium\n"
            f"candidate@example.com\n\n"
            f"{date_str}\n\n"
            f"{company}\n\n"
            f"Re: Application — {title}\n\n"
            f"Dear Hiring Manager,\n\n"
            f"I am writing to express my strong interest in the {title} position at {company}.\n\n"
            f"With an extensive background in brand management, sponsorship, campaign strategy, "
            f"and team leadership, I bring a proven track record of translating business objectives "
            f"into impactful marketing initiatives across both B2B and B2C environments.\n\n"
            f"My expertise in {skills_str} enables me to deliver both strategic direction and "
            f"hands-on execution — from developing integrated communications plans to managing "
            f"cross-functional teams at all levels.\n\n"
            f"I am particularly drawn to this role for the opportunity to drive meaningful brand "
            f"and business impact. I am confident that my profile would be a strong addition to "
            f"your team.\n\n"
            f"I would welcome the opportunity to discuss how my background aligns with your needs.\n\n"
            f"Kind regards,\n\n"
            f"the candidate"
        )

    # nl (default)
    months = ["januari", "februari", "maart", "april", "mei", "juni",
              "juli", "augustus", "september", "oktober", "november", "december"]
    date_str = f"{now.day} {months[now.month - 1]} {now.year}"
    skills_str = (", ".join(skills_to_use)
                  if skills_to_use else "merkstrategie en campagnebeheer")
    return (
        f"the candidate\n"
        f"Belgium, West-Vlaanderen\n"
        f"candidate@example.com\n\n"
        f"{date_str}\n\n"
        f"{company}\n\n"
        f"Betreft: Kandidatuur — {title}\n\n"
        f"Geachte heer / mevrouw,\n\n"
        f"Met oprechte interesse stel ik mijn kandidatuur voor de functie van {title} bij {company}.\n\n"
        f"Als marketingprofessional met een brede achtergrond in brand management, sponsoring, "
        f"campagnebeheer en teamleiding ben ik ervan overtuigd dat mijn profiel een sterke match "
        f"is met wat u zoekt.\n\n"
        f"Mijn ervaring in {skills_str} stelt me in staat zowel strategisch als operationeel te "
        f"denken en te handelen. Ik vertaal merkcommunicatie naar meetbare resultaten, zowel in "
        f"B2B als B2C omgevingen.\n\n"
        f"Wat mij aantrekt in deze functie, is de combinatie van strategische en creatieve "
        f"verantwoordelijkheden die een echte impact hebben op het merk en de business. Ik werk "
        f"graag in een dynamische omgeving waar visie en uitvoering hand in hand gaan.\n\n"
        f"Graag licht ik mijn motivatie verder toe tijdens een persoonlijk gesprek.\n\n"
        f"Met vriendelijke groeten,\n\n"
        f"the candidate"
    )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.get("/api/profile")
def get_profile() -> dict:
    return {
        "name": CANDIDATE_NAME,
        "location": CANDIDATE_LOCATION,
        "target_titles": sorted(TARGET_TITLES),
        "core_skills": sorted(CORE_SKILLS),
        "languages": sorted(LANGUAGES),
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
    site: str | None = None,
    min_score: int = 1,
) -> dict:
    global _scan_running
    if _scan_running:
        raise HTTPException(409, "A scan is already running")
    background_tasks.add_task(_run_scan, site=site, min_score=min_score)
    return {"started": True}


async def _run_scan(site: str | None, min_score: int) -> None:
    global _scan_running
    _scan_running = True
    try:
        import sys
        args = [sys.executable, "main.py", "run", "--min-score", str(min_score), "--browser"]
        if site:
            args += ["--site", site]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        await proc.communicate()
    finally:
        _scan_running = False


async def _trigger_auto_scan() -> None:
    """Called by the scheduler on Tuesday and Friday at 08:00 Brussels time."""
    if not _scan_running:
        await _run_scan(site=None, min_score=1)


@app.get("/api/scan/schedule")
def get_scan_schedule() -> dict:
    job = _scheduler.get_job("auto_scan")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {"next_run": next_run, "days": ["dinsdag", "vrijdag"], "hour": 8}


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
    return FileResponse(_index_file())


# Vite emits hashed bundles under dist/assets/ referenced as /assets/*.
if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

# Static files (favicon, etc.) served from the build output when present.
app.mount("/static", StaticFiles(directory=str(DIST_DIR if DIST_DIR.exists() else FRONTEND_DIR)), name="static")
