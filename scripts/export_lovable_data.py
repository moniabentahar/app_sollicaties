"""Export a scan CSV to the static listings.json the Lovable frontend reads.

Lovable (app_sollicaties) is frontend-only and cannot call this FastAPI backend,
so it renders from a bundled ``src/data/listings.json``. This script converts a
scan produced by ``main.py`` into that exact shape, letting you refresh the live
Lovable site after every scan.

Workflow:
    1. Run a scan:        python main.py run
    2. Export for Lovable: python scripts/export_lovable_data.py --out <lovable>/src/data/listings.json
    3. Commit & push the Lovable repo -> Lovable rebuilds with fresh data.

Usage:
    python scripts/export_lovable_data.py                 # latest scan -> docs/lovable/listings.json
    python scripts/export_lovable_data.py --scan scan_all_2026-05-30_1442.csv
    python scripts/export_lovable_data.py --fullest       # pick scan with most listings
    python scripts/export_lovable_data.py --out "C:/path/to/app_sollicaties/src/data/listings.json"

The output schema matches the original Lovable prototype exactly::

    { "file": "<scan filename>", "listings": [ { ...listing... } ] }
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

DOCS_DIR = Path("docs/vacatures")
DEFAULT_OUT = Path("docs/lovable/listings.json")


def _parse_row(row: dict[str, str]) -> dict:
    """Normalise one CSV row into the JSON shape (mirrors api.py)."""
    return {
        "title": row.get("title", ""),
        "company": row.get("company", ""),
        "location": row.get("location", ""),
        "source_site": row.get("source_site", ""),
        "remote": row.get("remote", ""),
        "experience_level": row.get("experience_level", ""),
        "languages": [la for la in row.get("languages", "").split("|") if la],
        "skills": [s for s in row.get("skills", "").split("|") if s],
        "posted_date": row.get("posted_date", ""),
        "apply_url": row.get("apply_url", ""),
        "description_summary": row.get("description_summary", ""),
        "score": int(row.get("score", 0) or 0),
        "flags": [f.strip() for f in row.get("flags", "").split("  ") if f.strip()],
        "tier": row.get("tier", "low"),
    }


def _read_listings(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [_parse_row(row) for row in csv.DictReader(fh)]


def _select_scan(scan: str | None, fullest: bool) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS_DIR.glob("*.csv"), reverse=True)
    if not files:
        sys.exit(f"No scan CSV files found in {DOCS_DIR}/. Run `python main.py run` first.")

    if scan:
        chosen = DOCS_DIR / scan
        if not chosen.exists():
            available = "\n  ".join(f.name for f in files)
            sys.exit(f"Scan '{scan}' not found. Available:\n  {available}")
        return chosen

    if fullest:
        return max(files, key=lambda f: sum(1 for _ in open(f, encoding="utf-8")) - 1)

    return files[0]  # latest by filename (same as /api/scan/latest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a scan to the Lovable listings.json.")
    parser.add_argument("--scan", help="Specific scan filename in docs/vacatures/ (default: latest).")
    parser.add_argument("--fullest", action="store_true", help="Pick the scan with the most listings.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output path (default: {DEFAULT_OUT}).")
    args = parser.parse_args()

    scan_path = _select_scan(args.scan, args.fullest)
    listings = _read_listings(scan_path)
    payload = {"file": scan_path.name, "listings": listings}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    tiers: dict[str, int] = {}
    for item in listings:
        tiers[item["tier"]] = tiers.get(item["tier"], 0) + 1
    breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(tiers.items()))
    print(f"Exported {len(listings)} listings from {scan_path.name}")
    print(f"  tiers: {breakdown}")
    print(f"  -> {args.out}")


if __name__ == "__main__":
    main()
