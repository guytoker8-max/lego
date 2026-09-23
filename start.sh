#!/usr/bin/env bash
# Start the BrickSnap website on this computer: http://localhost:8000
# Needs Python 3.10+ and Node.js 18+. Payments run in test mode.
set -e
cd "$(dirname "$0")"
echo "Installing the website (first run takes a few minutes)..."
(cd web && npm install --no-audit --no-fund && npx vite build)
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
export BRICKSNAP_ADMIN_TOKEN="${BRICKSNAP_ADMIN_TOKEN:-admin}"
echo
echo "BrickSnap is running. Open http://localhost:8000 (orders screen: /ops, token: $BRICKSNAP_ADMIN_TOKEN)"
echo "Press Ctrl+C to stop."
( sleep 3; (open http://localhost:8000 || xdg-open http://localhost:8000) >/dev/null 2>&1 ) &
exec uvicorn app.main:app --port 8000
