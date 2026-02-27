#!/usr/bin/env python3
"""
Analysis for Non-Linear Extension Experiment.
Reads results/nonlinear_results.csv.
Appends Extension Analysis section to analysis.md.
"""

import csv
import os
import statistics
import math
from collections import defaultdict
from typing import List, Dict, Tuple

RESULTS_FILE = "results/nonlinear_results.csv"
ANALYSIS_FILE = "analysis.md"

NULL_THRESHOLD = 0.02    # < 2% → null
PROCEED_THRESHOLD = 0.05  # > 5% in 2/3 scenarios → confirm

def load_results() -> List[Dict]:
    results = []
    with open(RESULTS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k in ["seed", "n_vms", "n_vms_rejected", "sla_violations_abs"]:
                row[k] = int(row[k])
            for k in ["total_energy_dc_kj", "total_compute_energy_kj",
                      "total_cooling_energy_kj", "avg_pue", "avg_dc_util",
                      "avg_active_hosts", "sla_violation_rate"]:
                row[k] = float(row[k])
            results.append(row)
    return results


def mean(xs): return statistics.mean(xs) if xs else 0.0
def std(xs): return statistics.stdev(xs) if len(xs) > 1 else 0.0
def ci95(xs):
    n = len(xs)
    if n < 2: return 0.0
    t_crit = 2.262  # t_{0.025, 9}
    return t_crit * std(xs) / math.sqrt(n)


def paired_ttest(xs, ys) -> Tuple[float, str]:
    diffs = [x - y for x, y in zip(xs, ys)]
    n = len(diffs)
    if n < 2: return 0.0, "N/A"
    d_mean = mean(diffs)
    d_std = std(diffs)
    if d_std == 0:
        return 0.0, "1.000" if d_mean == 0 else "< 0.001"
    t = d_mean / (d_std / math.sqrt(n))
    if abs(t) > 4.781: p = "< 0.001"
    elif abs(t) > 3.250: p = "< 0.005"
    elif abs(t) > 2.262: p = "< 0.050"
    else: p = f"≈ {min(1.0, 2 * max(0.05, 1 - abs(t) / 5.0)):.3f}"
    return t, p


def cohens_d(xs, ys) -> float:
    diffs = [x - y for x, y in zip(xs, ys)]
    s = std(diffs)
    return mean(diffs) / s if s > 0 else 0.0


def pct_improvement(base, prop) -> float:
    if base == 0: return 0.0
    return (base - prop) / base * 100.0


def main():
    if not os.path.exists(RESULTS_FILE):
        print(f"ERROR: {RESULTS_FILE} not found. Run simulate_nonlinear.py first.")
        return

    results = load_results()
    print(f"Loaded {len(results)} results from {RESULTS_FILE}")

    # Group by (power_model, pue_model, algorithm, scenario) → list of rows (by seed)
    groups = defaultdict(list)
    for r in results:
        k = (r["power_model"], r["pue_model"], r["algorithm"], r["scenario"])
        groups[k].append(r)

    conditions = [
        ("linear",    "linear",   "Replication (linear P + linear PUE)"),
        ("quadratic", "linear",   "Quadratic Power + Linear PUE"),
        ("linear",    "ashrae",   "Linear Power + ASHRAE Piecewise PUE"),
        ("quadratic", "ashrae",   "Quadratic Power + ASHRAE Piecewise PUE"),
    ]
    scenarios = ["low", "medium", "high"]
    algos = ["PABFD", "D_PABFD_NL", "SpreadFit", "Random"]
    algo_labels = {
        "PABFD":      "PABFD (consolidation)",
        "D_PABFD_NL": "D-PABFD-NL (ours)",
        "SpreadFit":  "SpreadFit (spreading)",
        "Random":     "Random",
    }

    lines = []
    lines.append("\n\n---\n")
    lines.append("# Extension Analysis — Non-Linear Power & PUE Models")
    lines.append("")
    lines.append("**Protocol Amendment PA-002:** Pre-registered sensitivity test (protocol §2, §11)")
    lines.append("**Date:** 2026-02-27")
    lines.append("**Motivation:** Primary experiment null result has analytic explanation: for linear")
    lines.append("P and linear PUE, all placement decisions are equivalent. This extension tests")
    lines.append("non-linear models where the degeneracy breaks.")
    lines.append("")
    lines.append("## Extension Hypothesis (H1-NL)")
    lines.append("")
    lines.append("> Under non-linear power (quadratic) or non-linear PUE (ASHRAE piecewise),")
    lines.append("> D-PABFD-NL outperforms PABFD by > 2% total DC energy in ≥ 1 scenario.")
    lines.append("")
    lines.append("## Analytic Prediction")
    lines.append("")
    lines.append("For quadratic P(u) = 100 + 150×u²:")
    lines.append("  ΔP(h) = 150 × [(u_h + δ)² − u_h²] = 150 × [2u_h×δ + δ²]")
    lines.append("  → ΔP increases with u_h → D-PABFD-NL prefers low-utilization hosts")
    lines.append("  → D-PABFD-NL ≡ SpreadFit under quadratic power (spreading policy)")
    lines.append("")
    lines.append("For ASHRAE PUE (non-linear, steeper at low loads):")
    lines.append("  PUE changes are non-uniform — ΔPUE differs between host choices")
    lines.append("  when the DC load crosses a PUE tier boundary.")
    lines.append("")
    lines.append("## Results by Condition")
    lines.append("")

    all_condition_verdicts = {}

    for power_model, pue_model, condition_label in conditions:
        lines.append(f"### Condition: {condition_label}")
        lines.append("")
        lines.append("| Algorithm | Low Churn (kJ) | Medium Churn (kJ) | High Churn (kJ) | Avg PUE (med) |")
        lines.append("|-----------|----------------|-------------------|-----------------|---------------|")

        # Per-algo summary
        for algo in algos:
            row_vals = []
            pue_med = None
            for scen in scenarios:
                k = (power_model, pue_model, algo, scen)
                rows = groups.get(k, [])
                if rows:
                    e = [r["total_energy_dc_kj"] for r in rows]
                    row_vals.append(f"{mean(e):.1f} ± {ci95(e):.1f}")
                    if scen == "medium":
                        pue_med = mean([r["avg_pue"] for r in rows])
                else:
                    row_vals.append("N/A")
            pue_str = f"{pue_med:.3f}" if pue_med is not None else "N/A"
            lines.append(f"| {algo_labels[algo]} | {' | '.join(row_vals)} | {pue_str} |")

        lines.append("")
        lines.append("**D-PABFD-NL vs PABFD (primary comparison):**")
        lines.append("")
        lines.append("| Scenario | PABFD (kJ) | D-PABFD-NL (kJ) | Improvement | t-stat | p-value | Cohen's d |")
        lines.append("|----------|------------|-----------------|-------------|--------|---------|-----------|")

        scenario_improvements = {}
        for scen in scenarios:
            k_base = (power_model, pue_model, "PABFD", scen)
            k_prop = (power_model, pue_model, "D_PABFD_NL", scen)
            base_rows = groups.get(k_base, [])
            prop_rows = groups.get(k_prop, [])
            if not base_rows or not prop_rows:
                continue
            e_base = [r["total_energy_dc_kj"] for r in base_rows]
            e_prop = [r["total_energy_dc_kj"] for r in prop_rows]
            pct = pct_improvement(mean(e_base), mean(e_prop))
            t, p = paired_ttest(e_base, e_prop)
            d = cohens_d(e_base, e_prop)
            sign = "↓" if pct > 0 else "↑"
            lines.append(f"| {scen.capitalize()} | {mean(e_base):.1f} | {mean(e_prop):.1f} | "
                         f"{pct:+.2f}% {sign} | {t:.3f} | {p} | {d:.3f} |")
            scenario_improvements[scen] = pct

        # Verdict for this condition
        n_improved = sum(1 for pct in scenario_improvements.values()
                         if pct > PROCEED_THRESHOLD * 100)
        n_null = sum(1 for pct in scenario_improvements.values()
                     if pct < NULL_THRESHOLD * 100)

        if n_improved >= 2:
            verdict = "✅ H1-NL CONFIRMED"
            verdict_detail = f"D-PABFD-NL shows >5% improvement in {n_improved}/3 scenarios"
        elif n_improved == 1:
            verdict = "⚠️ PARTIAL"
            verdict_detail = f"D-PABFD-NL shows >5% improvement in only 1/3 scenarios"
        elif n_null == len(scenario_improvements):
            verdict = "❌ NULL (< 2% in all scenarios)"
            verdict_detail = "Degeneracy persists under this condition"
        else:
            verdict = "⚠️ MARGINAL"
            verdict_detail = "Some improvement but below pre-registered 5% threshold"

        all_condition_verdicts[(power_model, pue_model)] = {
            "verdict": verdict,
            "improvements": scenario_improvements,
        }

        lines.append("")
        lines.append(f"**Verdict: {verdict}** — {verdict_detail}")
        lines.append("")

    # ─── Summary Table ────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## Summary: Where Does Non-Linearity Matter?")
    lines.append("")
    lines.append("| Power Model | PUE Model | Low Δ | Med Δ | High Δ | Verdict |")
    lines.append("|-------------|-----------|-------|-------|--------|---------|")

    for power_model, pue_model, condition_label in conditions:
        v = all_condition_verdicts.get((power_model, pue_model), {})
        imps = v.get("improvements", {})
        verdict = v.get("verdict", "N/A")
        row = [
            power_model,
            pue_model,
            f"{imps.get('low', 0.0):+.2f}%",
            f"{imps.get('medium', 0.0):+.2f}%",
            f"{imps.get('high', 0.0):+.2f}%",
            verdict,
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # ─── Theoretical Interpretation ──────────────────────────────────────────
    lines.append("## Theoretical Interpretation")
    lines.append("")
    lines.append("**Why non-linear models break the degeneracy:**")
    lines.append("")
    lines.append("Primary null result proved: for linear P(u)=a+b×u and linear PUE(u)=c-d×u,")
    lines.append("ΔE_total_DC is identical for any active host. No algorithm can beat any other.")
    lines.append("")
    lines.append("Quadratic P(u)=a+b×u²:")
    lines.append("  ΔP(h) = b×[(u_h+δ)²-u_h²] = b×δ×(2u_h + δ)")
    lines.append("  This is NOT constant — it grows with u_h.")
    lines.append("  D-PABFD-NL therefore prefers low-utilization hosts (SpreadFit behavior).")
    lines.append("  Whether spreading beats consolidation depends on:")
    lines.append("    - Magnitude of quadratic power savings (load-spreading benefit)")
    lines.append("    - PUE overhead from having more active hosts (consolidation benefit)")
    lines.append("")
    lines.append("ASHRAE piecewise PUE:")
    lines.append("  When DC load crosses a PUE tier boundary (e.g. u=0.4 → u=0.6),")
    lines.append("  ΔPUE is non-zero and differs based on which direction the load moves.")
    lines.append("  This creates non-degenerate PUE cost differences between host choices.")
    lines.append("")

    # ─── Implication for Paper Direction ──────────────────────────────────────
    lines.append("## Implications for Research Direction")
    lines.append("")
    lines.append("Three possible outcomes and their publication angles:")
    lines.append("")
    lines.append("1. **Null holds everywhere:** Novel theoretical result — 'PABFD is accidentally")
    lines.append("   PUE-optimal for a broad class of power/PUE models.' Target: CloudSim user")
    lines.append("   community, negative result venues (SIGMOD Record, Results in Negative).")
    lines.append("")
    lines.append("2. **H1-NL confirmed for non-linear models:** Stronger result — shows exactly")
    lines.append("   WHERE PUE-aware scheduling matters. Practical guidance: upgrade to SPECpower")
    lines.append("   quadratic model to unlock scheduling improvements. Target: IEEE TCC.")
    lines.append("")
    lines.append("3. **H1-NL partial:** Mixed evidence. Most interesting framing: 'The regime")
    lines.append("   boundary — linear vs. quadratic — determines whether PUE scheduling pays off.'")
    lines.append("   This is a 'when does it matter?' paper, which is often publishable and")
    lines.append("   practically useful for practitioners choosing simulation fidelity.")

    with open(ANALYSIS_FILE, "a") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nExtension analysis appended to {ANALYSIS_FILE}")

    # Print summary
    print("\n=== VERDICT SUMMARY ===")
    for (pm, pue_m), v in all_condition_verdicts.items():
        print(f"  {pm}+{pue_m}: {v['verdict']}")
        for scen, pct in v['improvements'].items():
            print(f"    {scen}: {pct:+.2f}%")


if __name__ == "__main__":
    main()
