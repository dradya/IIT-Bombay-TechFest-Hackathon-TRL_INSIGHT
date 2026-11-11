#!/usr/bin/env bash
# =====================================================================
#  TRL INSIGHT - start backend + frontend (Linux / macOS)
#  Backend : http://localhost:8000   Frontend: http://localhost:5173
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .venv/bin/activate ]; then
  echo "[ERROR] .venv not found. Run ./scripts/setup.sh first."
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

cleanup() {
  echo ""
  echo "Stopping TRL INSIGHT ..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

PORT="${TRL_PORT:-8000}"
echo "Starting backend on http://localhost:${PORT} ..."
(cd backend && python -m uvicorn app.main:app --reload --port "${PORT}") &

echo "Starting frontend on http://localhost:5173 ..."
(cd frontend && npm run dev) &

echo ""
echo "============================================================"
echo "  Frontend : http://localhost:5173"
echo "  API      : http://localhost:${PORT}/api/docs"
echo "  Press Ctrl+C to stop both services."
echo "============================================================"
wait
