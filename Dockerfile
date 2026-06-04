# Backend for Sollicitaties2026 — FastAPI + Scrapling (Playwright) + Claude.
# The official Playwright Python image ships Chromium + every OS library the
# headless browser needs, which is what makes the --browser scan work in the cloud.
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

WORKDIR /app

# Python dependencies (Scrapling, Anthropic, FastAPI, …)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Browser engines Scrapling drives (Chromium for DynamicFetcher, camoufox for stealth).
RUN python -m scrapling install || true

# Application code (secrets are excluded via .dockerignore).
COPY . ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    SOLLICITATIES_FETCHER=dynamic

# Hosting platforms (Render, Railway, Fly) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "python -m uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
