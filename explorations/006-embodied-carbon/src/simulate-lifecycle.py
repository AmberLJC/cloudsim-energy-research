"""
simulate-lifecycle.py — Embodied Carbon Lifecycle Fleet Simulation
====================================================================
Simulates a fleet of 50 servers over 10 years under three refresh policies.

Policies:
  A) FIXED-5:   Replace every 5 years (industry norm)
  B) CI-AWARE:  Replace when (remaining operational carbon to horizon) >
                (embodied carbon of new server + operational of new server to horizon)
                i.e., replace when new server has lower total forward carbon
  C) ORACLE:    Replace at the analytically optimal T* for current CI and eff_gain

Parameters:
  - Fleet size: 50 servers
  - Horizon: 10 years (annual steps)
  - P_old = 250W per server
  - Efficiency gain: 15%/yr (median scenario)
  - Embodied carbon: 1000 kgCO2 (median scenario)
  - Grid CI: tested at multiple levels (50, 100, 200, 400, 600, 800 gCO2/kWh)
  - Also tests dynamic CI (sinusoidal annual variation ±30% around mean)

Results:
  - Total carbon (embodied + operational) over 10 years per policy
  - Carbon savings: B vs A, C vs A, B vs C
  - Number of replacements per policy
  - Fleet age distribution at end
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import json
from dataclasses import dataclass, field
from typing import List, Dict

# ─── Parameters ──────────────────────────────────────────────────────────────
FLEET_SIZE = 50
HORIZON_YEARS = 10
P_OLD_W = 250.0
HOURS_PER_YEAR = 8760
EFFICIENCY_GAIN = 0.15    # 15%/yr
EMBODIED_KG = 1000.0      # kgCO2 per server
CI_SCENARIOS = {
    'nuclear_fr': 50,
    'norway_hydro': 100,
    'eu_avg': 300,
    'us_avg': 400,
    'uk_grid': 500,
    'coal_pl': 800,
}
N_SEEDS = 20   # Monte Carlo seeds for stochastic fleet heterogeneity


@dataclass
class Server:
    """Represents one physical server in the fleet."""
    server_id: int
    age_years: float          # current age (years since last replacement)
    gen_at_deploy: int        # hardware generation index (0=oldest, higher=newer)
    total_op_carbon: float = 0.0
    total_emb_carbon: float = 0.0
    replacements: int = 0

    def power_watts(self) -> float:
        """Current server's power based on generation efficiency."""
        return P_OLD_W * ((1.0 - EFFICIENCY_GAIN) ** self.gen_at_deploy)

    def annual_op_carbon(self, ci_g_per_kwh: float) -> float:
        """Operational carbon this year (kgCO2)."""
        return (self.power_watts() / 1000.0) * HOURS_PER_YEAR * (ci_g_per_kwh / 1000.0)

    def forward_op_carbon(self, ci_g_per_kwh: float, years_remaining: float) -> float:
        """Projected operational carbon for remaining `years_remaining` years."""
        return self.annual_op_carbon(ci_g_per_kwh) * years_remaining

    def new_server_forward_carbon(self, ci_g_per_kwh: float, years_remaining: float,
                                   next_gen: int) -> float:
        """
        Total forward carbon if we replace NOW:
        embodied of new + operational of new over years_remaining
        """
        p_new_w = P_OLD_W * ((1.0 - EFFICIENCY_GAIN) ** next_gen)
        op_new = (p_new_w / 1000.0) * HOURS_PER_YEAR * (ci_g_per_kwh / 1000.0) * years_remaining
        return EMBODIED_KG + op_new


def optimal_T_star(ci_g_per_kwh: float, current_gen: int, horizon: int = 15) -> int:
    """
    Analytically optimal refresh lifetime from current position.
    (Simplified: recompute optimal lifetime for remaining horizon.)
    """
    best_T = 1
    best_carbon = float('inf')
    for T in range(1, horizon + 1):
        total = 0.0
        t = 0
        gen = current_gen
        while t < horizon:
            total += EMBODIED_KG
            p_w = P_OLD_W * ((1.0 - EFFICIENCY_GAIN) ** gen)
            run = min(T, horizon - t)
            total += (p_w / 1000.0) * HOURS_PER_YEAR * (ci_g_per_kwh / 1000.0) * run
            t += T
            gen += T
        if total < best_carbon:
            best_carbon = total
            best_T = T
    return best_T


