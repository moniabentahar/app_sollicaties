# Sollicitaties2026 AI — Handbook

How to actually use this thing day-to-day, plus the moving parts behind it.
(The app's own UI is in Dutch — this handbook is in English but quotes the
Dutch button/label text so you can match what you see on screen.)

---

## 1. What this is

A personal job-hunting tool for the Belgian market:

1. You upload your CV (PDF) once.
2. It scrapes ~25 Belgian job sites (VDAB, Indeed, Jobat, StepStone, headhunters,
   sector sites, government portals, direct company pages — see [§10](#10-adding-or-removing-job-sites)).
3. Claude scores every listing against your CV (title match, Belgium/remote,
   language fit, skill overlap) and tiers it **Sterk / Overweeg / Laag**
   (Strong / Consider / Low).
4. You browse, filter, generate a tailored cover letter, and mark jobs as
   applied — all from one dashboard.
5. It also re-scans automatically once a week (Thursday) so new postings show up
   without you doing anything.

## 2. The three moving parts

This project has **three** separate pieces of frontend/backend code in the
same folder — worth knowing which is which so you don't edit the wrong one:

| Piece | What it is | Where |
|---|---|---|
| **The app you actually use** | Frontend hosted on **Lovable**, talking to a FastAPI backend that runs **on this PC** | `src/` (root) is the Lovable-managed frontend source |
| **Backend (always-on)** | FastAPI + the scraper/scorer, auto-started on this PC | `api.py`, `main.py`, `src/*.py` |
| **Local-only mirror** | A second, simpler frontend that the backend serves itself at `http://localhost:8000/` — no Lovable, no internet needed | `frontend/` |

**How the backend stays reachable from Lovable:** your PC's backend isn't on
the public internet by itself. A background watchdog keeps it alive and
exposes it:

```
Windows startup
  → "Sollicitaties-backend (auto)" shortcut
  → scripts/launch-hidden.vbs (runs silently, no window)
  → scripts/watchdog.ps1, forever:
      1. starts uvicorn on :8000 if it's not running
      2. starts a Cloudflare quick tunnel (bin/cloudflared.exe) → :8000
      3. publishes the current tunnel URL to a private-ish GitHub Gist
      4. keeps the PC awake while it's running
```

The Lovable frontend reads that Gist on load to find your backend
automatically — the tunnel URL changes every time the tunnel restarts
(reboot, sleep, etc.), so this auto-discovery is what makes it "just work"
without you ever pasting a URL. You can see it in `src/lib/api.ts`
(`resolveBase()`).

**Practical upshot:** as long as this PC is on and logged in, the watchdog is
running, and the Lovable app works from anywhere (phone, another computer).
If this PC is off or asleep, the Lovable app can't scan or load fresh data
— see [§11](#11-if-the-app-isnt-loading--troubleshooting).

## 3. Daily use — the short version

1. Open your Lovable app URL (bookmark it — it's not this repo, it's the
   Lovable-hosted site built from `src/`).
2. If you haven't yet, click **Upload CV** and pick your CV PDF.
3. Click **Start scan** (or just wait — it also runs automatically, see [§7](#7-the-automatic-schedule)).
4. Browse the **Vacatures** tab: filter by tier (Sterk/Overweeg/Laag) or by
   site, search by title/company/location.
5. Click a job card to open details. From there:
   - **Genereer brief** → Claude writes a tailored cover letter for that job.
   - Confirming the letter marks the job as applied and opens the vacancy
     page to actually submit.
   - Or just toggle **Gesolliciteerd** (applied) without a letter.
6. Check the **Gesolliciteerd** tab any time to see everything you've
   applied to, with the letter you sent.

## 4. First-time setup (or after a fresh PC)

Only needed once, or after reinstalling:

1. Copy `.env.example` → `config/.env` and fill in:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
   This is the only required secret — Claude both extracts CV profiles and
   scores/writes letters. Scraping itself (Scrapling) is free/local.
2. `pip install -r requirements.txt` (Python side).
3. Make sure the **Sollicitaties-backend (auto)** shortcut is in your Windows
   Startup folder (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`)
   — it already is on this machine. That's what keeps the backend + tunnel
   alive without you doing anything.
4. That's it — the Lovable frontend already points at the Gist-discovered
   backend URL by default.

If you ever want to run everything **locally only** (no Lovable, no
internet, e.g. for testing):
```bash
python -m uvicorn api:app --reload          # backend on :8000
cd frontend && bun install && bun run dev   # optional separate dev frontend
```
Or just open `http://localhost:8000/` once the backend is running — it
serves the built `frontend/` app itself.

## 5. The dashboard, piece by piece

- **Header** — your name/location/languages (from the CV), the scan-file
  picker if you have multiple past scans, and a "scannen…" indicator while
  a scan runs.
- **Stat cards** (Totaal / Sterk / Overweeg / Laag) — click one to filter by
  that tier; click again to clear.
- **Vacatures tab** — the live list from the most recent scan. Search box +
  tier filter + site filter.
- **Gesolliciteerd tab** — everything you've marked as applied, with the
  cover letter attached if you generated one.
- **Job card** → click opens **details**, from where you can:
  - open the original posting (**Solliciteer**, opens in a new tab),
  - generate a cover letter,
  - toggle applied status.

## 6. How the scoring actually works — read this once

Scoring lives in `src/filters.py`. Each listing starts at 0 and gets:

| Signal | Points |
|---|---|
| Title matches your CV's target titles / marketing-domain terms | +3 |
| Located in Belgium | +2 |
| Remote/hybrid mentioned | +1 |
| Requires Dutch or French (your preferred languages) | +2 |
| Each of your core skills mentioned (max 4) | +1 each |
| Junior/entry-level/stage/intern wording | **−3** |
| Not in Belgium and not remote | **−2** |

Tiers: **Sterk** ≥ 5, **Overweeg** ≥ 4, everything else **Laag**.

**⚠️ Important caveat:** a listing can *only* be Sterk or Overweeg if its
**title** matches a marketing/brand/sponsorship/partnership/communications
term (a hardcoded list in `_DOMAIN_TITLE_TERMS`) — this was built around a
marketing/sponsorship career profile. If you ever upload a CV for a
different field, every listing gets capped at **Laag** regardless of score,
because none of the titles hit that domain list. If that ever happens and
results look wrong, that hardcoded list in `src/filters.py` is why — it's
not reading your CV's `target_titles` for the domain gate, only for the
title-match *bonus points*.

## 7. The automatic schedule

The backend re-scans **every Thursday at 08:00** (Brussels time)
on its own — see the `CronTrigger` in `api.py`. You'll see "Volgende
automatische scan: …" in the dashboard when it's known.

New listings (first seen in the last 7 days) get an "is_new" flag
automatically.

## 8. Running scans another way — the CLI

Useful for scanning one site while testing, or from a terminal instead of
the browser:

```bash
python main.py run                         # scan everything
python main.py run --site jobat            # one site only
python main.py run --category senior       # a whole category
python main.py run --min-score 3 -v        # verbose, hide low scores in the table
python main.py show_profile                # print the active CV-derived profile
python main.py list_sites                  # list every configured site + category
```
CSVs land in `docs/vacatures/scan_all_YYYY-MM-DD_HHMM.csv` — the dashboard
always shows the newest one.

## 9. Where your data lives

Everything persists as plain files under `docs/` (not committed to git —
check `.gitignore`):

| File | What |
|---|---|
| `docs/profile.json` | Your active CV-derived profile |
| `docs/vacatures/*.csv` | Every past scan, timestamped |
| `docs/applied_jobs.json` | Everything you've marked as applied, incl. cover letters |
| `docs/seen_jobs.json` | First-seen dates, used for the "new" badge |
| `docs/scan_run.log` | Log of the last scan run (handy when a scan seems stuck) |

To start over with a clean slate: delete `docs/profile.json` and re-upload
your CV. To wipe applied history: delete `docs/applied_jobs.json`.

## 10. Adding or removing job sites

1. Update the **`belgische-jobsites`** Claude Code skill
   (`.claude/skills/belgische-jobsites/SKILL.md`) — it's the master list and
   source of truth, organized by category/priority.
2. Add the matching URL pattern(s) to `SITE_URLS` in `src/scraper.py`.
3. Test it in isolation: `python main.py run --site <key> -v`.

## 11. If the app isn't loading — troubleshooting

- **Dashboard loads but scans/uploads fail** → the PC-side backend or tunnel
  is down. Check for a running `cloudflared.exe` and a `python`/`uvicorn`
  process, or just look at `cf_tunnel.log` (Cloudflare tunnel) and
  `docs/scan_run.log` (last scan) for recent timestamps/errors.
- **Nothing running at all** → double-click `scripts/start-local.bat` for a
  quick manual restart (opens two visible windows so you can see what's
  happening), or sign out/in of Windows to let the Startup shortcut relaunch
  the hidden watchdog.
- **A scan looks stuck** → scans are hard-capped at 15 minutes
  (`SCAN_TIMEOUT_SECONDS`); check `docs/scan_run.log` for `[scan] TIMEOUT`.
- **CV upload fails** → almost always a missing/invalid `ANTHROPIC_API_KEY`
  in `config/.env`.
- **LinkedIn results are empty** → LinkedIn's guest API is blocked from
  datacenter IPs; it only works from your PC/VPS IP, and 403s need a fresh
  `li_at` session cookie (see the `belgische-jobsites` skill).

## 12. Other hosting options (documented but not the daily path)

Two alternative ways to host the *backend* online without relying on this
PC being on — already wired up in the repo if you ever want to switch:

- **Hugging Face Space** (`Dockerfile`, front-matter in root `README.md`) —
  free Docker hosting; set `ANTHROPIC_API_KEY` and `SCAN_TOKEN` as Space
  secrets.
- **Render** (`render.yaml`) — paid (~€7/mo, always-on), Blueprint-based,
  persists `docs/` on a mounted disk.

Either way, you'd point the Lovable frontend's `VITE_API_BASE_URL` at that
URL instead of relying on the Gist auto-discovery.

## 13. Security notes

- `config/.env`, `docs/profile.json`, `docs/applied_jobs.json` are
  git-ignored — your CV data and API key never get committed. Good.
- **⚠️ `.claude/skills/scrape-websites/SKILL.md` has a live-looking
  `FIRECRAWL_API_KEY` hardcoded in it, and that file *is* committed** (it's
  been in the repo since the initial commit, pushed to
  `github.com/moniabentahar/app_sollicaties`). If that key is real, treat it
  as compromised: rotate it in your Firecrawl account, then replace the
  hardcoded value in that skill file with a placeholder and load the real
  key from `config/.env` instead. I didn't touch it since that's a
  judgment call on your account — flagging it here so it doesn't get missed.
- `SCAN_TOKEN` (optional) protects the `/api/scan/run` trigger when the
  backend is exposed publicly — worth setting if you move to Hugging
  Face/Render so strangers can't trigger scans on your dime.
