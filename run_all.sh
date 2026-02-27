#!/bin/bash
# ============================================================
# run_all.sh — Reproduce all simulation results from scratch
# 
# Runtime: ~3-4 minutes on any modern laptop
# Requirements: Python 3.8+, NumPy, SciPy, Matplotlib
#
# Outputs:
#   results/carbon/results.csv                    — per-seed raw data (120 runs)
#   results/carbon/summary.json                   — aggregated results
#   results/carbon/ci-table-final.txt             — 95% CI table
#   results/carbon/ci-table-final.json            — CI data
#   results/combined-sim-results.json             — orthogonality experiment
#   results/ci-variability-ablation.json          — CI swing ablation
#   results/carbon/ablation_batch_sensitivity.csv — batch×deadline ablation (200 runs)
#   figures/*.png                                 — all 7 publication figures
# ============================================================

set -e

echo "============================================================"
echo "CloudSim Energy Research — Full Reproduction Run"
echo "Paper: Carbon-Aware Temporal Deferral in Cloud Scheduling"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check required packages
python3 -c "import numpy, scipy, matplotlib" || {
    echo "ERROR: Missing packages. Install with: pip install numpy scipy matplotlib"
    exit 1
}

echo "[1/6] Running main carbon deferral simulation (120 runs)..."
python3 simulate-carbon.py
echo "  → Done: results/carbon/results.csv, results/carbon/summary.json"
echo ""

echo "[2/6] Computing 95% confidence intervals..."
python3 compute-ci-from-csv.py
echo "  → Done: results/carbon/ci-table-final.txt, ci-table-final.json"
echo ""

echo "[3/6] Running combined VAR-PABFD + carbon deferral experiment (40 runs)..."
python3 simulate-combined.py
echo "  → Done: results/combined-sim-results.json"
echo ""

echo "[4/6] Running CI variability ablation..."
python3 ablation-ci-variability.py
echo "  → Done: results/ci-variability-ablation.json"
echo ""

echo "[5/6] Running batch fraction × deadline slack factorial ablation (200 runs)..."
python3 ablation-batch-sensitivity.py
echo "  → Done: results/carbon/ablation_batch_sensitivity.csv, ablation_batch_sensitivity_summary.json"
echo ""

echo "[6/6] Generating publication figures (7 total)..."
python3 generate-figures.py
echo "  → Done: figures/fig1_ci_profile.png ... fig7_batch_sensitivity.png"
echo ""

echo "============================================================"
echo "All results reproduced successfully!"
echo ""
echo "Key results:"
python3 -c "
import json
with open('results/carbon/summary.json') as f:
    s = json.load(f)
print(f'  Main carbon savings (oracle best): {s[\"mean_best_carbon_saving_pct\"]:.1f}% mean')
print(f'  Scenarios exceeding 5% threshold: {s[\"scenarios_above_5pct\"]}/3')
print(f'  Verdict: {s[\"verdict\"]}')
"
echo ""
echo "For full results, see: paper.md"
echo "============================================================"