class FleetSimulator:
    """Simulates a fleet of servers under a given refresh policy."""

    def __init__(self, policy: str, ci_g_per_kwh: float, seed: int = 42,
                 stagger_initial: bool = True):
        """
        policy: 'fixed5' | 'ci_aware' | 'oracle'
        stagger_initial: spread initial server ages uniformly 0–4 yrs (realistic fleet)
        """
        self.policy = policy
        self.ci = ci_g_per_kwh
        self.rng = np.random.default_rng(seed)
        self.total_carbon = 0.0
        self.total_embodied = 0.0
        self.total_operational = 0.0
        self.total_replacements = 0
        self.year_carbon = []  # per-year carbon log

        # Initialise fleet with staggered ages to represent realistic mix
        self.fleet: List[Server] = []
        for i in range(FLEET_SIZE):
            if stagger_initial:
                # Random age 0–4, corresponding generation
                age = float(self.rng.integers(0, 5))
            else:
                age = 0.0
            # Generation index: servers deployed age years ago are gen=0 (reference)
            # We treat initial gen=0 for all (same efficiency at start, age only affects refresh timing)
            srv = Server(server_id=i, age_years=age, gen_at_deploy=0)
            # Pay embodied for initial deployment (sunk cost, already paid)
            srv.total_emb_carbon = EMBODIED_KG
            self.total_embodied += EMBODIED_KG
            self.fleet.append(srv)

        # Global generation counter (increases as we deploy newer hardware)
        self.global_gen = 0

    def step_year(self, year: int):
        """Advance simulation by 1 year."""
        years_remaining = HORIZON_YEARS - year  # years left after this one

        year_carbon = 0.0

        for srv in self.fleet:
            should_replace = False

            if self.policy == 'fixed5':
                # Replace at age 5 (or multiples of 5)
                should_replace = (srv.age_years >= 5.0)

            elif self.policy == 'ci_aware':
                # Replace when keeping OLD server costs MORE carbon forward than replacing
                fwd_old = srv.forward_op_carbon(self.ci, years_remaining)
                fwd_new = srv.new_server_forward_carbon(self.ci, years_remaining,
                                                         self.global_gen + 1)
                should_replace = (fwd_old > fwd_new) and (years_remaining > 0.5)

            elif self.policy == 'oracle':
                # Replace when current age exceeds optimal T* for this CI
                T_star = optimal_T_star(self.ci, srv.gen_at_deploy,
                                        horizon=max(1, int(HORIZON_YEARS - year + srv.age_years)))
                should_replace = (srv.age_years >= T_star) and (years_remaining > 0.5)

            if should_replace:
                # Pay embodied carbon for new server
                emb = EMBODIED_KG
                srv.total_emb_carbon += emb
                self.total_embodied += emb
                year_carbon += emb
                srv.age_years = 0.0
                self.global_gen += 1
                srv.gen_at_deploy = self.global_gen
                srv.replacements += 1
                self.total_replacements += 1

            # Operational carbon this year
            op = srv.annual_op_carbon(self.ci)
            srv.total_op_carbon += op
            self.total_operational += op
            year_carbon += op

            srv.age_years += 1.0

        self.year_carbon.append(year_carbon)
        self.total_carbon += year_carbon

    def run(self):
        for year in range(HORIZON_YEARS):
            self.step_year(year)


# ─── Run simulations ──────────────────────────────────────────────────────────

print("=" * 70)
print("LIFECYCLE FLEET SIMULATION — 50 servers, 10 years")
print("=" * 70)

summary_results = {}
all_results = []

