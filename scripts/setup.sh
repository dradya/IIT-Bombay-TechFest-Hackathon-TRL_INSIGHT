#!/usr/bin/env bash
# =====================================================================
#  TRL INSIGHT - one-time setup for Linux / macOS
#  Requires: Python 3.10+ and Node.js 18+
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

echo "============================================================"
echo " TRL INSIGHT - SETUP"
echo "============================================================"

command -v python3 >/dev/null || { echo "[ERROR] python3 not found"; exit 1; }
command -v npm >/dev/null || { echo "[ERROR] npm not found (install Node.js 18+)"; exit 1; }

echo "[1/4] Creating virtual environment (.venv) ..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
else
  echo "       .venv already exists - reusing it."
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/4] Installing Python dependencies ..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "[3/4] Installing frontend dependencies ..."
(cd frontend && npm install)

echo "[4/4] Training the demonstration model (optional) ..."
(cd backend && python training/prepare_data.py --synthetic --samples 60 \
  && python training/train_model.py && python training/evaluate_model.py)

echo ""
echo "============================================================"
echo " SETUP COMPLETE"
echo "   ./scripts/start.sh   - start backend + frontend"
echo "   ./scripts/train.sh   - retrain the model"
echo "============================================================"
