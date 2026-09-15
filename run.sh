#!/usr/bin/env bash
# Convenience launcher: creates a venv on first run, then starts the bot.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "→ creating virtual environment"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "✗ .env not found. Run:  cp .env.example .env  and fill in API_ID / API_HASH"
  exit 1
fi

exec ./.venv/bin/python bot.py "$@"
