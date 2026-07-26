#!/usr/bin/env bash
# Fallback local run (no Docker). Starts API + frontend in the background.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

cd "$ROOT/frontend"
if [[ ! -f .env.local ]]; then
  cp .env.example .env.local
fi
npm install
npm run dev &
UI_PID=$!

trap 'kill $API_PID $UI_PID 2>/dev/null || true' EXIT
echo "API  http://127.0.0.1:8000  (pid $API_PID)"
echo "UI   http://localhost:3000  (pid $UI_PID)"
wait
