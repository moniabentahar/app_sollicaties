#!/usr/bin/env bash
# First-time setup: creates a venv, installs Python deps, and installs the
# Playwright browser that Scrapling uses for anti-bot scraping.
set -e

echo "=== Sollicitaties2026 — first-time setup ==="

# Create venv if it doesn't exist yet
if [ ! -d "venv" ]; then
  python -m venv venv
  echo "[1/3] Virtual environment created."
else
  echo "[1/3] Virtual environment already exists — skipping."
fi

# Activate (Linux/Mac: bin/activate; Windows Git Bash: Scripts/activate)
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate

# Python dependencies
echo "[2/3] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "      Done."

# Playwright / Scrapling browser
echo "[3/3] Installing Scrapling browser (Playwright Chromium)..."
scrapling install
echo "      Done."

# Prompt for API key if config/.env doesn't exist yet
mkdir -p config
if [ ! -f "config/.env" ]; then
  echo ""
  echo "Almost there! Create config/.env with your Anthropic API key:"
  echo "  echo 'ANTHROPIC_API_KEY=sk-ant-...' > config/.env"
else
  echo ""
  echo "config/.env already exists."
fi

echo ""
echo "Setup complete. Run ./start.sh to start the app."
