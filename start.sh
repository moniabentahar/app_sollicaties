#!/usr/bin/env bash
# Daily startup: activate venv and run the backend.
# Open http://localhost:8000 after this starts.
set -e

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null || true

echo "Starting Sollicitaties2026 backend..."
echo "Open http://localhost:${PORT:-8010} in your browser."
echo "(Ctrl+C to stop)"
echo ""

python -m uvicorn api:app --host 127.0.0.1 --port ${PORT:-8010}
