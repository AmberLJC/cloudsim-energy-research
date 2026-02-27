"""
Compute 95% Confidence Intervals from actual per-seed simulation results.
Uses results/carbon/results.csv from simulate-carbon.py
Outputs results/carbon/ci-table-final.txt + .json
"""

import csv
import json
import numpy as np
from scipy import stats
from collections import defaultdict

# Load CSV
rows = []
with open("results/carbon/results.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append({
            "scenario": row["scenario"],
            "policy": row["policy"],
            "seed": int(row["seed"]),
            "energy_kwh": float(row["energy_kwh"]),
            "carbon_gCO2": float(row["carbon_gCO2"]),
            "mean_wait_h": float(row["mean_wait_h"]),
            "n_deferred": int(row["n_deferred"]),
        })

# Build lookup: (scenario, policy, seed) → row
lookup = {}
for r in rows:
    lookup[(r["scenario"], r["policy"], r["seed"])] = r

scenarios = ["low_flex", "medium_flex", "high_flex"]
policies = ["baseline", "threshold", "adaptive", "oracle"]
seeds = sorted(set(r["seed"] for r in rows))
N = len(seeds)

print(f"Loaded {len(rows)} rows, {N} seeds: {seeds}")
print()

def t_ci_95(data):
    arr = np.array(data)
    n = len(arr)
    m = arr.mean()
    se = arr.std(ddof=1) / np.sqrt(n)
    h = stats.t.ppf(0.975, df=n-1) * se
    return m, m - h, m + h, arr.std(ddof=1)

# Compute per-seed carbon savings relative to baseline
results_table = []
for scenario in scenarios:
    for policy in policies:
        if policy == "baseline":
            continue
        
        c_savings = []
        e_overheads = []
        waits = []
        
        for seed in seeds:
            key_pol = (scenario, policy, seed)
            key_base = (scenario, "baseline", seed)
            
            if key_pol not in lookup or key_base not in lookup:
                print(f"  MISSING: {key_pol} or {key_base}")
                continue
            
            pol_row = lookup[key_pol]
            base_row = lookup[key_base]
            
            # Carbon saving vs baseline for this seed
            c_save_pct = 100.0 * (base_row["carbon_gCO2"] - pol_row["carbon_gCO2"]) / base_row["carbon_gCO2"]
            # Energy overhead vs baseline for this seed
            e_overhead_pct = 100.0 * (pol_row["energy_kwh"] - base_row["energy_kwh"]) / base_row["energy_kwh"]
            
            c_savings.append(c_save_pct)
            e_overheads.append(e_overhead_pct)
            waits.append(pol_row["mean_wait_h"])
        
        c_m, c_lo, c_hi, c_sd = t_ci_95(c_savings)
        e_m, e_lo, e_hi, e_sd = t_ci_95(e_overheads)
        w_m, w_lo, w_hi, w_sd = t_ci_95(waits)
        
        results_table.append({
            "scenario": scenario,
            "policy": policy,
            "n_seeds": len(c_savings),
            "c_saving_mean": round(c_m, 2),
            "c_saving_lo95": round(c_lo, 2),
            "c_saving_hi95": round(c_hi, 2),
            "c_saving_sd": round(c_sd, 2),
            "e_overhead_mean": round(e_m, 4),
            "e_overhead_lo95": round(e_lo, 4),
            "e_overhead_hi95": round(e_hi, 4),
            "wait_mean_h": round(w_m, 2),
            "wait_lo95": round(w_lo, 2),
            "wait_hi95": round(w_hi, 2),
            "significant": bool(c_lo > 0.0),  # Entire CI above zero
        })

# --- Print formatted table ---
print("=" * 105)
print("CARBON SAVINGS — 95% CONFIDENCE INTERVALS (t-distribution, n=10)")
print("From actual per-seed simulation data (simulate-carbon.py)")
print("=" * 105)
print(f"{'Policy':<12} {'Scenario':<14} {'C Saving':>9} {'95% CI':>20} {'SD':>6} {'E Overhead':>12} {'Wait (h)':>12} {'Sig?':>5}")
print("-" * 105)

