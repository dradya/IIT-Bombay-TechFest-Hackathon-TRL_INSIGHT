#!/usr/bin/env bash
# TRL INSIGHT - train the model (Linux / macOS)
# Default: synthetic demonstration dataset. For an official dataset run:
#   ./scripts/train.sh --source data/raw/official.csv
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .venv/bin/activate ]; then
  echo "[ERROR] .venv not found. Run ./scripts/setup.sh first."
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
  ARGS=(--synthetic --samples 60)
fi

cd backend
echo "[1/3] prepare_data ${ARGS[*]}"
python training/prepare_data.py "${ARGS[@]}"
echo "[2/3] train_model"
python training/train_model.py
echo "[3/3] evaluate_model"
python training/evaluate_model.py
echo "DONE - metrics written to backend/models/metrics.json"
