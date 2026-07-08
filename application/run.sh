#!/usr/bin/env bash
# Dev launcher for the SparkGuardian licensing portal.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env

echo "→ http://localhost:8000  (admin: /admin)"
uvicorn backend.main:app --reload --port 8000
