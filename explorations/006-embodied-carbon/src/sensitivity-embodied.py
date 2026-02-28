"""
sensitivity-embodied.py — GPU Embodied Carbon Sensitivity Analysis
===================================================================
Sweeps GPU embodied carbon (emb_kg) to test robustness of the
"extend inference refresh to 4yr" recommendation.

Fixed parameters (GPU inference scenario):
  max_useful_age_yr = 4
  eff_gain          = 0.50/gen
  refresh_norm      = 2yr
  H (horizon)       = 10yr
  N (fleet size)    = 50 GPUs
  seeds             = 20

Sweep: emb_kg ∈ [500, 1000, 1500, 2000, 3000, 4000, 5000] kgCO₂

For each emb_kg × CI scenario × seed:
  - Fixed-2yr     (industry norm baseline)
  - DP-Optimal    (backward-induction DP)
  - Fixed-4yr     (heuristic — paper recommendation)

Metrics:
  dp_savings_pct      = (Fixed-2yr − DP-Optimal) / Fixed-2yr * 100
  heuristic4_savings_pct = (Fixed-2yr − Fixed-4yr) / Fixed-2yr * 100
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import json
from typing import Dict, List, Optional

# ─── Parameters ───────────────────────────────────────────────────────────────
EMB_KG_SWEEP      = [500, 1000, 1500, 2000, 3000, 4000, 5000]
GPU_EFF_GAIN      = 0.50
GPU_REFRESH_NORM  = 2
GPU_MAX_AGE       = 4
GPU_HORIZON       = 10
GPU_FLEET_SIZE    = 50
N_SEEDS           = 20
P_OLD_W           = 250.0
HOURS_PER_YEAR    = 8760
MAX_GEN           = 30

CI_SCENARIOS: Dict[str, int] = {
    'nuclear_fr':   50,
    'norway_hydro': 100,
    'eu_avg':       300,
    'us_avg':       400,
    'uk_grid':      500,
    'coal_pl':      800,
}

# ─── DP Table & Policy (copied from simulate-lifecycle-v3.py) ─────────────────

def build_dp_table(ci_g_per_kwh, eff_gain, emb_kg, p_old_w, hours_per_year, horizon, max_gen=MAX_GEN):
    def op_carbon(g, ci):
        return (p_old_w * ((1 - eff_gain) ** g) / 1000.0) * hours_per_year * (ci / 1000.0)

    V = np.zeros((max_gen + 1, horizon + 1), dtype=np.float64)
    for yr in range(1, horizon + 1):
        for g in range(max_gen + 1):
            wait    = op_carbon(g, ci_g_per_kwh) + V[g, yr - 1]
            replace = (emb_kg + op_carbon(g + 1, ci_g_per_kwh) + V[g + 1, yr - 1]
                       if g + 1 <= max_gen else float('inf'))
            V[g, yr] = min(wait, replace)
    return V


def dp_should_replace(gen, years_remaining, V, ci_g_per_kwh, eff_gain, emb_kg, p_old_w, hours_per_year):
    if years_remaining <= 0 or gen + 1 > MAX_GEN:
        return False
    def op(g):
        return (p_old_w * ((1 - eff_gain) ** g) / 1000.0) * hours_per_year * (ci_g_per_kwh / 1000.0)
    wait    = op(gen)     + V[gen,     years_remaining - 1]
    replace = emb_kg + op(gen + 1) + V[gen + 1, years_remaining - 1]
    return replace < wait


# ─── Fleet Simulation ─────────────────────────────────────────────────────────

def run_single(policy, ci_val, emb_kg, seed,
               horizon=GPU_HORIZON, fleet_size=GPU_FLEET_SIZE,
               eff_gain=GPU_EFF_GAIN, p_old_w=P_OLD_W,
               hours_per_year=HOURS_PER_YEAR, refresh_norm=GPU_REFRESH_NORM,
               max_useful_age=GPU_MAX_AGE, dp_table=None):
    """Run one (policy, seed) combination; return total_carbon."""
    rng = np.random.default_rng(seed)

    # Parse fixed period
    if policy.startswith('fixed_'):
        fixed_n = int(policy.split('_')[1])

    # Initialise fleet with staggered ages
    ages = [float(rng.integers(0, max(1, refresh_norm))) for _ in range(fleet_size)]
    gens = [0] * fleet_size
    total_carbon = emb_kg * fleet_size  # sunk embodied at t=0

    for year in range(horizon):
        years_remaining = horizon - year
        year_carbon = 0.0
        for i in range(fleet_size):
            should_replace = False
            if policy == 'dp_optimal':
                should_replace = dp_should_replace(
                    gens[i], years_remaining, dp_table,
                    ci_val, eff_gain, emb_kg, p_old_w, hours_per_year)
            elif policy.startswith('fixed_'):
                should_replace = (ages[i] >= fixed_n)

            if max_useful_age is not None and ages[i] >= max_useful_age:
                should_replace = True

            if should_replace:
                year_carbon += emb_kg
                ages[i] = 0.0
                gens[i] += 1

            # operational carbon this year
            p_w = p_old_w * ((1 - eff_gain) ** gens[i])
            year_carbon += (p_w / 1000.0) * hours_per_year * (ci_val / 1000.0)
            ages[i] += 1.0

        total_carbon += year_carbon

    return total_carbon


def run_condition(policy, ci_val, emb_kg, n_seeds=N_SEEDS, dp_table=None):
    carbons = [run_single(policy, ci_val, emb_kg, seed=s, dp_table=dp_table)
               for s in range(n_seeds)]
    return float(np.mean(carbons)), float(np.std(carbons))


# ─── Main Sweep ───────────────────────────────────────────────────────────────

print("=" * 70)
print("EMBODIED CARBON SENSITIVITY ANALYSIS")
print(f"  Sweep: emb_kg ∈ {EMB_KG_SWEEP} kgCO₂")
print(f"  CI scenarios: {list(CI_SCENARIOS.values())} g/kWh")
print(f"  GPU inference: max_age={GPU_MAX_AGE}yr, eff={GPU_EFF_GAIN}/gen, norm={GPU_REFRESH_NORM}yr")
print(f"  Fleet: N={GPU_FLEET_SIZE}, H={GPU_HORIZON}yr, seeds={N_SEEDS}")
print("=" * 70)

results = {}  # results[emb_kg][ci_name] = {dp_savings, heuristic4_savings, ...}

for emb_kg in EMB_KG_SWEEP:
    print(f"\n── emb_kg = {emb_kg} kgCO₂ ──")
    results[emb_kg] = {}

    for ci_name, ci_val in CI_SCENARIOS.items():
        dp_table = build_dp_table(ci_val, GPU_EFF_GAIN, emb_kg, P_OLD_W, HOURS_PER_YEAR, GPU_HORIZON)

        c_fixed2_mean, c_fixed2_std = run_condition('fixed_2', ci_val, emb_kg)
        c_dp_mean,     c_dp_std     = run_condition('dp_optimal', ci_val, emb_kg, dp_table=dp_table)
        c_fixed4_mean, c_fixed4_std = run_condition('fixed_4', ci_val, emb_kg)

        dp_save      = (c_fixed2_mean - c_dp_mean)     / c_fixed2_mean * 100 if c_fixed2_mean > 0 else 0.0
        heuristic_save = (c_fixed2_mean - c_fixed4_mean) / c_fixed2_mean * 100 if c_fixed2_mean > 0 else 0.0

        print(f"  {ci_name:>14} ({ci_val:>4} g/kWh): "
              f"DP={dp_save:+.1f}%, Fixed-4yr={heuristic_save:+.1f}% vs Fixed-2yr")

        results[emb_kg][ci_name] = {
            'ci': ci_val,
            'fixed2_mean': c_fixed2_mean,
            'fixed2_std':  c_fixed2_std,
            'dp_mean':     c_dp_mean,
            'dp_std':      c_dp_std,
            'fixed4_mean': c_fixed4_mean,
            'fixed4_std':  c_fixed4_std,
            'dp_savings_pct':       float(dp_save),
            'heuristic4_savings_pct': float(heuristic_save),
        }


# ─── Acceptance Criterion: min emb_kg where DP savings ≥ 2% at EU avg (300) ──
eu_ci_name = 'eu_avg'
min_emb_for_2pct_dp = None
for emb_kg in EMB_KG_SWEEP:
    dp_save = results[emb_kg][eu_ci_name]['dp_savings_pct']
    if dp_save >= 2.0:
        min_emb_for_2pct_dp = emb_kg
        break  # EMB_KG_SWEEP is ordered smallest first

min_emb_for_5pct_dp = None
for emb_kg in EMB_KG_SWEEP:
    dp_save = results[emb_kg][eu_ci_name]['dp_savings_pct']
    if dp_save >= 5.0:
        min_emb_for_5pct_dp = emb_kg
        break

min_emb_for_5pct_h4 = None
for emb_kg in EMB_KG_SWEEP:
    h4_save = results[emb_kg][eu_ci_name]['heuristic4_savings_pct']
    if h4_save >= 5.0:
        min_emb_for_5pct_h4 = emb_kg
        break

print(f"\n── ACCEPTANCE CRITERION ──")
print(f"  Min emb_kg where DP-Optimal savings ≥ 2% at EU avg (300 g/kWh): {min_emb_for_2pct_dp} kgCO₂")
print(f"  Min emb_kg where DP-Optimal savings ≥ 5% at EU avg (300 g/kWh): {min_emb_for_5pct_dp} kgCO₂")
print(f"  Min emb_kg where Fixed-4yr savings ≥ 5% at EU avg (300 g/kWh):  {min_emb_for_5pct_h4} kgCO₂")


# ─── Save JSON Results ────────────────────────────────────────────────────────

os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'results'), exist_ok=True)
results_path = os.path.join(os.path.dirname(__file__), '..', 'results', 'sensitivity-embodied.json')

output = {
    'metadata': {
        'script': 'sensitivity-embodied.py',
        'scenario': 'GPU inference (max_age=4yr, eff_gain=0.50, norm=2yr, H=10yr, N=50)',
        'sweep_parameter': 'emb_kg (kgCO₂)',
        'emb_kg_values': EMB_KG_SWEEP,
        'ci_scenarios': CI_SCENARIOS,
        'seeds': N_SEEDS,
        'policies': {
            'fixed_2': 'Fixed-2yr (AI industry norm baseline)',
            'dp_optimal': 'DP-Optimal (backward-induction, globally optimal)',
            'fixed_4': 'Fixed-4yr (paper heuristic recommendation)',
        },
    },
    'acceptance_criterion': {
        'question': 'Min emb_kg where DP savings ≥ 2% at EU avg CI (300 g/kWh)',
        'answer_kg': min_emb_for_2pct_dp,
        'min_emb_for_5pct_dp_eu_avg': min_emb_for_5pct_dp,
        'min_emb_for_5pct_heuristic4_eu_avg': min_emb_for_5pct_h4,
    },
    'results': {str(k): v for k, v in results.items()},
}

with open(results_path, 'w') as f:
    json.dump(output, f, indent=2)
print(f"\nSaved results to {results_path}")


# ─── Figure ───────────────────────────────────────────────────────────────────

fig_dir = os.path.join(os.path.dirname(__file__), 'figures')
os.makedirs(fig_dir, exist_ok=True)
fig_path = os.path.join(fig_dir, 'fig_sensitivity_embodied.png')

ci_colors = {
    'nuclear_fr':   '#1a6b1a',
    'norway_hydro': '#2980b9',
    'eu_avg':       '#e67e22',
    'us_avg':       '#e74c3c',
    'uk_grid':      '#8e44ad',
    'coal_pl':      '#2c3e50',
}
ci_labels = {
    'nuclear_fr':   'Nuclear FR (50 g/kWh)',
    'norway_hydro': 'Norway Hydro (100 g/kWh)',
    'eu_avg':       'EU Average (300 g/kWh)',
    'us_avg':       'US Average (400 g/kWh)',
    'uk_grid':      'UK Grid (500 g/kWh)',
    'coal_pl':      'Coal PL (800 g/kWh)',
}

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle(
    "GPU Embodied Carbon Sensitivity Analysis\n"
    "GPU Inference Fleet: N=50, H=10yr, eff=50%/gen, max_age=4yr, norm=2yr, 20 seeds",
    fontsize=12, fontweight='bold'
)

emb_vals = EMB_KG_SWEEP

for ax_idx, (policy_key, policy_label, linestyle) in enumerate([
    ('dp_savings_pct',       'DP-Optimal savings vs Fixed-2yr (%)',       '-'),
]):
    ax = axes[0]
    for ci_name in CI_SCENARIOS:
        ys = [results[e][ci_name][policy_key] for e in emb_vals]
        ax.plot(emb_vals, ys, marker='o', linewidth=2, markersize=6,
                color=ci_colors[ci_name], label=ci_labels[ci_name])

    ax.axhline(0, color='black', linewidth=1.0, linestyle='--', alpha=0.6, label='Break-even (0%)')
    ax.axhline(5, color='gray',  linewidth=1.0, linestyle=':', alpha=0.8, label='Viable threshold (5%)')
    ax.set_xlabel("GPU Embodied Carbon, emb_kg (kgCO₂)", fontsize=11)
    ax.set_ylabel("Savings vs Fixed-2yr (%)", fontsize=11)
    ax.set_title("DP-Optimal Savings", fontsize=11)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(True, alpha=0.3)
    ax.set_xticks(emb_vals)
    ax.tick_params(axis='x', rotation=20)

    # Mark min_emb_for_2pct_dp on eu_avg line
    if min_emb_for_2pct_dp is not None:
        eu_y = results[min_emb_for_2pct_dp]['eu_avg']['dp_savings_pct']
        ax.annotate(
            f"≥2% threshold\nat {min_emb_for_2pct_dp} kgCO₂",
            xy=(min_emb_for_2pct_dp, eu_y),
            xytext=(min_emb_for_2pct_dp + 200, eu_y - 4),
            arrowprops=dict(arrowstyle='->', color='#e67e22'),
            fontsize=8, color='#e67e22',
        )

ax2 = axes[1]
for ci_name in CI_SCENARIOS:
    ys = [results[e][ci_name]['heuristic4_savings_pct'] for e in emb_vals]
    ax2.plot(emb_vals, ys, marker='s', linewidth=2, markersize=6,
             linestyle='--', color=ci_colors[ci_name], label=ci_labels[ci_name])

ax2.axhline(0, color='black', linewidth=1.0, linestyle='--', alpha=0.6, label='Break-even (0%)')
ax2.axhline(5, color='gray',  linewidth=1.0, linestyle=':', alpha=0.8, label='Viable threshold (5%)')
ax2.set_xlabel("GPU Embodied Carbon, emb_kg (kgCO₂)", fontsize=11)
ax2.set_ylabel("Savings vs Fixed-2yr (%)", fontsize=11)
ax2.set_title("Fixed-4yr (Heuristic) Savings", fontsize=11)
ax2.legend(fontsize=8, loc='lower right')
ax2.grid(True, alpha=0.3)
ax2.set_xticks(emb_vals)
ax2.tick_params(axis='x', rotation=20)

plt.tight_layout()
plt.savefig(fig_path, dpi=300, bbox_inches='tight')
plt.close()
print(f"Saved figure to {fig_path}")

print("\n[DONE] sensitivity-embodied.py complete.")
print(f"  min emb_kg for DP savings ≥ 2% @ EU avg: {min_emb_for_2pct_dp} kgCO₂")
print(f"  min emb_kg for DP savings ≥ 5% @ EU avg: {min_emb_for_5pct_dp} kgCO₂")
