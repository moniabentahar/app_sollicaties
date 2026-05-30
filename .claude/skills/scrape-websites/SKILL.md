---
name: scrape-websites
description: |
  Scrape and extract clean content from websites using Firecrawl.
  Use for researching companies, job postings, LinkedIn profiles,
  or any web page that needs to be read as structured text.
  Covers live CLI usage, REST API calls, and multi-page crawling.
---

# Scrape Websites with Firecrawl

Use Firecrawl to pull clean, readable content from any URL — company
pages, vacature sites, LinkedIn, HR portals, or news articles.

## Prerequisites

The API key must be set before any Firecrawl command or API call:

```bash
# Add to your .env in the project root (never commit this file)
FIRECRAWL_API_KEY=fc-fd14292b21554b19ae5de6b0a68d8a8e
```

Load it in the session:

```bash
# PowerShell
$env:FIRECRAWL_API_KEY = (Get-Content .env | Select-String "FIRECRAWL_API_KEY").ToString().Split("=")[1]

# Bash
export $(grep FIRECRAWL_API_KEY .env | xargs)
```

## Decision Tree

```
Do you have the URL already?
  YES → use scrape (Path A)
  NO  → use search first, then scrape (Path B)

Does the page need a login or button click?
  YES → use interact (Path C)
  NO  → plain scrape is enough
```

---

## Path A — Scrape a Known URL

### CLI

```bash
# Basic scrape → saves clean markdown
firecrawl scrape "https://www.example.com/vacature/developer" \
  -o docs/vacatures/developer.md

# Include only the main content, skip nav/footer
firecrawl scrape "https://www.bedrijf.nl/over-ons" \
  --include-tags main,article \
  -o docs/bedrijven/bedrijf-nl.md
```

### REST API (PowerShell)

```powershell
$response = Invoke-RestMethod `
  -Uri "https://api.firecrawl.dev/v2/scrape" `
  -Method POST `
  -Headers @{ Authorization = "Bearer $env:FIRECRAWL_API_KEY"; "Content-Type" = "application/json" } `
  -Body (@{
    url     = "https://www.bedrijf.nl/vacatures/software-engineer"
    formats = @("markdown")
  } | ConvertTo-Json)

# The clean markdown content
$response.data.markdown
```

### REST API (Python / Node — for src/ code)

```python
import httpx, os

def scrape(url: str) -> str:
    r = httpx.post(
        "https://api.firecrawl.dev/v2/scrape",
        headers={"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
        json={"url": url, "formats": ["markdown"]},
    )
    r.raise_for_status()
    return r.json()["data"]["markdown"]
```

```typescript
import axios from "axios";

async function scrape(url: string): Promise<string> {
  const { data } = await axios.post(
    "https://api.firecrawl.dev/v2/scrape",
    { url, formats: ["markdown"] },
    { headers: { Authorization: `Bearer ${process.env.FIRECRAWL_API_KEY}` } }
  );
  return data.data.markdown;
}
```

---

## Path B — Search Then Scrape

Use when you don't have a direct URL yet.

```bash
# Find vacatures
firecrawl search "software developer vacature Amsterdam 2026" \
  --limit 5

# Then scrape the most relevant result
firecrawl scrape "https://result-from-search.nl/vacature/123" \
  -o docs/vacatures/result.md
```

REST API search → scrape sequence:

```powershell
# Step 1: search
$search = Invoke-RestMethod `
  -Uri "https://api.firecrawl.dev/v2/search" `
  -Method POST `
  -Headers @{ Authorization = "Bearer $env:FIRECRAWL_API_KEY"; "Content-Type" = "application/json" } `
  -Body (@{ query = "software developer vacature Amsterdam"; limit = 5 } | ConvertTo-Json)

# Step 2: pick the first result and scrape
$url = $search.data[0].url
firecrawl scrape $url -o docs/vacatures/search-result.md
```

---

## Path C — Pages That Need Interaction

Use when the content is behind a login, a "load more" button, or a
cookie wall.

```bash
# Click through a cookie banner and scrape
firecrawl interact "https://jobs.bedrijf.nl" \
  --actions '[{"type":"click","selector":"#cookie-accept"},{"type":"wait","ms":1000}]' \
  --then-scrape \
  -o docs/vacatures/jobs-bedrijf.md
```

---

## Path D — Crawl an Entire Vacature Section

Use when you want every job posting from a company's careers page in
one pass.

```bash
firecrawl crawl "https://www.bedrijf.nl/vacatures" \
  --limit 30 \
  --depth 2 \
  -o docs/bedrijven/bedrijf-all-vacatures/
```

---

## Saving Output

Always save scraped content under `docs/` so it stays out of the root:

```
docs/
├── bedrijven/          ← company research pages
├── vacatures/          ← individual job postings
└── contacten/          ← recruiter or contact pages
```

```bash
# Example naming convention
firecrawl scrape "$URL" -o "docs/vacatures/$(date +%Y-%m-%d)-bedrijfsnaam.md"
```

---

## Error Recovery

If a scrape fails or returns unexpected output, use the `ask` command
with the job ID that Firecrawl printed:

```bash
firecrawl ask --job-id "job_abc123" "Why did this scrape return empty content?"
```

Or via REST:

```powershell
Invoke-RestMethod `
  -Uri "https://api.firecrawl.dev/v2/support/ask" `
  -Method POST `
  -Headers @{ Authorization = "Bearer $env:FIRECRAWL_API_KEY"; "Content-Type" = "application/json" } `
  -Body (@{ question = "Why is the markdown empty?"; jobId = "job_abc123" } | ConvertTo-Json)
```

---

## Quick Checklist Before Running

- [ ] `FIRECRAWL_API_KEY` is set in the session
- [ ] Output path is inside `docs/`, not the root
- [ ] `.env` is in `.gitignore`
- [ ] For multi-URL runs: use `crawl` or loop `scrape`, not repeated manual calls

---

## Related Skills

- `firecrawl/firecrawl-search` — search-first discovery workflow
- `firecrawl/firecrawl-interact` — pages that require clicks or login
- `firecrawl/firecrawl-crawl` — bulk extraction across many pages
