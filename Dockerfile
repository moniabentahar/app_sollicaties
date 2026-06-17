# Backend for Sollicitaties2026 — FastAPI + Scrapling (Playwright) + Claude.
# Tuned to run on Hugging Face Spaces (free, no card) which runs the container
# as uid 1000. The official Playwright image ships Chromium + all OS libs.
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

# Browsers in the base image live here and are world-readable — point
# Scrapling/patchright at them so no per-user reinstall is needed at runtime.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    SOLLICITATIES_FETCHER=dynamic \
    HF_HOME=/tmp/hf

WORKDIR /app

# Python dependencies (Scrapling, Anthropic, FastAPI, …)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the stealth browser Scrapling drives. Use the `scrapling` console
# script — `python -m scrapling` is NOT valid and fails silently. No `|| true`:
# a failed browser install must break the build, not surface as a broken scan.
RUN scrapling install
RUN chmod -R a+rX /ms-playwright || true

# Application code (secrets are excluded via .dockerignore).
COPY . ./

# Hugging Face runs the container as uid 1000 — runtime dirs must be writable.
RUN mkdir -p docs/vacatures && chmod -R 777 docs

# Hosting platforms inject $PORT; Hugging Face uses app_port from README (8000).
CMD ["sh", "-c", "python -m uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
