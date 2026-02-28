"""
sensitivity-efficiency.py — GPU Efficiency Gain Sensitivity Analysis
=====================================================================
Tests robustness of GPU inference lifecycle results across three
efficiency gain assumptions:
  - eff = 0.25 (conservative: 25%/gen efficiency improvement)
  - eff = 0.50 (baseline, as used in simulate-lifecycle-v3.py)
  - eff = 0.75 (optimistic: 75%/gen efficiency improvement)

For each efficiency level, computes DP-Optimal vs Fixed-2yr savings
across 6 CI scenarios (50, 100, 300, 400, 500, 800 gCO2/kWh),
GPU inference scenario: max_useful_age=4yr, emb=3000 kgCO2, 20 seeds.

Outputs:
  results/sensitivity-efficiency.json
  src/figures/fig_sensitivity_efficiency.png
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os, json, sys
from typing import Dict, List, Optional

# ─── Parameters ──────────────────────────────────────────────────────────────
GPU_FLEET_SIZE   = 50
GPU_HORIZON      = 10
GPU_EMBODIED_KG  = 3000.0
GPU_REFRESH_NORM = 2
GPU_MAX_AGE      = 4      # inference constraint
P_BASE_W         = 300.0
HOURS_PER_YEAR   = 8760
N_SEEDS          = 20
MAX_GEN          = 30

CI_SCENARIOS = {
    'nuclear_fr':   50,
    'norway_hydro': 100,
    'eu_avg':       300,
    'us_avg':       400,
    'uk_grid':      500,
    'coal_pl':      800,
}

EFF_GAIN_LEVELS = [0.25, 0.50, 0.75]


# ─── DP Table ─────────────────────────────────────────────────────────────────

def build_dp_table(ci_g_per_kwh, eff_gain, emb_kg, p_old_w, hours, horizon, max_gen=MAX_GEN):
    def op_carbon(g, ci):
        p_w = p_old_w * ((1.0 - eff_gain) ** g)
        return (p_w / 1000.0) * hours * (ci / 1000.0)

    V = np.zeros((max_gen + 1, horizon + 1), dtype=np.float64)
    for yr in range(1, horizon + 1):
        for g in range(max_gen + 1):
            wait    = op_carbon(g, ci_g_per_kwh) + V[g, yr - 1]
            replace = (emb_kg + op_carbon(g + 1, ci_g_per_kwh) + V[g + 1, yr - 1]
                       if g + 1 <= max_gen else float('inf'))
            V[g, yr] = min(wait, replace)
    return V


def dp_should_replace(gen, years_remaining, V, ci_g_per_kwh, eff_gain, emb_kg, p_old_w, hours):
    if years_remaining <= 0 or gen + 1 > MAX_GEN:
        return False

    def op_carbon(g):
        p_w = p_old_w * ((1.0 - eff_gain) ** g)
        return (p_w / 1000.0) * hours * (ci_g_per_kwh / 1000.0)

    wait    = op_carbon(gen)     + V[gen,     years_remaining - 1]
    replace = emb_kg + op_carbon(gen + 1) + V[gen + 1, years_remaining - 1]
    return replace < wait


# ─── Fleet Simulation ─────────────────────────────────────────────────────────

def run_policy(policy, ci_val, eff_gain, emb_kg, p_old_w, hours, horizon,
               fleet_size, refresh_norm, max_age, n_seeds, dp_table):
    results = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        # stagger initial ages [0, refresh_norm)
        ages = rng.integers(0, max(1, refresh_norm), size=fleet_size).astype(float)
        gens = np.zeros(fleet_size, dtype=int)
        total_carbon = 0.0  # matches v3: sunk costs excluded from comparison metric
        total_reps   = 0

        for year in range(horizon):
            years_remaining = horizon - year
            year_carbon = 0.0
            for i in range(fleet_size):
                should_replace = False
                if policy == 'fixed_2':
                    should_replace = (ages[i] >= refresh_norm)
                elif policy == 'dp_optimal':
                    should_replace = dp_should_replace(
                        gens[i], years_remaining, dp_table, ci_val, eff_gain, emb_kg, p_old_w, hours)

                # Hard max-age constraint
                if max_age is not None and ages[i] >= max_age:
                    should_replace = True

                if should_replace:
                    year_carbon  += emb_kg
                    total_carbon += emb_kg
                    total_reps   += 1
                    ages[i]       = 0.0
                    gens[i]      += 1

                # operational carbon
                p_w = p_old_w * ((1.0 - eff_gain) ** gens[i])
                op  = (p_w / 1000.0) * hours * (ci_val / 1000.0)
                total_carbon += op
                year_carbon  += op
                ages[i]      += 1.0

        results.append({'total_carbon': total_carbon, 'replacements': total_reps})

    vals = [r['total_carbon'] for r in results]
    reps = [r['replacements'] for r in results]
    return {
        'mean_carbon': float(np.mean(vals)),
        'std_carbon':  float(np.std(vals)),
        'min_carbon':  float(np.min(vals)),
        'max_carbon':  float(np.max(vals)),
        'mean_replacements': float(np.mean(reps)),
    }


# ─── Main Run ─────────────────────────────────────────────────────────────────

print("Sensitivity Analysis: GPU Efficiency Gain (0.25 / 0.50 / 0.75 per generation)")
print(f"GPU inference: max_age={GPU_MAX_AGE}yr, emb={GPU_EMBODIED_KG}kg, norm={GPU_REFRESH_NORM}yr")
print()

sensitivity_results = {}

for eff in EFF_GAIN_LEVELS:
    eff_key = f"eff_{int(eff*100):03d}"
    print(f"── Efficiency gain: {eff:.2f} ({int(eff*100)}%/gen) ──")
    sensitivity_results[eff_key] = {
        'eff_gain': eff,
        'scenarios': {}
    }

    for ci_name, ci_val in CI_SCENARIOS.items():
        dp_table = build_dp_table(
            ci_g_per_kwh=ci_val, eff_gain=eff, emb_kg=GPU_EMBODIED_KG,
            p_old_w=P_BASE_W, hours=HOURS_PER_YEAR, horizon=GPU_HORIZON
        )

        agg_fixed = run_policy(
            'fixed_2', ci_val, eff, GPU_EMBODIED_KG, P_BASE_W, HOURS_PER_YEAR,
            GPU_HORIZON, GPU_FLEET_SIZE, GPU_REFRESH_NORM, GPU_MAX_AGE, N_SEEDS, dp_table
        )
        agg_dp = run_policy(
            'dp_optimal', ci_val, eff, GPU_EMBODIED_KG, P_BASE_W, HOURS_PER_YEAR,
            GPU_HORIZON, GPU_FLEET_SIZE, GPU_REFRESH_NORM, GPU_MAX_AGE, N_SEEDS, dp_table
        )

        c_fixed = agg_fixed['mean_carbon']
        c_dp    = agg_dp['mean_carbon']
        saving  = (c_fixed - c_dp) / c_fixed * 100 if c_fixed > 0 else 0.0

        print(f"  {ci_name:>14} ({ci_val:>4}): Fixed-2yr={c_fixed:>9,.0f}kg "
              f"DP={c_dp:>9,.0f}kg  saving={saving:+.1f}%")

        sensitivity_results[eff_key]['scenarios'][ci_name] = {
            'ci': ci_val,
            'fixed_2yr': agg_fixed,
            'dp_optimal': agg_dp,
            'saving_pct': float(saving),
        }

    savings_list = [sensitivity_results[eff_key]['scenarios'][n]['saving_pct']
                    for n in CI_SCENARIOS]
    sensitivity_results[eff_key]['summary'] = {
        'min_saving_pct':  float(min(savings_list)),
        'mean_saving_pct': float(np.mean(savings_list)),
        'max_saving_pct':  float(max(savings_list)),
    }
    print(f"  → savings: min={min(savings_list):+.1f}% mean={np.mean(savings_list):+.1f}% max={max(savings_list):+.1f}%")
    print()

# ─── Save JSON ────────────────────────────────────────────────────────────────

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "sensitivity-efficiency.json")

output = {
    "metadata": {
        "script": "sensitivity-efficiency.py",
        "scenario": "GPU inference (max_age=4yr, emb=3000kg, norm=2yr, fleet=50, horizon=10yr, seeds=20)",
        "eff_gain_levels": EFF_GAIN_LEVELS,
        "ci_scenarios": CI_SCENARIOS,
    },
    "results": sensitivity_results,
}

with open(out_path, 'w') as f:
    json.dump(output, f, indent=2)
print(f"Saved {out_path}")


# ─── Figure ───────────────────────────────────────────────────────────────────

ci_values  = list(CI_SCENARIOS.values())
ci_labels  = [f"{v}" for v in ci_values]
colors     = ['#e67e22', '#2980b9', '#27ae60']
linestyles = ['--', '-', ':']
markers    = ['s', 'o', '^']

fig, ax = plt.subplots(figsize=(10, 6))

for (eff, color, ls, mk) in zip(EFF_GAIN_LEVELS, colors, linestyles, markers):
    eff_key  = f"eff_{int(eff*100):03d}"
    savings  = [sensitivity_results[eff_key]['scenarios'][n]['saving_pct']
                for n in CI_SCENARIOS]
    label    = f"eff = {int(eff*100)}%/gen"
    ax.plot(ci_values, savings, marker=mk, linestyle=ls, linewidth=2,
            markersize=8, color=color, label=label)
    # annotate endpoints
    ax.annotate(f"{savings[-1]:+.0f}%", xy=(ci_values[-1], savings[-1]),
                xytext=(5, 0), textcoords='offset points', fontsize=8,
                color=color, va='center')

ax.set_xlabel("Grid Carbon Intensity (gCO₂/kWh)", fontsize=12)
ax.set_ylabel("DP-Optimal Carbon Savings vs Fixed-2yr (%)", fontsize=12)
ax.set_title(
    "GPU Inference Fleet: DP-Optimal Savings Sensitivity to Efficiency Gain Assumption\n"
    "max_age=4yr · emb=3000 kgCO₂ · 50 servers · 10yr · 20 seeds",
    fontsize=11
)
ax.set_xticks(ci_values)
ax.set_xticklabels(ci_labels, fontsize=10)
ax.legend(fontsize=11, loc='upper right')
ax.grid(True, alpha=0.35)
ax.set_ylim(0, max(
    max(sensitivity_results[f'eff_{int(e*100):03d}']['scenarios'][n]['saving_pct']
        for n in CI_SCENARIOS)
    for e in EFF_GAIN_LEVELS
) + 10)

# shade between min/max eff lines
savings_025 = [sensitivity_results['eff_025']['scenarios'][n]['saving_pct'] for n in CI_SCENARIOS]
savings_075 = [sensitivity_results['eff_075']['scenarios'][n]['saving_pct'] for n in CI_SCENARIOS]
ax.fill_between(ci_values, savings_025, savings_075, alpha=0.10, color='gray',
                label='Sensitivity band (25–75%)')

plt.tight_layout()

fig_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(fig_dir, exist_ok=True)
fig_path = os.path.join(fig_dir, "fig_sensitivity_efficiency.png")
plt.savefig(fig_path, dpi=300, bbox_inches='tight')
plt.close()
print(f"Saved {fig_path}")
print()
print("[DONE] sensitivity-efficiency.py complete.")
