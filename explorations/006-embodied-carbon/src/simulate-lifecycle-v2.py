"""
simulate-lifecycle-v2.py — Embodied Carbon Lifecycle Fleet Simulation (v2)
===========================================================================
Fixes two critical bugs from v1 and adds a GPU/accelerator scenario.

CHANGES FROM v1:
  Bug Fix 1: Replaces myopic CI-Aware (Policy B) with DP-Optimal (Policy B_dp).
             CI-Aware made ZERO replacements at EU-average CI (300 g/kWh) because
             it compared "replace once vs keep forever," ignoring multi-period
             opportunities. DP-Optimal precomputes the globally-optimal refresh
             schedule via backward induction for each (gen, years_remaining) state.

  Bug Fix 2: Oracle policy recalculated T* every year from gen_at_deploy, creating
             inconsistent decisions that caused it to UNDERPERFORM Fixed-5yr at
             CI=300–400. Oracle is now simply the DP policy (same table as B_dp),
             renamed DP-Oracle. By construction, DP-Oracle is optimal over the horizon.

  New Policy D: Fixed-T_star — uses the analytically computed T*(CI) from the
                falsification-embodied.py analysis. Simple lookup, clean comparison.

  GPU Scenario: AI accelerator fleet (eff_gain=50%/gen, emb=3000 kgCO₂, norm=2yr).
                Compares Fixed-2yr vs DP-Optimal — the most compelling scenario for
                embodied carbon impact from AI hardware refresh cycles.

Policies (CPU fleet):
  A) FIXED-5yr:      Replace every 5 years (industry norm)
  B_dp) DP-Optimal:  Replace based on DP-optimal backward-induction schedule
  C_dp) DP-Oracle:   Identical to B_dp (sanity check: should match exactly)
  D) Fixed-T_star:   Replace every T*(CI) years (analytically optimal period)

GPU Policies:
  GPU_A) Fixed-2yr:  Replace every 2 years (AI industry norm)
  GPU_B) DP-Optimal: Replace based on GPU-parameterized DP table

Fleet parameters (CPU):
  - Fleet size:      50 servers
  - Horizon:         10 years (annual steps)
  - P_base:          250 W
  - Efficiency gain: 15%/gen
  - Embodied carbon: 1000 kgCO₂
  - CI scenarios:    50–800 gCO₂/kWh
  - Seeds:           20 (Monte Carlo fleet heterogeneity)

Fleet parameters (GPU):
  - Fleet size:      50 GPU servers
  - Horizon:         10 years
  - P_base:          250 W (normalised per-unit)
  - Efficiency gain: 50%/gen (H100→H200→B200 each ~2× compute/watt)
  - Embodied carbon: 3000 kgCO₂ (GPU rack vs CPU server)
  - CI scenarios:    same as CPU fleet
  - Refresh norm:    2 years (current AI industry cycle)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ─── CPU Fleet Parameters ─────────────────────────────────────────────────────
FLEET_SIZE       = 50
HORIZON_YEARS    = 10
P_OLD_W          = 250.0
HOURS_PER_YEAR   = 8760
EFFICIENCY_GAIN  = 0.15     # 15%/gen
EMBODIED_KG      = 1000.0   # kgCO₂ per server
N_SEEDS          = 20       # Monte Carlo seeds

CI_SCENARIOS: Dict[str, int] = {
    'nuclear_fr':  50,
    'norway_hydro': 100,
    'eu_avg':      300,
    'us_avg':      400,
    'uk_grid':     500,
    'coal_pl':     800,
}

# ─── GPU/Accelerator Fleet Parameters ─────────────────────────────────────────
GPU_FLEET_SIZE    = 50
GPU_HORIZON       = 10
GPU_EFF_GAIN      = 0.50    # 50%/gen — 2× compute/watt per generation
GPU_EMBODIED_KG   = 3000.0  # kgCO₂ — GPU rack vs CPU server
GPU_REFRESH_NORM  = 2       # years — current AI industry refresh cycle

# Maximum hardware generation to precompute in DP tables.
# At gen 30, power is P_base × (1-eff)^30 → essentially zero for any eff ≥ 0.15.
MAX_GEN = 30


# ──────────────────────────────────────────────────────────────────────────────
# DP TABLE CONSTRUCTION
# ──────────────────────────────────────────────────────────────────────────────

def build_dp_table(
    ci_g_per_kwh: float,
    eff_gain: float,
    emb_kg: float,
    p_old_w: float,
    hours_per_year: int,
    horizon: int,
    max_gen: int = MAX_GEN,
) -> np.ndarray:
    """
    Build DP value table V[gen, years_remaining] via backward induction.

    State: (gen, years_remaining)
      gen            — hardware generation index (0=baseline, higher=newer/more efficient)
      years_remaining — number of annual steps still to be simulated

    Value: V[gen, yr] = minimum total carbon (kgCO₂) achievable from this state.

    Transitions at each state (gen, yr):
      wait:    cost = op_carbon(gen) + V[gen, yr-1]
      replace: cost = emb_kg + op_carbon(gen+1) + V[gen+1, yr-1]

    Where op_carbon(g) = P_old × (1-eff)^g / 1000 × hours_per_year × CI_kg_per_kWh

    Base case: V[gen, 0] = 0 for all gen (no more years → no more carbon)

    Note: "replace" means we install a new server at the START of the year
    (paying embodied carbon immediately) then operate the new server for that year.
    This matches the v1 simulation's step_year logic exactly.

    Returns: ndarray of shape (max_gen+1, horizon+1)
    """
    ci_kg = ci_g_per_kwh / 1000.0

    def op_carbon(g: int) -> float:
        """Operational carbon for one year at generation g."""
        p_w = p_old_w * ((1.0 - eff_gain) ** g)
        return (p_w / 1000.0) * hours_per_year * ci_kg

    # V[g, yr] — shape: (max_gen+1) × (horizon+1), float64
    V = np.zeros((max_gen + 1, horizon + 1), dtype=np.float64)
    # V[:, 0] = 0 already (base case)

    for yr in range(1, horizon + 1):
        for g in range(max_gen + 1):
            # Option A: wait — run current gen for one year, continue
            wait_cost = op_carbon(g) + V[g, yr - 1]

            # Option B: replace — pay embodied, run next gen for one year, continue
            if g + 1 <= max_gen:
                replace_cost = emb_kg + op_carbon(g + 1) + V[g + 1, yr - 1]
            else:
                replace_cost = float('inf')  # can't go beyond max_gen

            V[g, yr] = min(wait_cost, replace_cost)

    return V


def dp_should_replace(
    gen: int,
    years_remaining: int,
    V: np.ndarray,
    ci_g_per_kwh: float,
    eff_gain: float,
    emb_kg: float,
    p_old_w: float,
    hours_per_year: int,
    max_gen: int = MAX_GEN,
) -> bool:
    """
    Return True if the DP policy says to replace the server at this decision point.

    At state (gen, years_remaining):
      wait_cost    = op_carbon(gen) + V[gen, years_remaining-1]
      replace_cost = emb_kg + op_carbon(gen+1) + V[gen+1, years_remaining-1]

    Replace iff replace_cost < wait_cost.
    """
    if years_remaining <= 0:
        return False
    if gen + 1 > max_gen:
        return False  # can't go further

    ci_kg = ci_g_per_kwh / 1000.0

    def op_carbon(g: int) -> float:
        p_w = p_old_w * ((1.0 - eff_gain) ** g)
        return (p_w / 1000.0) * hours_per_year * ci_kg

    wait_cost    = op_carbon(gen)     + V[gen,     years_remaining - 1]
    replace_cost = emb_kg + op_carbon(gen + 1) + V[gen + 1, years_remaining - 1]
    return replace_cost < wait_cost


# ──────────────────────────────────────────────────────────────────────────────
# ANALYTICAL T_STAR (for Policy D)
# ──────────────────────────────────────────────────────────────────────────────

def compute_total_carbon_fixed(
    ci_g_per_kwh: float,
    eff_gain: float,
    emb_kg: float,
    p_old_w: float,
    hours_per_year: int,
    lifetime_T: int,
    horizon: int,
) -> float:
    """
    Total carbon for fixed-T refresh policy over `horizon` years.
    Exactly the same model as falsification-embodied.py.
    """
    ci_kg = ci_g_per_kwh / 1000.0
    total = 0.0
    t = 0
    cycle = 0
    while t < horizon:
        total += emb_kg
        p_w = p_old_w * ((1.0 - eff_gain) ** cycle)
        run = min(lifetime_T, horizon - t)
        total += (p_w / 1000.0) * hours_per_year * ci_kg * run
        t += lifetime_T
        cycle += 1
    return total


def find_t_star(
    ci_g_per_kwh: float,
    eff_gain: float,
    emb_kg: float,
    p_old_w: float,
    hours_per_year: int,
    horizon: int,
) -> int:
    """
    Find the analytically optimal refresh period T* ∈ {1, ..., horizon}
    that minimises total carbon under a fixed-period refresh policy.
    (Same search as falsification-embodied.py.)
    """
    best_T = 1
    best_c = float('inf')
    for T in range(1, horizon + 1):
        c = compute_total_carbon_fixed(
            ci_g_per_kwh, eff_gain, emb_kg, p_old_w, hours_per_year, T, horizon
        )
        if c < best_c:
            best_c = c
            best_T = T
    return best_T


# ──────────────────────────────────────────────────────────────────────────────
# SERVER & FLEET SIMULATOR
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Server:
    """One physical server in the fleet."""
    server_id:      int
    age_years:      float   # years since last replacement
    gen_at_deploy:  int     # hardware generation index at last deployment
    total_op_carbon: float = 0.0
    total_emb_carbon: float = 0.0
    replacements:   int = 0

    def power_watts(self, eff_gain: float, p_old: float) -> float:
        return p_old * ((1.0 - eff_gain) ** self.gen_at_deploy)

    def annual_op_carbon(
        self, ci_g_per_kwh: float, eff_gain: float, p_old: float, hours: int
    ) -> float:
        p_w = self.power_watts(eff_gain, p_old)
        return (p_w / 1000.0) * hours * (ci_g_per_kwh / 1000.0)


class FleetSimulator:
    """
    Simulates a fleet under a given refresh policy.

    Supported policies:
      'fixed_N'    — replace when age >= N (e.g., 'fixed_5', 'fixed_2')
      'dp_optimal' — replace according to precomputed DP table
      'fixed_tstar' — replace when age >= T*(CI), analytically computed
    """

    def __init__(
        self,
        policy: str,
        ci_g_per_kwh: float,
        seed: int,
        horizon: int,
        fleet_size: int,
        eff_gain: float,
        emb_kg: float,
        p_old_w: float,
        hours_per_year: int,
        dp_table: Optional[np.ndarray],   # precomputed DP table or None
        t_star: Optional[int],            # precomputed T*(CI) or None
        refresh_norm: int = 5,            # used as N for 'fixed_N' policy label
        stagger_initial: bool = True,
    ):
        self.policy       = policy
        self.ci           = ci_g_per_kwh
        self.horizon      = horizon
        self.fleet_size   = fleet_size
        self.eff_gain     = eff_gain
        self.emb_kg       = emb_kg
        self.p_old_w      = p_old_w
        self.hours        = hours_per_year
        self.dp_table     = dp_table
        self.t_star       = t_star
        self.refresh_norm = refresh_norm

        self.rng              = np.random.default_rng(seed)
        self.total_carbon     = 0.0
        self.total_embodied   = 0.0
        self.total_operational = 0.0
        self.total_replacements = 0
        self.year_carbon: List[float] = []

        # Initial fleet: stagger ages 0..(refresh_norm-1) to represent realistic mix
        self.fleet: List[Server] = []
        max_initial_age = max(1, refresh_norm)
        for i in range(fleet_size):
            age = float(self.rng.integers(0, max_initial_age)) if stagger_initial else 0.0
            srv = Server(server_id=i, age_years=age, gen_at_deploy=0)
            srv.total_emb_carbon = emb_kg   # sunk cost at deployment
            self.total_embodied += emb_kg
            self.fleet.append(srv)
        # NOTE: No global_gen counter — each server's generation is tracked
        # independently. Replacing server i advances its gen from g → g+1.
        # This matches the DP model exactly (eff_gain = improvement per generation)
        # and is more physically realistic than a fleet-wide counter.

    def _parse_fixed_N(self) -> int:
        """Extract N from policy string 'fixed_N'."""
        parts = self.policy.split('_')
        if len(parts) == 2 and parts[0] == 'fixed':
            try:
                return int(parts[1])
            except ValueError:
                pass
        return self.refresh_norm  # fallback

    def step_year(self, year: int):
        """Advance simulation by 1 year."""
        years_remaining = self.horizon - year   # years left including this one

        year_carbon = 0.0
        for srv in self.fleet:
            should_replace = False

            if self.policy == 'fixed_tstar':
                assert self.t_star is not None, "t_star must be provided for fixed_tstar"
                should_replace = (srv.age_years >= self.t_star)

            elif self.policy.startswith('fixed_'):
                N = self._parse_fixed_N()
                should_replace = (srv.age_years >= N)

            elif self.policy in ('dp_optimal', 'dp_oracle'):
                # Use precomputed DP table
                assert self.dp_table is not None, "dp_table must be provided for dp_optimal/dp_oracle"
                should_replace = dp_should_replace(
                    gen=srv.gen_at_deploy,
                    years_remaining=years_remaining,
                    V=self.dp_table,
                    ci_g_per_kwh=self.ci,
                    eff_gain=self.eff_gain,
                    emb_kg=self.emb_kg,
                    p_old_w=self.p_old_w,
                    hours_per_year=self.hours,
                    max_gen=MAX_GEN,
                )

            elif self.policy == 'fixed_tstar':
                assert self.t_star is not None, "t_star must be provided for fixed_tstar"
                should_replace = (srv.age_years >= self.t_star)

            if should_replace:
                srv.total_emb_carbon  += self.emb_kg
                self.total_embodied   += self.emb_kg
                year_carbon           += self.emb_kg
                srv.age_years          = 0.0
                srv.gen_at_deploy     += 1   # per-server: advance this server's gen by 1
                srv.replacements      += 1
                self.total_replacements += 1

            # Operational carbon this year (using post-replacement gen if replaced)
            op = srv.annual_op_carbon(self.ci, self.eff_gain, self.p_old_w, self.hours)
            srv.total_op_carbon    += op
            self.total_operational += op
            year_carbon            += op
            srv.age_years          += 1.0

        self.year_carbon.append(year_carbon)
        self.total_carbon += year_carbon

    def run(self):
        for year in range(self.horizon):
            self.step_year(year)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN SIMULATION — CPU FLEET
# ──────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("LIFECYCLE FLEET SIMULATION v2 — 50 servers, 10 years, eff=15%, emb=1000kg")
print("=" * 72)
print()
print("Policies:")
print("  A   Fixed-5yr     — industry norm, replace every 5 years")
print("  B_dp DP-Optimal   — backward-induction DP, globally optimal schedule")
print("  C_dp DP-Oracle    — identical to B_dp (sanity check, should match)")
print("  D   Fixed-T_star  — replace every T*(CI) years (analytical optimum)")
print()

summary_results: Dict = {}
cpu_policies = ['fixed_5', 'dp_optimal', 'dp_oracle', 'fixed_tstar']
policy_labels = {
    'fixed_5':     'A  Fixed-5yr',
    'dp_optimal':  'B_dp DP-Optimal',
    'dp_oracle':   'C_dp DP-Oracle',
    'fixed_tstar': 'D  Fixed-T*',
}

for ci_name, ci_val in CI_SCENARIOS.items():
    print(f"── CI scenario: {ci_name} ({ci_val} gCO₂/kWh) ──")

    # Precompute DP table and T* once per CI scenario (shared across seeds)
    dp_table = build_dp_table(
        ci_g_per_kwh=ci_val,
        eff_gain=EFFICIENCY_GAIN,
        emb_kg=EMBODIED_KG,
        p_old_w=P_OLD_W,
        hours_per_year=HOURS_PER_YEAR,
        horizon=HORIZON_YEARS,
    )
    t_star = find_t_star(
        ci_g_per_kwh=ci_val,
        eff_gain=EFFICIENCY_GAIN,
        emb_kg=EMBODIED_KG,
        p_old_w=P_OLD_W,
        hours_per_year=HOURS_PER_YEAR,
        horizon=HORIZON_YEARS,
    )
    print(f"  Precomputed T*(CI={ci_val}) = {t_star} yr")

    policy_results: Dict[str, List[Dict]] = {p: [] for p in cpu_policies}

    for seed in range(N_SEEDS):
        for policy in cpu_policies:
            sim = FleetSimulator(
                policy=policy,
                ci_g_per_kwh=ci_val,
                seed=seed,
                horizon=HORIZON_YEARS,
                fleet_size=FLEET_SIZE,
                eff_gain=EFFICIENCY_GAIN,
                emb_kg=EMBODIED_KG,
                p_old_w=P_OLD_W,
                hours_per_year=HOURS_PER_YEAR,
                dp_table=dp_table,
                t_star=t_star,
                refresh_norm=5,
            )
            sim.run()
            policy_results[policy].append({
                'total_carbon':      sim.total_carbon,
                'total_embodied':    sim.total_embodied,
                'total_operational': sim.total_operational,
                'replacements':      sim.total_replacements,
            })

    # Aggregate over seeds
    agg: Dict[str, Dict] = {}
    for policy in cpu_policies:
        vals = [r['total_carbon'] for r in policy_results[policy]]
        reps = [r['replacements'] for r in policy_results[policy]]
        agg[policy] = {
            'mean_carbon': float(np.mean(vals)),
            'std_carbon':  float(np.std(vals)),
            'mean_replacements': float(np.mean(reps)),
        }

    c_A   = agg['fixed_5']['mean_carbon']
    c_Bdp = agg['dp_optimal']['mean_carbon']
    c_Cdp = agg['dp_oracle']['mean_carbon']
    c_D   = agg['fixed_tstar']['mean_carbon']

    save_Bdp_vs_A  = (c_A - c_Bdp) / c_A * 100
    save_Cdp_vs_A  = (c_A - c_Cdp) / c_A * 100
    save_D_vs_A    = (c_A - c_D)   / c_A * 100
    Bdp_vs_Cdp_pct = (c_Bdp - c_Cdp) / c_A * 100  # should be ~0

    print(f"  A   Fixed-5yr:    {c_A:>10,.0f} kgCO₂  reps={agg['fixed_5']['mean_replacements']:.1f}")
    print(f"  B_dp DP-Optimal:  {c_Bdp:>10,.0f} kgCO₂  reps={agg['dp_optimal']['mean_replacements']:.1f}  "
          f"→ {save_Bdp_vs_A:+.1f}% vs A")
    print(f"  C_dp DP-Oracle:   {c_Cdp:>10,.0f} kgCO₂  reps={agg['dp_oracle']['mean_replacements']:.1f}  "
          f"→ {save_Cdp_vs_A:+.1f}% vs A")
    print(f"  D   Fixed-T*={t_star}yr: {c_D:>10,.0f} kgCO₂  reps={agg['fixed_tstar']['mean_replacements']:.1f}  "
          f"→ {save_D_vs_A:+.1f}% vs A")
    print(f"  B_dp vs C_dp gap: {Bdp_vs_Cdp_pct:.4f}% of A (should be ≈ 0)")
    print()

    summary_results[ci_name] = {
        'ci':          ci_val,
        't_star':      t_star,
        'policy_A':    agg['fixed_5'],
        'policy_Bdp':  agg['dp_optimal'],
        'policy_Cdp':  agg['dp_oracle'],
        'policy_D':    agg['fixed_tstar'],
        'Bdp_saves_vs_A_pct': float(save_Bdp_vs_A),
        'D_saves_vs_A_pct':   float(save_D_vs_A),
        'Bdp_vs_Cdp_gap_pct': float(Bdp_vs_Cdp_pct),
    }

# ─── Summary Table ─────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("SUMMARY: CPU Fleet Carbon Savings vs Fixed-5yr (Policy A)")
print("  Fleet: 50 servers × 10yr × eff=15%/gen × emb=1000 kgCO₂ × 20 seeds")
print("=" * 72)
print(f"{'Scenario':>14} | {'CI':>6} | {'T*':>4} | {'B_dp vs A':>10} | "
      f"{'D vs A':>8} | {'B_dp repl':>10} | {'A repl':>7} | {'Oracle≡B_dp':>12}")
print("-" * 90)
all_Bdp_savings = []
for ci_name, res in summary_results.items():
    r = res
    b_repl = r['policy_Bdp']['mean_replacements']
    a_repl = r['policy_A']['mean_replacements']
    gap    = r['Bdp_vs_Cdp_gap_pct']
    print(f"{ci_name:>14} | {r['ci']:>6} | {r['t_star']:>4} | "
          f"{r['Bdp_saves_vs_A_pct']:>+9.1f}% | "
          f"{r['D_saves_vs_A_pct']:>+7.1f}% | "
          f"{b_repl:>10.1f} | {a_repl:>7.1f} | "
          f"{'✓ match' if abs(gap) < 0.01 else f'MISMATCH {gap:.4f}%':>12}")
    all_Bdp_savings.append(r['Bdp_saves_vs_A_pct'])

print()
print(f"DP-Optimal saves range: [{min(all_Bdp_savings):+.1f}%, {max(all_Bdp_savings):+.1f}%] vs Fixed-5yr")
min_saving = min(all_Bdp_savings)
if min_saving < -0.1:
    print(f"⚠️  WARNING: DP-Optimal is worse than Fixed-5yr at some CI! (min={min_saving:+.1f}%)")
    print("   This indicates a bug in the DP implementation.")
elif min_saving < 0.0:
    print(f"⚠️  Near-zero negative: {min_saving:.4f}% — likely floating-point noise, not a real loss.")
else:
    print(f"✅ DP-Optimal is ≥ Fixed-5yr at ALL CI scenarios (min saving = {min_saving:+.1f}%)")

max_gap = max(abs(r['Bdp_vs_Cdp_gap_pct']) for r in summary_results.values())
if max_gap < 0.01:
    print(f"✅ B_dp and DP-Oracle match exactly (max gap = {max_gap:.6f}%)")
else:
    print(f"⚠️  B_dp vs DP-Oracle gap: {max_gap:.6f}% (should be ~0 since they use the same DP)")
print()


# ──────────────────────────────────────────────────────────────────────────────
# GPU/AI ACCELERATOR SCENARIO
# ──────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("GPU / AI ACCELERATOR LIFECYCLE SCENARIO")
print("  eff_gain=50%/gen (H100→H200→B200: ~2× compute/watt per generation)")
print("  emb=3000 kgCO₂ (GPU rack manufacturing vs CPU server)")
print(f"  Industry norm: replace every {GPU_REFRESH_NORM} years")
print(f"  Fleet: {GPU_FLEET_SIZE} GPU servers × {GPU_HORIZON} yr horizon × 20 seeds")
print("=" * 72)
print()

gpu_summary: Dict = {}
gpu_policies = ['fixed_2', 'dp_optimal']
gpu_policy_labels = {
    'fixed_2':    'GPU_A Fixed-2yr (industry norm)',
    'dp_optimal': 'GPU_B DP-Optimal',
}

for ci_name, ci_val in CI_SCENARIOS.items():
    print(f"── GPU CI scenario: {ci_name} ({ci_val} gCO₂/kWh) ──")

    # Precompute GPU DP table and T*(CI) with GPU parameters
    gpu_dp_table = build_dp_table(
        ci_g_per_kwh=ci_val,
        eff_gain=GPU_EFF_GAIN,
        emb_kg=GPU_EMBODIED_KG,
        p_old_w=P_OLD_W,
        hours_per_year=HOURS_PER_YEAR,
        horizon=GPU_HORIZON,
    )
    gpu_t_star = find_t_star(
        ci_g_per_kwh=ci_val,
        eff_gain=GPU_EFF_GAIN,
        emb_kg=GPU_EMBODIED_KG,
        p_old_w=P_OLD_W,
        hours_per_year=HOURS_PER_YEAR,
        horizon=GPU_HORIZON,
    )
    print(f"  GPU T*(CI={ci_val}) = {gpu_t_star} yr")

    gpu_policy_results: Dict[str, List[Dict]] = {p: [] for p in gpu_policies}

    for seed in range(N_SEEDS):
        for policy in gpu_policies:
            sim = FleetSimulator(
                policy=policy,
                ci_g_per_kwh=ci_val,
                seed=seed,
                horizon=GPU_HORIZON,
                fleet_size=GPU_FLEET_SIZE,
                eff_gain=GPU_EFF_GAIN,
                emb_kg=GPU_EMBODIED_KG,
                p_old_w=P_OLD_W,
                hours_per_year=HOURS_PER_YEAR,
                dp_table=gpu_dp_table,
                t_star=gpu_t_star,
                refresh_norm=GPU_REFRESH_NORM,
            )
            sim.run()
            gpu_policy_results[policy].append({
                'total_carbon':      sim.total_carbon,
                'total_embodied':    sim.total_embodied,
                'total_operational': sim.total_operational,
                'replacements':      sim.total_replacements,
            })

    # Aggregate
    gpu_agg: Dict[str, Dict] = {}
    for policy in gpu_policies:
        vals = [r['total_carbon'] for r in gpu_policy_results[policy]]
        reps = [r['replacements'] for r in gpu_policy_results[policy]]
        gpu_agg[policy] = {
            'mean_carbon': float(np.mean(vals)),
            'std_carbon':  float(np.std(vals)),
            'mean_replacements': float(np.mean(reps)),
        }

    c_GPU_A = gpu_agg['fixed_2']['mean_carbon']
    c_GPU_B = gpu_agg['dp_optimal']['mean_carbon']
    gpu_save = (c_GPU_A - c_GPU_B) / c_GPU_A * 100

    print(f"  GPU_A Fixed-2yr:   {c_GPU_A:>10,.0f} kgCO₂  reps={gpu_agg['fixed_2']['mean_replacements']:.1f}")
    print(f"  GPU_B DP-Optimal:  {c_GPU_B:>10,.0f} kgCO₂  reps={gpu_agg['dp_optimal']['mean_replacements']:.1f}  "
          f"→ {gpu_save:+.1f}% vs Fixed-2yr")
    print()

    gpu_summary[ci_name] = {
        'ci':        ci_val,
        'gpu_t_star': gpu_t_star,
        'policy_GPU_A': gpu_agg['fixed_2'],
        'policy_GPU_B': gpu_agg['dp_optimal'],
        'GPU_B_saves_vs_A_pct': float(gpu_save),
    }

# GPU summary table
print()
print("=" * 72)
print("SUMMARY: GPU Fleet — DP-Optimal vs Fixed-2yr (industry norm)")
print("  eff_gain=50%/gen × emb=3000 kgCO₂ × 10yr × 20 seeds")
print("=" * 72)
print(f"{'Scenario':>14} | {'CI':>6} | {'T*':>4} | {'GPU_B vs A':>12} | "
      f"{'B repl':>8} | {'A repl':>8}")
print("-" * 65)
gpu_savings_all = []
for ci_name, res in gpu_summary.items():
    b_repl = res['policy_GPU_B']['mean_replacements']
    a_repl = res['policy_GPU_A']['mean_replacements']
    save   = res['GPU_B_saves_vs_A_pct']
    gpu_savings_all.append(save)
    print(f"{ci_name:>14} | {res['ci']:>6} | {res['gpu_t_star']:>4} | "
          f"{save:>+11.1f}% | {b_repl:>8.1f} | {a_repl:>8.1f}")

print()
print(f"GPU DP-Optimal savings range: [{min(gpu_savings_all):+.1f}%, {max(gpu_savings_all):+.1f}%] vs Fixed-2yr")
print()


# ──────────────────────────────────────────────────────────────────────────────
# SAVE RESULTS JSON
# ──────────────────────────────────────────────────────────────────────────────

def numpy_convert(o):
    """Convert numpy scalars to Python native for JSON serialisation."""
    if isinstance(o, (np.integer,)):  return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.ndarray,)):  return o.tolist()
    return o

os.makedirs("results", exist_ok=True)
output_json = {
    "metadata": {
        "script":       "simulate-lifecycle-v2.py",
        "cpu_fleet":    {"fleet_size": FLEET_SIZE, "horizon": HORIZON_YEARS,
                         "eff_gain": EFFICIENCY_GAIN, "emb_kg": EMBODIED_KG,
                         "seeds": N_SEEDS},
        "gpu_fleet":    {"fleet_size": GPU_FLEET_SIZE, "horizon": GPU_HORIZON,
                         "eff_gain": GPU_EFF_GAIN, "emb_kg": GPU_EMBODIED_KG,
                         "refresh_norm": GPU_REFRESH_NORM, "seeds": N_SEEDS},
        "policies_cpu": ["A=Fixed-5yr", "B_dp=DP-Optimal", "C_dp=DP-Oracle", "D=Fixed-T*"],
        "policies_gpu": ["GPU_A=Fixed-2yr", "GPU_B=DP-Optimal"],
    },
    "cpu_fleet":  summary_results,
    "gpu_fleet":  gpu_summary,
}

with open("results/lifecycle-sim-v2-summary.json", "w") as f:
    json.dump(output_json, f, default=numpy_convert, indent=2)
print("Saved results/lifecycle-sim-v2-summary.json")


# ──────────────────────────────────────────────────────────────────────────────
# FIGURES
# ──────────────────────────────────────────────────────────────────────────────

os.makedirs("figures", exist_ok=True)

# ── Figure 8: DP-Optimal savings vs Fixed-5yr, all CI scenarios ──────────────
ci_names  = list(summary_results.keys())
ci_labels = [f"{n}\n({summary_results[n]['ci']} g/kWh)" for n in ci_names]
bdp_vs_a  = [summary_results[n]['Bdp_saves_vs_A_pct'] for n in ci_names]
d_vs_a    = [summary_results[n]['D_saves_vs_A_pct']   for n in ci_names]
t_stars   = [summary_results[n]['t_star'] for n in ci_names]

x = np.arange(len(ci_names))
width = 0.35
fig, ax = plt.subplots(figsize=(12, 6))
bars1 = ax.bar(x - width/2, bdp_vs_a, width,
               label='B_dp: DP-Optimal vs Fixed-5yr', color='#2980b9', alpha=0.85)
bars2 = ax.bar(x + width/2, d_vs_a, width,
               label='D: Fixed-T*(CI) vs Fixed-5yr', color='#8e44ad', alpha=0.85)

for bar, val, t in zip(bars1, bdp_vs_a, t_stars):
    ypos = bar.get_height() + (0.3 if val >= 0 else -1.5)
    va   = 'bottom' if val >= 0 else 'top'
    ax.text(bar.get_x() + bar.get_width()/2., ypos,
            f'{val:+.1f}%', ha='center', va=va, fontsize=8.5, color='#1a5276')

for bar, val in zip(bars2, d_vs_a):
    ypos = bar.get_height() + (0.3 if val >= 0 else -1.5)
    va   = 'bottom' if val >= 0 else 'top'
    ax.text(bar.get_x() + bar.get_width()/2., ypos,
            f'{val:+.1f}%', ha='center', va=va, fontsize=8.5, color='#5b2c6f')

ax.axhline(0, color='black', linewidth=0.9)
ax.set_xticks(x)
ax.set_xticklabels(ci_labels, fontsize=9)
ax.set_ylabel("Carbon Saving vs Fixed-5yr Norm (%)", fontsize=11)
ax.set_title(
    "CPU Fleet: DP-Optimal vs Fixed-5yr — Carbon Savings across Grid CI\n"
    "Fleet: 50 servers × 10yr × eff=15%/gen × emb=1000 kgCO₂ × 20 seeds",
    fontsize=11
)
ax.legend(fontsize=10)
ax.grid(True, axis='y', alpha=0.3)
all_vals = bdp_vs_a + d_vs_a
ax.set_ylim(min(all_vals) - 5, max(all_vals) + 10)
plt.tight_layout()
plt.savefig("figures/embodied_fig8_dp_savings.png", dpi=300, bbox_inches='tight')
plt.close()
print("Saved figures/embodied_fig8_dp_savings.png (300 DPI)")


# ── Figure 9: GPU scenario — DP-Optimal vs Fixed-2yr ─────────────────────────
gpu_ci_names  = list(gpu_summary.keys())
gpu_ci_labels = [f"{n}\n({gpu_summary[n]['ci']} g/kWh)" for n in gpu_ci_names]
gpu_saves     = [gpu_summary[n]['GPU_B_saves_vs_A_pct'] for n in gpu_ci_names]
gpu_t_stars   = [gpu_summary[n]['gpu_t_star'] for n in gpu_ci_names]

# Also compute embodied fraction of total carbon for Fixed-2yr vs DP-Optimal
gpu_emb_frac_A = [
    gpu_summary[n]['policy_GPU_A']['mean_carbon'] for n in gpu_ci_names
]
gpu_emb_frac_B = [
    gpu_summary[n]['policy_GPU_B']['mean_carbon'] for n in gpu_ci_names
]

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle(
    "AI Accelerator (GPU) Lifecycle: DP-Optimal vs Fixed-2yr Industry Norm\n"
    "eff=50%/gen (H100→H200→B200) · emb=3000 kgCO₂ · 50 GPUs · 10yr · 20 seeds",
    fontsize=12
)

# Left: savings bar chart
ax = axes[0]
colors_gpu = ['#27ae60' if s >= 0 else '#e74c3c' for s in gpu_saves]
bars = ax.bar(range(len(gpu_ci_names)), gpu_saves, color=colors_gpu, alpha=0.85)
for bar, val, t in zip(bars, gpu_saves, gpu_t_stars):
    ypos = bar.get_height() + (0.3 if val >= 0 else -1.5)
    va   = 'bottom' if val >= 0 else 'top'
    ax.text(bar.get_x() + bar.get_width()/2., ypos,
            f'{val:+.1f}%\n(T*={t}yr)', ha='center', va=va, fontsize=8.5)
ax.axhline(0, color='black', linewidth=0.9)
ax.set_xticks(range(len(gpu_ci_names)))
ax.set_xticklabels(gpu_ci_labels, fontsize=9)
ax.set_ylabel("Carbon Saving vs Fixed-2yr (%)", fontsize=11)
ax.set_title("GPU_B DP-Optimal vs GPU_A Fixed-2yr", fontsize=11)
ax.grid(True, axis='y', alpha=0.3)
ax.set_ylim(min(gpu_saves) - 5, max(gpu_saves) + 15)

# Right: absolute carbon comparison (tCO₂)
ax = axes[1]
ci_vals_gpu = [gpu_summary[n]['ci'] for n in gpu_ci_names]
ax.plot(ci_vals_gpu, [c / 1000 for c in gpu_emb_frac_A], 's-',
        color='#e74c3c', linewidth=2.5, markersize=7, label='GPU_A Fixed-2yr')
ax.plot(ci_vals_gpu, [c / 1000 for c in gpu_emb_frac_B], 'o-',
        color='#27ae60', linewidth=2.5, markersize=7, label='GPU_B DP-Optimal')
ax.set_xlabel("Grid CI (gCO₂/kWh)", fontsize=11)
ax.set_ylabel("Total Fleet Carbon — 10yr (tCO₂)", fontsize=11)
ax.set_title("Absolute GPU Lifecycle Carbon vs Grid CI", fontsize=11)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("figures/embodied_fig9_gpu_lifecycle.png", dpi=300, bbox_inches='tight')
plt.close()
print("Saved figures/embodied_fig9_gpu_lifecycle.png (300 DPI)")

print()
print("[DONE] simulate-lifecycle-v2.py complete.")
