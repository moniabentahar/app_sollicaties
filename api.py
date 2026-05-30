"""Sollicitaties2026 — FastAPI server for the web dashboard."""

from __future__ import annotations

import asyncio
import csv
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.profile import (
    CANDIDATE_LOCATION,
    CANDIDATE_NAME,
    CORE_SKILLS,
    LANGUAGES,
    TARGET_TITLES,
)

app = FastAPI(title="Sollicitaties2026 API")

DOCS_DIR = Path("docs/vacatures")
FRONTEND_DIR = Path("frontend")

_scan_running = False


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
    files = sorted(DOCS_DIR.glob("*.csv"), reverse=True)
    return [{"name": f.name, "stem": f.stem} for f in files]


@app.get("/api/scan/latest")
def get_latest_scan() -> dict:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS_DIR.glob("*.csv"), reverse=True)
    if not files:
        return {"file": None, "listings": []}

    latest = files[0]
    listings: list[dict] = []
    with open(latest, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            # Normalise pipe-separated list fields back to arrays
            row["languages"] = [l for l in row.get("languages", "").split("|") if l]
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
            row["languages"] = [l for l in row.get("languages", "").split("|") if l]
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
        args = ["python", "main.py", "run", "--min-score", str(min_score)]
        if site:
            args += ["--site", site]
        # Force UTF-8 in the child so Rich's CSV-saved banner (→, ≥, …) does not
        # crash on Windows' cp1252 console pipe.
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


# ---------------------------------------------------------------------------
# Serve frontend — must be last so API routes take priority
# ---------------------------------------------------------------------------

FRONTEND_DIR.mkdir(exist_ok=True)

@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
