# App Sollicitaties (Job Applications)

> Workspace conventions, environment, git workflow, and the **Skills catalog**
> live in the root [`/home/bruno/CLAUDE.md`](/home/bruno/CLAUDE.md). This file
> only covers what's specific to this repo.

Job-applications tool. **Hybrid**: a Python/FastAPI backend (`api.py`, `main.py`,
`requirements.txt`, `Dockerfile`, `render.yaml`) plus a TanStack/Vite frontend
(`frontend/` and `src/`). Published as a Hugging Face Space and deployable on Render.

## Stack & commands

**Frontend** — Vite + React + shadcn/ui, Bun:
```bash
bun install
bun run dev      # bun run build / build:dev / preview / lint / format
```

**Backend** — Python/FastAPI (use the global venv, see root CLAUDE.md):
```bash
source /home/bruno/myenv/bin/activate
pip install -r requirements.txt
python main.py
```

## Skills to use

- **UI work** → `frontend-design:frontend-design`.
- **Supabase** (if/when used for storage/auth) → `supabase:supabase`.
- **Searching for jobs** → the local `belgische-jobsites` skill (curated Belgian job-sites list) — **consult it first**; scrape pages with the local `scrape-websites` skill or `firecrawl:*`.
- Anything else → see the root Skills catalog.