for row in results_table:
    sig_str = "✓" if row["significant"] else "~"
    print(
        f"{row['policy']:<12} {row['scenario']:<14} "
        f"{row['c_saving_mean']:>8.2f}% "
        f"[{row['c_saving_lo95']:>6.2f}%, {row['c_saving_hi95']:>6.2f}%] "
        f"{row['c_saving_sd']:>5.2f}% "
        f"{row['e_overhead_mean']:>11.4f}% "
        f"{row['wait_mean_h']:>5.2f}h [{row['wait_lo95']:>4.2f}–{row['wait_hi95']:>4.2f}] "
        f"{sig_str:>5}"
    )

print("=" * 105)
print()
print("KEY FINDINGS:")
print()
thresh_rows = [r for r in results_table if r["policy"] == "threshold"]
for r in thresh_rows:
    print(f"  Threshold × {r['scenario']}: {r['c_saving_mean']:.2f}% "
          f"[{r['c_saving_lo95']:.2f}–{r['c_saving_hi95']:.2f}%] "
          f"{'✓ Statistically significant (CI entirely > 0)' if r['significant'] else '~ Positive trend, not significant'}")

print()
print("Energy neutrality (all CIs should include 0.0000%):")
for r in results_table:
    includes_zero = r["e_overhead_lo95"] <= 0.0 <= r["e_overhead_hi95"]
    print(f"  {r['policy']} × {r['scenario']}: "
          f"[{r['e_overhead_lo95']:.4f}%, {r['e_overhead_hi95']:.4f}%] "
          f"{'✓' if includes_zero else '⚠ does not include zero!'}")

print()
print("Threshold policy efficiency vs Oracle:")
for scenario in scenarios:
    thresh = next(r for r in results_table if r["policy"] == "threshold" and r["scenario"] == scenario)
    oracle = next(r for r in results_table if r["policy"] == "oracle" and r["scenario"] == scenario)
    eff = 100.0 * thresh["c_saving_mean"] / oracle["c_saving_mean"] if oracle["c_saving_mean"] > 0 else 0
    print(f"  {scenario}: threshold={thresh['c_saving_mean']:.2f}%, oracle={oracle['c_saving_mean']:.2f}%, efficiency={eff:.1f}%")

# Save outputs
with open("results/carbon/ci-table-final.json", "w") as f:
    json.dump(results_table, f, indent=2)

output_lines = []  # re-capture for file
import io, sys
# Save the text to file too
with open("results/carbon/ci-table-final.txt", "w") as f:
    # Reprint to file
    f.write("=" * 105 + "\n")
    f.write("CARBON SAVINGS — 95% CONFIDENCE INTERVALS (t-distribution, n=10)\n")
    f.write("From actual per-seed simulation data (simulate-carbon.py)\n")
    f.write("=" * 105 + "\n")
    f.write(f"{'Policy':<12} {'Scenario':<14} {'C Saving':>9} {'95% CI':>20} {'SD':>6} {'E Overhead':>12} {'Wait (h)':>12} {'Sig?':>5}\n")
    f.write("-" * 105 + "\n")
    for row in results_table:
        sig_str = "SIGNIFICANT" if row["significant"] else "n.s."
        f.write(
            f"{row['policy']:<12} {row['scenario']:<14} "
            f"{row['c_saving_mean']:>8.2f}% "
            f"[{row['c_saving_lo95']:>6.2f}%, {row['c_saving_hi95']:>6.2f}%] "
            f"{row['c_saving_sd']:>5.2f}% "
            f"{row['e_overhead_mean']:>11.4f}% "
            f"{row['wait_mean_h']:>5.2f}h [{row['wait_lo95']:>4.2f}-{row['wait_hi95']:>4.2f}] "
            f"{sig_str}\n"
        )
    f.write("=" * 105 + "\n")

print(f"\nSaved: results/carbon/ci-table-final.json")
print(f"Saved: results/carbon/ci-table-final.txt")
