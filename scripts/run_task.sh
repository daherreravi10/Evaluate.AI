#!/usr/bin/env bash
# One task on its own, so two laptops can work in parallel.
# Usage: TEAM_NAME="Your Team" bash scripts/run_task.sh rents|valuation [--quick]
#
# Laptop A: bash scripts/run_task.sh rents       -> commits outputs/rents_*.csv + metrics_rents.json
# Laptop B: bash scripts/run_task.sh valuation   -> commits outputs/valuation_*.csv + metrics_valuation.json
# Each laptop only touches its own files, so the two pushes never conflict.
# report.html is rebuilt from whichever metrics exist: whoever pushes last runs `python -m src.report`.
set -euo pipefail
cd "$(dirname "$0")/.."
TASK="${1:?rents or valuation}"
Q="${2:-}"
case "$TASK" in rents|valuation) ;; *) echo "task must be rents or valuation"; exit 1;; esac
SLUG=$(python -c "from src.config import team_slug; print(team_slug())")
echo "== $TASK ($SLUG)"
python -m src."$TASK" $Q
python -m src.validate "outputs/${TASK}_${SLUG}.csv"
python -m src.report
echo "== ready to commit: outputs/${TASK}_${SLUG}.csv outputs/metrics_${TASK}.json report.html"
