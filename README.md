---
title: Sollicitaties Backend
emoji: 🔎
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 8000
pinned: false
---

# Sollicitaties2026 — backend

FastAPI backend that scans Belgian job sites (Scrapling + a headless browser)
and ranks vacancies with Claude. This Space hosts the API that the Lovable
front-end calls so scanning works from anywhere.

## Required secrets (set under Settings → Variables and secrets)

| Name | What |
|------|------|
| `ANTHROPIC_API_KEY` | Your `sk-ant-…` key (Claude extraction) |
| `SCAN_TOKEN` | A long random string; protects the scan trigger |

Optional: `ALLOWED_ORIGINS` (default `*`), `SOLLICITATIES_FETCHER` (default `dynamic`).

The front-end (Lovable) must set `VITE_API_BASE_URL` to this Space's URL and
`VITE_SCAN_TOKEN` to the same value as `SCAN_TOKEN`.
