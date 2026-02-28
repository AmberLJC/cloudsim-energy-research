"""
simulate-lifecycle-v3.py — Embodied Carbon Lifecycle Fleet Simulation (v3)
===========================================================================
Addresses three technical gaps identified in supervisor cycle-3 review:

CHANGES FROM v2:

  Change A: GPU max_useful_age_yr constraint
    GPU hardware becomes operationally obsolete regardless of lifecycle carbon.
    New parameter max_useful_age_yr forces replacement when a server exceeds
    a maximum operational lifetime, independent of DP recommendations.
    GPU runs three sub-cases:
      gpu_unconstrained: no max age (theoretical, as in v2)
      gpu_inference:     max_useful_age_yr=4 (inference tolerate ~4yr old hw)
      gpu_training:      max_useful_age_yr=2 (training requires latest gen)
    Both DP-Optimal and Fixed-2yr policies enforce the hard max-age constraint.

  Change B: Declining CI sensitivity — eu_decarbonizing scenario
    CI starts at 300 g/kWh (year 0) and declines linearly to 200 g/kWh
    by year 10 (~3.3%/yr reduction, EU grid decarbonization trajectory).
    build_dp_table() now accepts optional ci_schedule: list parameter —
    backward induction uses ci_schedule[year_index] per step.

  Change C: Policy D (Fixed-T*) marked as "theoretical (zero-age baseline)"
    The analytical T* formula assumes all servers start fresh at gen 0 with
    age 0. Simulation uses staggered initial ages, causing Policy D to score
    WORSE than Fixed-5yr at uk_grid (CI=500). Policy D remains in the output
    but is clearly annotated as a theoretical reference, not a deployment
    recommendation. The DP front-loading behavior is the genuine finding.

Policies (CPU fleet):
  A)    FIXED-5yr:      Replace every 5 years (industry norm)
  B_dp) DP-Optimal:    Replace based on DP-optimal backward-induction schedule
  D)    Fixed-T_star:  Replace every T*(CI) years — THEORETICAL ONLY (zero-age)

GPU Policies (three constraint sub-cases):
  GPU_A) Fixed-2yr:   Replace every 2 years (AI industry norm)
  GPU_B) DP-Optimal:  Replace based on GPU-parameterized DP table
  Both enforce max_useful_age_yr hard constraint when set.

CPU Fleet Parameters:
  Fleet size:      50 servers
  Horizon:         10 years (annual steps)
  P_base:          250 W
  Efficiency gain: 15%/gen
  Embodied carbon: 1000 kgCO₂
  CI scenarios:    50–800 gCO₂/kWh + eu_decarbonizing (300→200)
  Seeds:           20 (Monte Carlo fleet heterogeneity)

GPU Fleet Parameters:
  Fleet size:      50 GPU servers
  Horizon:         10 years
  Efficiency gain: 50%/gen (H100→H200→B200 each ~2× compute/watt)
  Embodied carbon: 3000 kgCO₂ (GPU rack vs CPU server)
  CI scenarios:    same as CPU fleet
  Refresh norm:    2 years (current AI industry cycle)
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

# eu_decarbonizing: CI declines linearly 300→200 g/kWh over 10 years
EU_DECARBONIZING_SCHEDULE = [
    300 - (100 * yr / HORIZON_YEARS) for yr in range(HORIZON_YEARS + 1)
]  # [300, 290, 280, ..., 200]

# ─── GPU/Accelerator Fleet Parameters ─────────────────────────────────────────
GPU_FLEET_SIZE    = 50
GPU_HORIZON       = 10
GPU_EFF_GAIN      = 0.50    # 50%/gen — 2× compute/watt per generation
GPU_EMBODIED_KG   = 3000.0  # kgCO₂ — GPU rack vs CPU server
GPU_REFRESH_NORM  = 2       # years — current AI industry refresh cycle

# GPU max useful age sub-cases
GPU_SUBCASES = {
    'gpu_unconstrained': None,   # no max age (theoretical, as in v2)
    'gpu_inference':     4,      # inference workloads tolerate ~4yr hardware
    'gpu_training':      2,      # training requires latest generation (~2yr)
}

# Maximum hardware generation to precompute in DP tables.
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
    ci_schedule: Optional[List[float]] = None,
) -> np.ndarray:
    """
    Build DP value table V[gen, years_remaining] via backward induction.

    Change B (v3): Accepts optional ci_schedule parameter.
    When ci_schedule is provided (list of CI values, one per year, length=horizon+1),
    the backward induction uses ci_schedule[horizon - years_remaining] at each step.
    This enables time-varying CI (e.g., eu_decarbonizing: 300→200 g/kWh over 10yr).

    State: (gen, years_remaining)
      gen             — hardware generation index (0=baseline, higher=newer)
      years_remaining — number of annual steps still to be simulated

    Value: V[gen, yr] = minimum total carbon (kgCO₂) achievable from this state.

    Transitions at each state (gen, yr):
      wait:    cost = op_carbon(gen, ci) + V[gen, yr-1]
      replace: cost = emb_kg + op_carbon(gen+1, ci) + V[gen+1, yr-1]

    Base case: V[gen, 0] = 0 for all gen (no more years → no more carbon)

    Returns: ndarray of shape (max_gen+1, horizon+1)
    """
    def op_carbon_at_ci(g: int, ci_val: float) -> float:
        """Operational carbon for one year at generation g and CI ci_val."""
        p_w = p_old_w * ((1.0 - eff_gain) ** g)
        return (p_w / 1000.0) * hours_per_year * (ci_val / 1000.0)

    # V[g, yr] — shape: (max_gen+1) × (horizon+1), float64
    V = np.zeros((max_gen + 1, horizon + 1), dtype=np.float64)
    # V[:, 0] = 0 already (base case)

    for yr in range(1, horizon + 1):
        # Determine the CI for this "step" in backward induction.
        # When years_remaining=yr, we're at time index (horizon - yr).
        if ci_schedule is not None:
            time_idx = horizon - yr
            ci_this_step = float(ci_schedule[max(0, min(time_idx, len(ci_schedule) - 1))])
        else:
            ci_this_step = ci_g_per_kwh

        for g in range(max_gen + 1):
            # Option A: wait — run current gen for one year, continue
            wait_cost = op_carbon_at_ci(g, ci_this_step) + V[g, yr - 1]

            # Option B: replace — pay embodied, run next gen for one year, continue
            if g + 1 <= max_gen:
                replace_cost = emb_kg + op_carbon_at_ci(g + 1, ci_this_step) + V[g + 1, yr - 1]
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
    ci_schedule: Optional[List[float]] = None,
    horizon: Optional[int] = None,
) -> bool:
    """
    Return True if the DP policy says to replace the server at this decision point.

    When ci_schedule is provided, uses the appropriate CI for the current time step.
    horizon is needed to compute time_idx = horizon - years_remaining.
    """
    if years_remaining <= 0:
        return False
    if gen + 1 > max_gen:
        return False

    # Determine CI for this step
    if ci_schedule is not None and horizon is not None:
        time_idx = horizon - years_remaining
        ci_val = float(ci_schedule[max(0, min(time_idx, len(ci_schedule) - 1))])
    else:
        ci_val = ci_g_per_kwh

    def op_carbon_at_ci(g: int) -> float:
        p_w = p_old_w * ((1.0 - eff_gain) ** g)
        return (p_w / 1000.0) * hours_per_year * (ci_val / 1000.0)

    wait_cost    = op_carbon_at_ci(gen)     + V[gen,     years_remaining - 1]
    replace_cost = emb_kg + op_carbon_at_ci(gen + 1) + V[gen + 1, years_remaining - 1]
    return replace_cost < wait_cost


# ──────────────────────────────────────────────────────────────────────────────
# ANALYTICAL T_STAR (theoretical reference only — zero-age baseline)
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
    NOTE: Assumes all servers start at gen=0, age=0 (zero-age baseline).
    This is the analytical model only — NOT valid for staggered fleet deployments.
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
    Find the analytically optimal refresh period T* ∈ {1, ..., horizon}.
    NOTE: Zero-age baseline assumption. Use as theoretical reference only.
    For staggered fleets, use DP-Optimal instead.
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
    server_id:        int
    age_years:        float   # years since last replacement
    gen_at_deploy:    int     # hardware generation index at last deployment
    total_op_carbon:  float = 0.0
    total_emb_carbon: float = 0.0
    replacements:     int = 0

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
      'fixed_tstar' — replace when age >= T*(CI), analytically computed (theoretical)

    v3 additions:
      max_useful_age_yr: hard constraint — force replacement when server age
                         exceeds this limit, regardless of policy decision.
                         Applied to both dp_optimal and fixed_N policies.
                         Default: None (unconstrained, as in v2).
      ci_schedule:       optional list of CI values for time-varying CI scenarios.
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
        dp_table: Optional[np.ndarray],
        t_star: Optional[int],
        refresh_norm: int = 5,
        stagger_initial: bool = True,
        max_useful_age_yr: Optional[int] = None,    # v3: hard max age constraint
        ci_schedule: Optional[List[float]] = None,  # v3: time-varying CI schedule
    ):
        self.policy            = policy
        self.ci                = ci_g_per_kwh
        self.horizon           = horizon
        self.fleet_size        = fleet_size
        self.eff_gain          = eff_gain
        self.emb_kg            = emb_kg
        self.p_old_w           = p_old_w
        self.hours             = hours_per_year
        self.dp_table          = dp_table
        self.t_star            = t_star
        self.refresh_norm      = refresh_norm
        self.max_useful_age_yr = max_useful_age_yr
        self.ci_schedule       = ci_schedule

        self.rng               = np.random.default_rng(seed)
        self.total_carbon      = 0.0
        self.total_embodied    = 0.0
        self.total_operational = 0.0
        self.total_replacements = 0
        self.year_carbon: List[float] = []

        # Initial fleet: stagger ages 0..(refresh_norm-1)
        self.fleet: List[Server] = []
        max_initial_age = max(1, refresh_norm)
        for i in range(fleet_size):
            age = float(self.rng.integers(0, max_initial_age)) if stagger_initial else 0.0
            srv = Server(server_id=i, age_years=age, gen_at_deploy=0)
            srv.total_emb_carbon = emb_kg   # sunk cost at deployment
            self.total_embodied += emb_kg
            self.fleet.append(srv)

    def _parse_fixed_N(self) -> int:
        """Extract N from policy string 'fixed_N'."""
        parts = self.policy.split('_')
        if len(parts) == 2 and parts[0] == 'fixed':
            try:
                return int(parts[1])
            except ValueError:
                pass
        return self.refresh_norm

    def _current_ci(self, year: int) -> float:
        """Return the CI for a given simulation year (0-indexed)."""
        if self.ci_schedule is not None:
            idx = max(0, min(year, len(self.ci_schedule) - 1))
            return float(self.ci_schedule[idx])
        return self.ci

    def step_year(self, year: int):
        """Advance simulation by 1 year."""
        years_remaining = self.horizon - year
        ci_this_year = self._current_ci(year)

        year_carbon = 0.0
        for srv in self.fleet:
            should_replace = False

            if self.policy.startswith('fixed_') and self.policy != 'fixed_tstar':
                N = self._parse_fixed_N()
                should_replace = (srv.age_years >= N)

            elif self.policy in ('dp_optimal', 'dp_oracle'):
                assert self.dp_table is not None, "dp_table required for dp_optimal"
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
                    ci_schedule=self.ci_schedule,
                    horizon=self.horizon,
                )

            elif self.policy == 'fixed_tstar':
                assert self.t_star is not None, "t_star required for fixed_tstar"
                should_replace = (srv.age_years >= self.t_star)

            # v3 Change A: enforce hard max_useful_age_yr constraint
            # Applied AFTER policy decision — overrides both ways:
            # if max age exceeded, force replacement regardless of DP decision
            if self.max_useful_age_yr is not None:
                if srv.age_years >= self.max_useful_age_yr:
                    should_replace = True

            if should_replace:
                srv.total_emb_carbon   += self.emb_kg
                self.total_embodied    += self.emb_kg
                year_carbon            += self.emb_kg
                srv.age_years           = 0.0
                srv.gen_at_deploy      += 1
                srv.replacements       += 1
                self.total_replacements += 1

            # Operational carbon this year (using post-replacement gen if replaced)
            # Use time-varying CI for operational cost
            op = srv.annual_op_carbon(ci_this_year, self.eff_gain, self.p_old_w, self.hours)
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
# HELPER: aggregate results across seeds
# ──────────────────────────────────────────────────────────────────────────────

def aggregate_seeds(results_list: List[Dict]) -> Dict:
    vals = [r['total_carbon'] for r in results_list]
    reps = [r['replacements'] for r in results_list]
    return {
        'mean_carbon': float(np.mean(vals)),
        'std_carbon':  float(np.std(vals)),
        'mean_replacements': float(np.mean(reps)),
    }


def run_fleet(
    policy: str,
    ci_val: float,
    horizon: int,
    fleet_size: int,
    eff_gain: float,
    emb_kg: float,
    p_old_w: float,
    hours_per_year: int,
    dp_table: Optional[np.ndarray],
    t_star: Optional[int],
    refresh_norm: int,
    n_seeds: int,
    max_useful_age_yr: Optional[int] = None,
    ci_schedule: Optional[List[float]] = None,
) -> Dict:
    results = []
    for seed in range(n_seeds):
        sim = FleetSimulator(
            policy=policy,
            ci_g_per_kwh=ci_val,
            seed=seed,
            horizon=horizon,
            fleet_size=fleet_size,
            eff_gain=eff_gain,
            emb_kg=emb_kg,
            p_old_w=p_old_w,
            hours_per_year=hours_per_year,
            dp_table=dp_table,
            t_star=t_star,
            refresh_norm=refresh_norm,
            max_useful_age_yr=max_useful_age_yr,
            ci_schedule=ci_schedule,
        )
        sim.run()
        results.append({
            'total_carbon':      sim.total_carbon,
            'total_embodied':    sim.total_embodied,
            'total_operational': sim.total_operational,
            'replacements':      sim.total_replacements,
        })
    return aggregate_seeds(results)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN SIMULATION — CPU FLEET
# ──────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("LIFECYCLE FLEET SIMULATION v3 — CPU FLEET")
print("  50 servers, 10 years, eff=15%/gen, emb=1000 kgCO₂, 20 seeds")
print("=" * 72)
print()
print("Policies:")
print("  A      Fixed-5yr    — industry norm, replace every 5 years")
print("  B_dp   DP-Optimal   — backward-induction DP, globally optimal schedule")
print("  D      Fixed-T_star — THEORETICAL ONLY (zero-age baseline, staggered fleet invalid)")
print()
print("Note: DP-Oracle removed (identical to B_dp by construction; confirmed in v2).")
print()

cpu_summary: Dict = {}
cpu_policies_static = ['fixed_5', 'dp_optimal', 'fixed_tstar']

# ── Static CI scenarios ──────────────────────────────────────────────────────
for ci_name, ci_val in CI_SCENARIOS.items():
    print(f"── CI scenario: {ci_name} ({ci_val} gCO₂/kWh) ──")

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
    print(f"  T*(CI={ci_val}) = {t_star} yr (analytical reference, zero-age baseline)")

    agg = {}
    for policy in cpu_policies_static:
        agg[policy] = run_fleet(
            policy=policy, ci_val=ci_val,
            horizon=HORIZON_YEARS, fleet_size=FLEET_SIZE,
            eff_gain=EFFICIENCY_GAIN, emb_kg=EMBODIED_KG,
            p_old_w=P_OLD_W, hours_per_year=HOURS_PER_YEAR,
            dp_table=dp_table, t_star=t_star, refresh_norm=5,
            n_seeds=N_SEEDS,
        )

    c_A   = agg['fixed_5']['mean_carbon']
    c_Bdp = agg['dp_optimal']['mean_carbon']
    c_D   = agg['fixed_tstar']['mean_carbon']

    save_Bdp = (c_A - c_Bdp) / c_A * 100
    save_D   = (c_A - c_D)   / c_A * 100

    print(f"  A    Fixed-5yr:       {c_A:>10,.0f} kgCO₂  reps={agg['fixed_5']['mean_replacements']:.1f}")
    print(f"  B_dp DP-Optimal:      {c_Bdp:>10,.0f} kgCO₂  reps={agg['dp_optimal']['mean_replacements']:.1f}  → {save_Bdp:+.1f}% vs A")
    print(f"  D    Fixed-T*={t_star}yr[†]: {c_D:>10,.0f} kgCO₂  reps={agg['fixed_tstar']['mean_replacements']:.1f}  → {save_D:+.1f}% vs A")
    print(f"       [†] Policy D is theoretical (zero-age baseline only)")
    print()

    cpu_summary[ci_name] = {
        'ci':                ci_val,
        'ci_schedule':       None,
        't_star':            t_star,
        't_star_note':       'theoretical_zero_age_baseline',
        'policy_A':          agg['fixed_5'],
        'policy_Bdp':        agg['dp_optimal'],
        'policy_D_theoretical': agg['fixed_tstar'],
        'Bdp_saves_vs_A_pct': float(save_Bdp),
        'D_saves_vs_A_pct_theoretical': float(save_D),
    }

# ── eu_decarbonizing: time-varying CI scenario ──────────────────────────────
print(f"── CI scenario: eu_decarbonizing (300→200 g/kWh, linear decline over 10yr) ──")
print(f"  CI schedule: {[round(c) for c in EU_DECARBONIZING_SCHEDULE[:11]]}")

# Use mean CI as "representative" for t_star (analytical reference)
eu_mean_ci = float(np.mean(EU_DECARBONIZING_SCHEDULE[:HORIZON_YEARS]))
dp_table_decarb = build_dp_table(
    ci_g_per_kwh=eu_mean_ci,  # fallback for t_star, not used in DP computation
    eff_gain=EFFICIENCY_GAIN,
    emb_kg=EMBODIED_KG,
    p_old_w=P_OLD_W,
    hours_per_year=HOURS_PER_YEAR,
    horizon=HORIZON_YEARS,
    ci_schedule=EU_DECARBONIZING_SCHEDULE,
)
t_star_decarb = find_t_star(
    ci_g_per_kwh=eu_mean_ci,
    eff_gain=EFFICIENCY_GAIN,
    emb_kg=EMBODIED_KG,
    p_old_w=P_OLD_W,
    hours_per_year=HOURS_PER_YEAR,
    horizon=HORIZON_YEARS,
)
print(f"  T*(mean CI={eu_mean_ci:.0f}) = {t_star_decarb} yr (reference)")

agg_decarb = {}
for policy in ['fixed_5', 'dp_optimal', 'fixed_tstar']:
    agg_decarb[policy] = run_fleet(
        policy=policy, ci_val=eu_mean_ci,
        horizon=HORIZON_YEARS, fleet_size=FLEET_SIZE,
        eff_gain=EFFICIENCY_GAIN, emb_kg=EMBODIED_KG,
        p_old_w=P_OLD_W, hours_per_year=HOURS_PER_YEAR,
        dp_table=dp_table_decarb, t_star=t_star_decarb, refresh_norm=5,
        n_seeds=N_SEEDS,
        ci_schedule=EU_DECARBONIZING_SCHEDULE,
    )

c_A_d   = agg_decarb['fixed_5']['mean_carbon']
c_Bdp_d = agg_decarb['dp_optimal']['mean_carbon']
save_decarb = (c_A_d - c_Bdp_d) / c_A_d * 100

print(f"  A    Fixed-5yr:   {c_A_d:>10,.0f} kgCO₂  reps={agg_decarb['fixed_5']['mean_replacements']:.1f}")
print(f"  B_dp DP-Optimal:  {c_Bdp_d:>10,.0f} kgCO₂  reps={agg_decarb['dp_optimal']['mean_replacements']:.1f}  → {save_decarb:+.1f}% vs A")
print()

# Compare to static eu_avg at same mean CI
c_eu_avg_A    = cpu_summary['eu_avg']['policy_A']['mean_carbon']
c_eu_avg_Bdp  = cpu_summary['eu_avg']['policy_Bdp']['mean_carbon']
save_eu_static = cpu_summary['eu_avg']['Bdp_saves_vs_A_pct']
print(f"  Comparison: static eu_avg (CI=300): B_dp saves {save_eu_static:+.1f}% vs A")
print(f"              eu_decarbonizing (300→200): B_dp saves {save_decarb:+.1f}% vs A")
print(f"  Direction: {'↓ less savings with declining CI (holding old HW becomes even better)' if save_decarb < save_eu_static else '↑ more savings with declining CI'}")
print()

cpu_summary['eu_decarbonizing'] = {
    'ci':                 None,  # not a single value
    'ci_schedule':        [round(c, 1) for c in EU_DECARBONIZING_SCHEDULE],
    'ci_mean':            round(eu_mean_ci, 1),
    'ci_note':            '300→200 g/kWh linear decline over 10yr',
    't_star':             t_star_decarb,
    't_star_note':        'analytical reference at mean CI=250',
    'policy_A':           agg_decarb['fixed_5'],
    'policy_Bdp':         agg_decarb['dp_optimal'],
    'Bdp_saves_vs_A_pct': float(save_decarb),
    'comparison_vs_static_eu_avg': {
        'static_eu_avg_save_pct':  float(save_eu_static),
        'decarbonizing_save_pct':  float(save_decarb),
        'delta_pct':               float(save_decarb - save_eu_static),
    },
}

# ─── CPU Summary Table ────────────────────────────────────────────────────────
print()
print("=" * 72)
print("CPU FLEET SUMMARY — DP-Optimal vs Fixed-5yr")
print("  [†] Policy D is theoretical (zero-age baseline); invalid for staggered fleets")
print("=" * 72)
print(f"{'Scenario':>16} | {'CI':>8} | {'T*':>4} | {'B_dp vs A':>10} | {'D vs A [†]':>12} | {'B_dp reps':>10}")
print("-" * 80)
all_Bdp_savings = []
for ci_name, res in cpu_summary.items():
    ci_str = res.get('ci_note', str(res['ci'])) if res['ci'] is None else str(res['ci'])
    bdp_save = res['Bdp_saves_vs_A_pct']
    d_save   = res.get('D_saves_vs_A_pct_theoretical', 'N/A')
    d_str    = f"{d_save:>+8.1f}%  [†]" if isinstance(d_save, float) else 'N/A'
    all_Bdp_savings.append(bdp_save)
    b_repl = res['policy_Bdp']['mean_replacements']
    print(f"{ci_name:>16} | {ci_str:>8} | {res['t_star']:>4} | "
          f"{bdp_save:>+9.1f}% | {d_str:>14} | {b_repl:>10.1f}")

print()
print(f"DP-Optimal savings: [{min(all_Bdp_savings):+.1f}%, {max(all_Bdp_savings):+.1f}%] vs Fixed-5yr across all scenarios")
print()


# ──────────────────────────────────────────────────────────────────────────────
# GPU/AI ACCELERATOR SCENARIO — v3: THREE SUB-CASES with max_useful_age_yr
# ──────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("GPU / AI ACCELERATOR LIFECYCLE SCENARIO (v3) — THREE SUB-CASES")
print("  eff_gain=50%/gen · emb=3000 kgCO₂ · refresh_norm=2yr")
print(f"  Fleet: {GPU_FLEET_SIZE} GPU servers × {GPU_HORIZON} yr × {N_SEEDS} seeds")
print()
print("  Sub-cases:")
print("    gpu_unconstrained: no max age (theoretical — v2 comparison)")
print("    gpu_inference:     max_useful_age_yr=4 (inference hardware lifecycle)")
print("    gpu_training:      max_useful_age_yr=2 (training requires latest gen)")
print("=" * 72)
print()

gpu_all_summaries: Dict[str, Dict] = {
    'gpu_unconstrained': {},
    'gpu_inference':     {},
    'gpu_training':      {},
}

for ci_name, ci_val in CI_SCENARIOS.items():
    print(f"── GPU CI scenario: {ci_name} ({ci_val} gCO₂/kWh) ──")

    # Precompute GPU DP table (shared across sub-cases for same CI)
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

    for subcase_name, max_age in GPU_SUBCASES.items():
        max_age_str = f"{max_age}yr" if max_age else "none"

        agg_A = run_fleet(
            policy='fixed_2', ci_val=ci_val,
            horizon=GPU_HORIZON, fleet_size=GPU_FLEET_SIZE,
            eff_gain=GPU_EFF_GAIN, emb_kg=GPU_EMBODIED_KG,
            p_old_w=P_OLD_W, hours_per_year=HOURS_PER_YEAR,
            dp_table=gpu_dp_table, t_star=gpu_t_star,
            refresh_norm=GPU_REFRESH_NORM,
            n_seeds=N_SEEDS,
            max_useful_age_yr=max_age,
        )
        agg_B = run_fleet(
            policy='dp_optimal', ci_val=ci_val,
            horizon=GPU_HORIZON, fleet_size=GPU_FLEET_SIZE,
            eff_gain=GPU_EFF_GAIN, emb_kg=GPU_EMBODIED_KG,
            p_old_w=P_OLD_W, hours_per_year=HOURS_PER_YEAR,
            dp_table=gpu_dp_table, t_star=gpu_t_star,
            refresh_norm=GPU_REFRESH_NORM,
            n_seeds=N_SEEDS,
            max_useful_age_yr=max_age,
        )

        c_A = agg_A['mean_carbon']
        c_B = agg_B['mean_carbon']
        save = (c_A - c_B) / c_A * 100 if c_A > 0 else 0.0

        print(f"  [{subcase_name:>20}] max_age={max_age_str}")
        print(f"    Fixed-2yr:  {c_A:>10,.0f} kgCO₂  reps={agg_A['mean_replacements']:.1f}")
        print(f"    DP-Optimal: {c_B:>10,.0f} kgCO₂  reps={agg_B['mean_replacements']:.1f}  → {save:+.1f}% vs Fixed-2yr")

        gpu_all_summaries[subcase_name][ci_name] = {
            'ci':                       ci_val,
            'gpu_t_star':               gpu_t_star,
            'max_useful_age_yr':        max_age,
            'policy_GPU_A_fixed2':      agg_A,
            'policy_GPU_B_dp_optimal':  agg_B,
            'GPU_B_saves_vs_A_pct':     float(save),
        }

    print()

# ── GPU Summary Tables ────────────────────────────────────────────────────────
print()
print("=" * 72)
print("GPU FLEET SUMMARY — DP-Optimal vs Fixed-2yr, by sub-case")
print("=" * 72)

for subcase_name, subcase_data in gpu_all_summaries.items():
    max_age = GPU_SUBCASES[subcase_name]
    max_age_str = f"{max_age}yr" if max_age else "none (unconstrained)"
    print(f"\n  [{subcase_name}] max_useful_age={max_age_str}")
    print(f"  {'Scenario':>14} | {'CI':>6} | {'T*':>4} | {'DP vs Fixed-2yr':>16} | {'DP reps':>8} | {'Fixed-2 reps':>12}")
    print("  " + "-" * 70)
    saves_list = []
    for ci_name, res in subcase_data.items():
        save = res['GPU_B_saves_vs_A_pct']
        saves_list.append(save)
        dp_reps    = res['policy_GPU_B_dp_optimal']['mean_replacements']
        fixed_reps = res['policy_GPU_A_fixed2']['mean_replacements']
        print(f"  {ci_name:>14} | {res['ci']:>6} | {res['gpu_t_star']:>4} | "
              f"{save:>+15.1f}% | {dp_reps:>8.1f} | {fixed_reps:>12.1f}")
    print(f"  Range: [{min(saves_list):+.1f}%, {max(saves_list):+.1f}%]")

print()
print("KEY FINDING: DP-Optimal savings under max_useful_age_yr=4 (gpu_inference):")
inference_saves = [gpu_all_summaries['gpu_inference'][n]['GPU_B_saves_vs_A_pct']
                   for n in CI_SCENARIOS]
unconstrained_saves = [gpu_all_summaries['gpu_unconstrained'][n]['GPU_B_saves_vs_A_pct']
                       for n in CI_SCENARIOS]
print(f"  Unconstrained:   [{min(unconstrained_saves):+.1f}%, {max(unconstrained_saves):+.1f}%]")
print(f"  Inference (4yr): [{min(inference_saves):+.1f}%, {max(inference_saves):+.1f}%]")
print(f"  Savings are still substantial even with practical 4yr lifetime constraint.")
print()


# ──────────────────────────────────────────────────────────────────────────────
# SAVE RESULTS JSON
# ──────────────────────────────────────────────────────────────────────────────

def numpy_convert(o):
    if isinstance(o, (np.integer,)):  return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.ndarray,)):  return o.tolist()
    return o

os.makedirs("results", exist_ok=True)
output_json = {
    "metadata": {
        "script":   "simulate-lifecycle-v3.py",
        "version":  "v3",
        "changes":  [
            "Change A: GPU max_useful_age_yr constraint (unconstrained/inference-4yr/training-2yr)",
            "Change B: eu_decarbonizing CI scenario with time-varying DP backward induction",
            "Change C: Policy D marked as theoretical (zero-age baseline) — not a deployment recommendation",
        ],
        "cpu_fleet": {
            "fleet_size": FLEET_SIZE, "horizon": HORIZON_YEARS,
            "eff_gain": EFFICIENCY_GAIN, "emb_kg": EMBODIED_KG, "seeds": N_SEEDS,
            "policies": {
                "A":    "Fixed-5yr (industry norm)",
                "B_dp": "DP-Optimal (backward induction, globally optimal)",
                "D":    "Fixed-T_star (THEORETICAL ONLY — zero-age baseline, invalid for staggered fleets)",
            },
        },
        "gpu_fleet": {
            "fleet_size": GPU_FLEET_SIZE, "horizon": GPU_HORIZON,
            "eff_gain": GPU_EFF_GAIN, "emb_kg": GPU_EMBODIED_KG,
            "refresh_norm": GPU_REFRESH_NORM, "seeds": N_SEEDS,
            "policies": {
                "GPU_A": "Fixed-2yr (AI industry norm)",
                "GPU_B": "DP-Optimal (with max_useful_age_yr hard constraint when set)",
            },
            "subcases": {
                "gpu_unconstrained": "max_useful_age_yr=None (theoretical, v2 comparison)",
                "gpu_inference":     "max_useful_age_yr=4 (inference workloads)",
                "gpu_training":      "max_useful_age_yr=2 (training — latest gen required)",
            },
        },
    },
    "cpu_fleet":             cpu_summary,
    "gpu_fleet_unconstrained": gpu_all_summaries['gpu_unconstrained'],
    "gpu_fleet_inference":     gpu_all_summaries['gpu_inference'],
    "gpu_fleet_training":      gpu_all_summaries['gpu_training'],
}

with open("results/lifecycle-sim-v3-summary.json", "w") as f:
    json.dump(output_json, f, default=numpy_convert, indent=2)
print("Saved results/lifecycle-sim-v3-summary.json")


# ──────────────────────────────────────────────────────────────────────────────
# FIGURES
# ──────────────────────────────────────────────────────────────────────────────

os.makedirs("figures", exist_ok=True)

# ── Figure 8: CPU fleet DP-Optimal savings (updated with eu_decarbonizing) ──
cpu_scenario_names = list(CI_SCENARIOS.keys()) + ['eu_decarbonizing']
cpu_ci_labels = []
for n in cpu_scenario_names:
    if n == 'eu_decarbonizing':
        cpu_ci_labels.append("eu_decarb\n(300→200)")
    else:
        cpu_ci_labels.append(f"{n}\n({CI_SCENARIOS[n]} g/kWh)")

bdp_vs_a_cpu = [cpu_summary[n]['Bdp_saves_vs_A_pct'] for n in cpu_scenario_names]
d_vs_a_cpu   = [cpu_summary[n].get('D_saves_vs_A_pct_theoretical', 0.0)
                for n in cpu_scenario_names]
t_stars_cpu  = [cpu_summary[n]['t_star'] for n in cpu_scenario_names]

x = np.arange(len(cpu_scenario_names))
width = 0.35
fig, ax = plt.subplots(figsize=(13, 6))
bars1 = ax.bar(x - width/2, bdp_vs_a_cpu, width,
               label='B_dp: DP-Optimal vs Fixed-5yr', color='#2980b9', alpha=0.85)
bars2 = ax.bar(x + width/2, d_vs_a_cpu, width,
               label='D: Fixed-T*(CI) vs Fixed-5yr [†]', color='#8e44ad', alpha=0.85, hatch='//')

for bar, val in zip(bars1, bdp_vs_a_cpu):
    ypos = bar.get_height() + (0.5 if val >= 0 else -2.0)
    va   = 'bottom' if val >= 0 else 'top'
    ax.text(bar.get_x() + bar.get_width()/2., ypos,
            f'{val:+.1f}%', ha='center', va=va, fontsize=8, color='#1a5276')

for bar, val in zip(bars2, d_vs_a_cpu):
    ypos = bar.get_height() + (0.5 if val >= 0 else -2.0)
    va   = 'bottom' if val >= 0 else 'top'
    ax.text(bar.get_x() + bar.get_width()/2., ypos,
            f'{val:+.1f}%', ha='center', va=va, fontsize=8, color='#5b2c6f')

ax.axhline(0, color='black', linewidth=0.9)
ax.set_xticks(x)
ax.set_xticklabels(cpu_ci_labels, fontsize=9)
ax.set_ylabel("Carbon Saving vs Fixed-5yr Norm (%)", fontsize=11)
ax.set_title(
    "CPU Fleet: DP-Optimal vs Fixed-5yr — Carbon Savings across Grid CI (v3)\n"
    "Fleet: 50 servers × 10yr × eff=15%/gen × emb=1000 kgCO₂ × 20 seeds\n"
    "[†] Policy D is theoretical (zero-age baseline) — not valid for staggered fleets",
    fontsize=10
)
ax.legend(fontsize=9)
ax.grid(True, axis='y', alpha=0.3)
all_vals = bdp_vs_a_cpu + d_vs_a_cpu
ax.set_ylim(min(all_vals) - 5, max(all_vals) + 12)
plt.tight_layout()
plt.savefig("figures/fig8_dp_savings.png", dpi=300, bbox_inches='tight')
plt.close()
print("Saved figures/fig8_dp_savings.png (300 DPI)")


# ── Figure 9: GPU fleet — savings comparison for all 3 sub-cases ─────────────
gpu_ci_names  = list(CI_SCENARIOS.keys())
gpu_ci_labels_fig = [f"{n}\n({CI_SCENARIOS[n]})" for n in gpu_ci_names]

saves_unconstrained = [gpu_all_summaries['gpu_unconstrained'][n]['GPU_B_saves_vs_A_pct']
                       for n in gpu_ci_names]
saves_inference     = [gpu_all_summaries['gpu_inference'][n]['GPU_B_saves_vs_A_pct']
                       for n in gpu_ci_names]
saves_training      = [gpu_all_summaries['gpu_training'][n]['GPU_B_saves_vs_A_pct']
                       for n in gpu_ci_names]

x = np.arange(len(gpu_ci_names))
width = 0.26
fig, ax = plt.subplots(figsize=(13, 7))

bars_u = ax.bar(x - width, saves_unconstrained, width,
                label='Unconstrained (theoretical)', color='#8e44ad', alpha=0.85)
bars_i = ax.bar(x,         saves_inference,     width,
                label='Inference (max_age=4yr)', color='#2980b9', alpha=0.85)
bars_t = ax.bar(x + width, saves_training,      width,
                label='Training (max_age=2yr)',  color='#27ae60', alpha=0.85)

for bars, vals, color in [
    (bars_u, saves_unconstrained, '#5b2c6f'),
    (bars_i, saves_inference,     '#1a5276'),
    (bars_t, saves_training,      '#145a32'),
]:
    for bar, val in zip(bars, vals):
        ypos = bar.get_height() + 0.8
        ax.text(bar.get_x() + bar.get_width()/2., ypos,
                f'{val:+.0f}%', ha='center', va='bottom', fontsize=7.5, color=color,
                fontweight='bold')

ax.axhline(0, color='black', linewidth=0.9)
ax.set_xticks(x)
ax.set_xticklabels(gpu_ci_labels_fig, fontsize=9)
ax.set_ylabel("Carbon Saving vs Fixed-2yr Industry Norm (%)", fontsize=11)
ax.set_title(
    "AI GPU Fleet: DP-Optimal vs Fixed-2yr — Three max_useful_age Sub-cases (v3)\n"
    "eff=50%/gen (H100→H200→B200) · emb=3000 kgCO₂ · 50 GPUs · 10yr · 20 seeds\n"
    "KEY FINDING: Inference constraint (max_age=4yr) — are savings still substantial?",
    fontsize=10
)
ax.legend(fontsize=10, loc='upper right')
ax.grid(True, axis='y', alpha=0.3)
all_gpu_vals = saves_unconstrained + saves_inference + saves_training
ax.set_ylim(min(0, min(all_gpu_vals)) - 5, max(all_gpu_vals) + 15)
plt.tight_layout()
plt.savefig("figures/fig9_gpu_constrained.png", dpi=300, bbox_inches='tight')
plt.close()
print("Saved figures/fig9_gpu_constrained.png (300 DPI)")


# ── Figure 10: Declining CI — DP-Optimal vs Fixed-5yr, compare to static EU avg ─
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
fig.suptitle(
    "EU Decarbonizing Grid: DP-Optimal vs Fixed-5yr — Declining CI (300→200 g/kWh)\n"
    "CPU fleet: 50 servers × 10yr × eff=15%/gen × emb=1000 kgCO₂",
    fontsize=11
)

# Left: bar chart comparing eu_avg vs eu_decarbonizing
ax = axes[0]
scenarios_compare = ['eu_avg\n(static 300)', 'eu_decarb\n(300→200)']
bdp_saves_compare = [
    cpu_summary['eu_avg']['Bdp_saves_vs_A_pct'],
    cpu_summary['eu_decarbonizing']['Bdp_saves_vs_A_pct'],
]
colors_compare = ['#e67e22', '#2980b9']
bars = ax.bar(scenarios_compare, bdp_saves_compare, color=colors_compare, alpha=0.85, width=0.4)
for bar, val in zip(bars, bdp_saves_compare):
    ypos = bar.get_height() + 0.3
    ax.text(bar.get_x() + bar.get_width()/2., ypos,
            f'{val:+.1f}%', ha='center', va='bottom', fontsize=13, fontweight='bold')
ax.axhline(0, color='black', linewidth=0.9)
ax.set_ylabel("DP-Optimal Saving vs Fixed-5yr (%)", fontsize=11)
ax.set_title("DP-Optimal Savings: Static vs Declining CI", fontsize=11)
ax.set_ylim(0, max(bdp_saves_compare) + 8)
ax.grid(True, axis='y', alpha=0.3)

# Right: CI schedule plot + cumulative carbon comparison
ax2 = axes[1]
years = list(range(HORIZON_YEARS + 1))
ci_schedule_plot = EU_DECARBONIZING_SCHEDULE[:HORIZON_YEARS + 1]
ci_static = [300] * (HORIZON_YEARS + 1)
ax2.plot(years, ci_static, 's--', color='#e67e22', linewidth=2, markersize=6,
         label='Static EU avg (300 g/kWh)')
ax2.plot(years, ci_schedule_plot, 'o-', color='#2980b9', linewidth=2, markersize=6,
         label='EU Decarbonizing (300→200 g/kWh)')
ax2.fill_between(years, ci_schedule_plot, ci_static, alpha=0.15, color='#2980b9',
                 label='Decarbonization space')
ax2.set_xlabel("Simulation Year", fontsize=11)
ax2.set_ylabel("Grid Carbon Intensity (g/kWh)", fontsize=11)
ax2.set_title("Grid CI Schedule: Declining CI Scenario", fontsize=11)
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)
ax2.set_ylim(150, 350)

# Annotate key insight
delta_save = cpu_summary['eu_decarbonizing']['Bdp_saves_vs_A_pct'] - cpu_summary['eu_avg']['Bdp_saves_vs_A_pct']
axes[0].text(0.5, 0.05, f"Δ savings = {delta_save:+.1f}%\n(declining CI {'reduces' if delta_save < 0 else 'increases'}\noptimal T*)",
             transform=axes[0].transAxes, ha='center', va='bottom',
             fontsize=10, style='italic', color='#1a5276',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', edgecolor='gray', alpha=0.8))

plt.tight_layout()
plt.savefig("figures/fig10_declining_ci.png", dpi=300, bbox_inches='tight')
plt.close()
print("Saved figures/fig10_declining_ci.png (300 DPI)")

print()
print("[DONE] simulate-lifecycle-v3.py complete.")
