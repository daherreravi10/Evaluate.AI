#!/usr/bin/env bash
# Whole pipeline in order. Usage: TEAM_NAME="Your Team" bash scripts/run_all.sh [--quick]
set -euo pipefail
cd "$(dirname "$0")/.."
Q="${1:-}"
echo "== tests";        python -m pytest -q
echo "== outside data"; python -m src.exo.build
echo "== Task 4";       python -m src.rents $Q
echo "== Task 5";       python -m src.valuation $Q
echo "== validate";     python -m src.validate
echo "== mock judge";   python scripts/mock_judge.py
echo "== report";       python -m src.report
