#!/usr/bin/env bash
# run_all.sh — Reproduce all results for 006-embodied-carbon
# Usage: bash run_all.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/src"

echo "============================================================"
echo "006-embodied-carbon: Full Reproduction Pipeline"
echo "============================================================"
echo ""

cd "$SRC"

echo "Step 1: simulate-lifecycle.py (baseline CPU fleet)"
python3 simulate-lifecycle.py
echo ""

echo "Step 2: simulate-lifecycle-v2.py (GPU fleet, v2)"
python3 simulate-lifecycle-v2.py
echo ""

echo "Step 3: simulate-lifecycle-v3.py (GPU fleet v3: max_age, declining CI, Policy D note)"
python3 simulate-lifecycle-v3.py
echo ""

echo "Step 4: heuristic-policy.py (threshold heuristic design)"
python3 heuristic-policy.py
echo ""

echo "Step 5: falsification-embodied.py (adversarial falsification tests)"
python3 falsification-embodied.py
echo ""

echo "Step 6: sensitivity-efficiency.py (eff_gain sensitivity sweep)"
python3 sensitivity-efficiency.py
echo ""

echo "Step 7: sensitivity-embodied.py (emb_kg sensitivity sweep — Section 6.2)"
python3 sensitivity-embodied.py
echo ""

echo "============================================================"
echo "All steps complete."
echo "Results: $SCRIPT_DIR/results/"
echo "Figures: $SRC/figures/"
echo "============================================================"