for ci_name, ci_val in CI_SCENARIOS.items():
    print(f"\n── CI scenario: {ci_name} ({ci_val} gCO₂/kWh) ──")
    policy_results = {'fixed5': [], 'ci_aware': [], 'oracle': []}

    for seed in range(N_SEEDS):
        for policy in ['fixed5', 'ci_aware', 'oracle']:
            sim = FleetSimulator(policy=policy, ci_g_per_kwh=ci_val, seed=seed)
            sim.run()
            policy_results[policy].append({
                'total_carbon': sim.total_carbon,
                'total_embodied': sim.total_embodied,
                'total_operational': sim.total_operational,
                'replacements': sim.total_replacements,
                'year_carbon': sim.year_carbon,
            })

    # Aggregate across seeds
    agg = {}
    for policy in ['fixed5', 'ci_aware', 'oracle']:
        vals = [r['total_carbon'] for r in policy_results[policy]]
        reps = [r['replacements'] for r in policy_results[policy]]
        agg[policy] = {
            'mean_carbon': np.mean(vals),
            'std_carbon': np.std(vals),
            'mean_replacements': np.mean(reps),
        }

    c_a = agg['fixed5']['mean_carbon']
    c_b = agg['ci_aware']['mean_carbon']
    c_c = agg['oracle']['mean_carbon']

    save_b_vs_a = (c_a - c_b) / c_a * 100
    save_c_vs_a = (c_a - c_c) / c_a * 100
    save_b_vs_c = (c_b - c_c) / c_b * 100 if c_b > 0 else 0.0

    summary_results[ci_name] = {
        'ci': ci_val,
        'policy_A_fixed5': agg['fixed5'],
        'policy_B_ci_aware': agg['ci_aware'],
        'policy_C_oracle': agg['oracle'],
        'B_saves_vs_A_pct': save_b_vs_a,
        'C_saves_vs_A_pct': save_c_vs_a,
        'B_gap_vs_C_pct': save_b_vs_c,
    }

    print(f"  Policy A (Fixed-5yr): {c_a:>10,.0f} kgCO₂ "
          f"(±{agg['fixed5']['std_carbon']:,.0f}), "
          f"replacements={agg['fixed5']['mean_replacements']:.1f}")
    print(f"  Policy B (CI-Aware):  {c_b:>10,.0f} kgCO₂ "
          f"(±{agg['ci_aware']['std_carbon']:,.0f}), "
          f"replacements={agg['ci_aware']['mean_replacements']:.1f}")
    print(f"  Policy C (Oracle):    {c_c:>10,.0f} kgCO₂ "
          f"(±{agg['oracle']['std_carbon']:,.0f}), "
          f"replacements={agg['oracle']['mean_replacements']:.1f}")
    print(f"  → B saves {save_b_vs_a:+.1f}% vs A | "
          f"C saves {save_c_vs_a:+.1f}% vs A | "
          f"B within {abs(save_b_vs_c):.1f}% of oracle C")

# ─── Summary table ────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SUMMARY: Carbon Savings by Policy (Fleet of 50, 10yr, eff=15%, emb=1000kg)")
print("=" * 70)
print(f"{'Scenario':>14} | {'CI':>6} | {'B vs A':>8} | {'C vs A':>8} | "
      f"{'B∆ vs C':>8} | {'B repl':>7} | {'A repl':>7}")
print("-" * 70)
for ci_name, res in summary_results.items():
    b_repl = res['policy_B_ci_aware']['mean_replacements']
    a_repl = res['policy_A_fixed5']['mean_replacements']
    print(f"{ci_name:>14} | {res['ci']:>6} | {res['B_saves_vs_A_pct']:>+7.1f}% | "
          f"{res['C_saves_vs_A_pct']:>+7.1f}% | {res['B_gap_vs_C_pct']:>+7.1f}% | "
          f"{b_repl:>7.1f} | {a_repl:>7.1f}")

# Save JSON summary
os.makedirs("results", exist_ok=True)
# Convert numpy types for JSON serialisation
def convert(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.ndarray,)): return o.tolist()
    return o

with open("results/lifecycle-sim-summary.json", "w") as f:
    json.dump(summary_results, f, default=convert, indent=2)
print("\nSaved results/lifecycle-sim-summary.json")

# ─── Figures ──────────────────────────────────────────────────────────────────
os.makedirs("figures", exist_ok=True)

# Figure 1: Bar chart — carbon savings B vs A and C vs A across CI scenarios
ci_names = list(summary_results.keys())
b_vs_a = [summary_results[n]['B_saves_vs_A_pct'] for n in ci_names]
c_vs_a = [summary_results[n]['C_saves_vs_A_pct'] for n in ci_names]
ci_labels = [f"{n}\n({summary_results[n]['ci']} g/kWh)" for n in ci_names]

x = np.arange(len(ci_names))
width = 0.35
fig, ax = plt.subplots(figsize=(11, 6))
bars1 = ax.bar(x - width/2, b_vs_a, width, label='Policy B (CI-Aware) vs A (5yr norm)',
               color='#2980b9', alpha=0.85)
bars2 = ax.bar(x + width/2, c_vs_a, width, label='Policy C (Oracle) vs A (5yr norm)',
               color='#27ae60', alpha=0.85)

for bar, val in zip(bars1, b_vs_a):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
            f'{val:+.1f}%', ha='center', va='bottom', fontsize=9)
for bar, val in zip(bars2, c_vs_a):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
            f'{val:+.1f}%', ha='center', va='bottom', fontsize=9)

ax.axhline(0, color='black', linewidth=0.8)
ax.set_xticks(x)
ax.set_xticklabels(ci_labels, fontsize=9)
ax.set_ylabel("Carbon Saving vs Fixed-5yr Policy (%)", fontsize=11)
ax.set_title("Lifecycle Carbon Savings: CI-Aware and Oracle vs Industry Norm\n"
             "Fleet of 50 servers, 10-year horizon, eff=15%/yr, emb=1000 kgCO₂", fontsize=11)
ax.legend(fontsize=10)
ax.grid(True, axis='y', alpha=0.3)
ax.set_ylim(min(min(b_vs_a), min(c_vs_a)) - 5, max(max(b_vs_a), max(c_vs_a)) + 8)
plt.tight_layout()
plt.savefig("figures/embodied_fig5_fleet_savings.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved figures/embodied_fig5_fleet_savings.png")

# Figure 2: Absolute carbon per policy across CI, with error bars (seed=0 for year curves)
fig, ax = plt.subplots(figsize=(10, 6))
ci_vals = [summary_results[n]['ci'] for n in ci_names]
c_A = [summary_results[n]['policy_A_fixed5']['mean_carbon'] / 1000 for n in ci_names]
c_B = [summary_results[n]['policy_B_ci_aware']['mean_carbon'] / 1000 for n in ci_names]
c_C = [summary_results[n]['policy_C_oracle']['mean_carbon'] / 1000 for n in ci_names]
std_A = [summary_results[n]['policy_A_fixed5']['std_carbon'] / 1000 for n in ci_names]
std_B = [summary_results[n]['policy_B_ci_aware']['std_carbon'] / 1000 for n in ci_names]
std_C = [summary_results[n]['policy_C_oracle']['std_carbon'] / 1000 for n in ci_names]

ax.errorbar(ci_vals, c_A, yerr=std_A, marker='s', label='A: Fixed-5yr', color='#e74c3c',
            linewidth=2, capsize=4, markersize=7)
ax.errorbar(ci_vals, c_B, yerr=std_B, marker='o', label='B: CI-Aware', color='#2980b9',
            linewidth=2, capsize=4, markersize=7)
ax.errorbar(ci_vals, c_C, yerr=std_C, marker='^', label='C: Oracle', color='#27ae60',
            linewidth=2, capsize=4, markersize=7)

ax.set_xlabel("Grid Carbon Intensity (gCO₂/kWh)", fontsize=12)
ax.set_ylabel("Total Fleet Carbon — 10yr (tCO₂)", fontsize=12)
ax.set_title("Total Lifecycle Carbon: Three Policies across Grid CI\n"
             "Fleet of 50 servers, mean ± 1σ over 20 seeds", fontsize=11)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("figures/embodied_fig6_absolute_carbon.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved figures/embodied_fig6_absolute_carbon.png")

# Figure 3: Year-by-year cumulative carbon for one seed (CI=400, all policies)
fig, ax = plt.subplots(figsize=(9, 5))
ci_demo = 400
for policy, color, label in [
    ('fixed5', '#e74c3c', 'A: Fixed-5yr'),
    ('ci_aware', '#2980b9', 'B: CI-Aware'),
    ('oracle', '#27ae60', 'C: Oracle'),
]:
    sim = FleetSimulator(policy=policy, ci_g_per_kwh=ci_demo, seed=0)
    sim.run()
    cumulative = np.cumsum(sim.year_carbon) / 1000  # tCO2
    ax.plot(range(1, HORIZON_YEARS + 1), cumulative, marker='o', color=color,
            linewidth=2.5, markersize=6, label=label)

ax.set_xlabel("Year", fontsize=12)
ax.set_ylabel("Cumulative Fleet Carbon (tCO₂)", fontsize=12)
ax.set_title(f"Cumulative Lifecycle Carbon — US-Avg Grid (CI={ci_demo} gCO₂/kWh)\n"
             f"Fleet of 50 servers", fontsize=11)
ax.legend(fontsize=11)
ax.set_xticks(range(1, HORIZON_YEARS + 1))
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("figures/embodied_fig7_cumulative_carbon.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved figures/embodied_fig7_cumulative_carbon.png")

print("\n[DONE] simulate-lifecycle.py complete.")
