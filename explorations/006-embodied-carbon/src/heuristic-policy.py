#!/usr/bin/env python3
"""
heuristic-policy.py
Exploration #006 — Embodied Carbon Lifecycle Optimization
Task 2: Derive a practical 2-parameter threshold heuristic that approximates DP-Optimal
        without requiring future CI or efficiency forecasts.

Heuristic policy:
  "Replace any server older than age_threshold years if current CI exceeds CI_threshold;
   otherwise hold until max_useful_age."

Author: Research Worker (subagent) | 2026-02-28
"""

import json
import itertools
import numpy as np
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Fleet / simulation parameters (must match simulate-lifecycle-v3.py)
# ──────────────────────────────────────────────────────────────────────────────
FLEET_SIZE   = 50
HORIZON      = 10
EFF_GAIN_CPU = 0.15          # 15 %/gen efficiency improvement (CPU)
EFF_GAIN_GPU = 0.50          # 50 %/gen efficiency improvement (GPU)
EMB_KG_CPU   = 1_000.0      # kg CO₂eq per CPU server replacement
EMB_KG_GPU   = 3_000.0      # kg CO₂eq per GPU server replacement
P_BASE_CPU   = 250.0         # W baseline power (CPU)
P_BASE_GPU   = 300.0         # W baseline power (GPU rack, approx)
HOURS_YEAR   = 8_760
N_SEEDS      = 20
REFRESH_NORM_CPU = 5         # industry norm for CPU
REFRESH_NORM_GPU = 2         # industry norm for GPU

CI_SCENARIOS = {
    "nuclear_fr":    50,
    "norway_hydro":  100,
    "eu_avg":        300,
    "us_avg":        400,
    "uk_grid":       500,
    "coal_pl":       800,
}

MAX_USEFUL_AGE_INFERENCE = 4   # GPU inference hard ceiling


# ──────────────────────────────────────────────────────────────────────────────
# Core simulation helpers
# ──────────────────────────────────────────────────────────────────────────────

def annual_op_carbon(gen: int, ci_g_per_kwh: float, p_base: float, eff_gain: float) -> float:
    """Annual operational carbon for hardware generation `gen` (kg CO₂eq)."""
    power_w = p_base * (1 - eff_gain) ** gen
    return power_w / 1_000 * HOURS_YEAR * ci_g_per_kwh / 1_000  # kg


def simulate_fleet(
    policy,          # callable(age, gen, ci, years_remaining) -> bool (True = replace)
    ci: float,
    p_base: float,
    eff_gain: float,
    emb_kg: float,
    refresh_norm: int,
    max_useful_age: int | None,
    n_seeds: int = N_SEEDS,
    fleet_size: int = FLEET_SIZE,
    horizon: int = HORIZON,
) -> tuple[float, float, float]:
    """
    Simulate fleet under given policy.
    Returns (mean_total_carbon, std_total_carbon, mean_replacements).
    """
    totals = []
    reps   = []

    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        # Staggered initial ages: uniform [0, refresh_norm)
        ages = rng.integers(0, refresh_norm, size=fleet_size).tolist()
        gens = [0] * fleet_size

        total_carbon   = 0.0
        n_replacements = 0

        for year in range(horizon):
            years_remaining = horizon - year
            for i in range(fleet_size):
                # Hard age constraint: must replace if at/past max_useful_age
                force_replace = (max_useful_age is not None and ages[i] >= max_useful_age)
                want_replace  = policy(ages[i], gens[i], ci, years_remaining)

                if force_replace or want_replace:
                    total_carbon   += emb_kg
                    n_replacements += 1
                    gens[i]        += 1
                    ages[i]         = 0

                total_carbon += annual_op_carbon(gens[i], ci, p_base, eff_gain)
                ages[i]      += 1

        totals.append(total_carbon)
        reps.append(n_replacements)

    return float(np.mean(totals)), float(np.std(totals)), float(np.mean(reps))


# ──────────────────────────────────────────────────────────────────────────────
# Fixed-norm policy (industry baseline)
# ──────────────────────────────────────────────────────────────────────────────

def make_fixed_norm_policy(refresh_norm: int):
    def policy(age, gen, ci, years_remaining):
        return age >= refresh_norm
    return policy


# ──────────────────────────────────────────────────────────────────────────────
# Threshold heuristic policy
# ──────────────────────────────────────────────────────────────────────────────

def make_threshold_policy(age_threshold: int, ci_threshold: float):
    """
    Replace if:
      - server age >= age_threshold  AND  current CI >= ci_threshold
    Otherwise hold until max_useful_age (enforced by the simulator).
    No future knowledge required: decision uses only current age and current CI.
    """
    def policy(age, gen, ci, years_remaining):
        return (age >= age_threshold) and (ci >= ci_threshold)
    return policy


# ──────────────────────────────────────────────────────────────────────────────
# Grid search over (age_threshold, ci_threshold)
# ──────────────────────────────────────────────────────────────────────────────

def grid_search_heuristic(
    p_base: float,
    eff_gain: float,
    emb_kg: float,
    refresh_norm: int,
    max_useful_age: int | None,
    fleet_label: str,
    dp_savings_pct: dict,   # scenario -> DP saving % vs fixed-norm (from v3 results)
):
    print(f"\n{'='*60}")
    print(f"Fleet: {fleet_label}  |  max_useful_age={max_useful_age}")
    print(f"{'='*60}")

    age_thresholds = list(range(1, (max_useful_age or HORIZON) + 1))
    ci_thresholds  = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800]

    # Pre-compute Fixed-norm baseline for each CI scenario
    fixed_norm_policy = make_fixed_norm_policy(refresh_norm)
    baseline = {}
    for scenario, ci in CI_SCENARIOS.items():
        mean_c, _, _ = simulate_fleet(
            fixed_norm_policy, ci, p_base, eff_gain, emb_kg,
            refresh_norm, max_useful_age
        )
        baseline[scenario] = mean_c

    # Grid search: evaluate each (age_thresh, ci_thresh) pair
    best_score      = -1e18
    best_params     = None
    best_per_scenario = None

    results_log = []

    for age_t, ci_t in itertools.product(age_thresholds, ci_thresholds):
        heuristic_policy = make_threshold_policy(age_t, ci_t)
        savings_vs_fixed = {}

        for scenario, ci in CI_SCENARIOS.items():
            mean_c, _, _ = simulate_fleet(
                heuristic_policy, ci, p_base, eff_gain, emb_kg,
                refresh_norm, max_useful_age
            )
            fixed_c = baseline[scenario]
            savings_pct = (fixed_c - mean_c) / fixed_c * 100
            savings_vs_fixed[scenario] = savings_pct

        # Score = mean saving across all scenarios (unweighted)
        score = np.mean(list(savings_vs_fixed.values()))

        results_log.append({
            "age_threshold": age_t,
            "ci_threshold":  ci_t,
            "mean_saving_vs_fixed": round(score, 4),
            "per_scenario":  {k: round(v, 4) for k, v in savings_vs_fixed.items()},
        })

        if score > best_score:
            best_score      = score
            best_params     = (age_t, ci_t)
            best_per_scenario = savings_vs_fixed

    print(f"\nBest params: age_threshold={best_params[0]}, ci_threshold={best_params[1]}")
    print(f"Mean saving vs Fixed-norm: {best_score:.2f}%")
    print("\nPer-scenario comparison (Heuristic vs Fixed-norm vs DP-Optimal):")
    print(f"{'Scenario':<18} {'Fixed→Heur%':>12} {'Fixed→DP%':>12} {'Heur/DP%':>10}")
    print("-" * 54)
    for scenario in CI_SCENARIOS:
        h_save  = best_per_scenario[scenario]
        dp_save = dp_savings_pct.get(scenario, 0.0)
        ratio   = (h_save / dp_save * 100) if dp_save > 0 else float("nan")
        print(f"{scenario:<18} {h_save:>+11.1f}% {dp_save:>+11.1f}% {ratio:>9.1f}%")

    return best_params, best_score, best_per_scenario, results_log


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    out_dir = Path(__file__).parent.parent / "results"
    out_dir.mkdir(exist_ok=True)

    # Load v3 DP savings from existing results for reference
    v3_path = Path(__file__).parent / "results" / "lifecycle-sim-v3-summary.json"
    with open(v3_path) as f:
        v3 = json.load(f)

    dp_savings_cpu = {
        sc: v3["cpu_fleet"][sc]["Bdp_saves_vs_A_pct"]
        for sc in CI_SCENARIOS
        if sc in v3["cpu_fleet"]
    }
    dp_savings_gpu_inf = {
        sc: v3["gpu_fleet_inference"][sc]["GPU_B_saves_vs_A_pct"]
        for sc in CI_SCENARIOS
        if sc in v3["gpu_fleet_inference"]
    }

    output = {}

    # ── CPU Fleet ──────────────────────────────────────────────────────────────
    (cpu_age_t, cpu_ci_t), cpu_score, cpu_per_sc, cpu_log = grid_search_heuristic(
        p_base         = P_BASE_CPU,
        eff_gain       = EFF_GAIN_CPU,
        emb_kg         = EMB_KG_CPU,
        refresh_norm   = REFRESH_NORM_CPU,
        max_useful_age = None,
        fleet_label    = "CPU (no hard ceiling)",
        dp_savings_pct = dp_savings_cpu,
    )

    # Compute Heuristic/DP ratio for best CPU params
    cpu_heur_dp_ratios = {}
    for sc in CI_SCENARIOS:
        h = cpu_per_sc[sc]
        d = dp_savings_cpu.get(sc, 0.0)
        cpu_heur_dp_ratios[sc] = round(h / d * 100, 2) if d > 0 else None

    output["cpu_fleet"] = {
        "best_age_threshold": cpu_age_t,
        "best_ci_threshold":  cpu_ci_t,
        "mean_saving_vs_fixed5yr_pct": round(cpu_score, 4),
        "per_scenario_saving_vs_fixed_pct":  {k: round(v, 4) for k, v in cpu_per_sc.items()},
        "dp_savings_pct": {k: round(v, 4) for k, v in dp_savings_cpu.items()},
        "heuristic_captures_pct_of_dp":  cpu_heur_dp_ratios,
        "grid_search_log": cpu_log,
    }

    # ── GPU Inference Fleet (max_useful_age=4) ────────────────────────────────
    (gpu_age_t, gpu_ci_t), gpu_score, gpu_per_sc, gpu_log = grid_search_heuristic(
        p_base         = P_BASE_GPU,
        eff_gain       = EFF_GAIN_GPU,
        emb_kg         = EMB_KG_GPU,
        refresh_norm   = REFRESH_NORM_GPU,
        max_useful_age = MAX_USEFUL_AGE_INFERENCE,
        fleet_label    = "GPU Inference (max_useful_age=4yr)",
        dp_savings_pct = dp_savings_gpu_inf,
    )

    gpu_heur_dp_ratios = {}
    for sc in CI_SCENARIOS:
        h = gpu_per_sc[sc]
        d = dp_savings_gpu_inf.get(sc, 0.0)
        gpu_heur_dp_ratios[sc] = round(h / d * 100, 2) if d > 0 else None

    output["gpu_fleet_inference"] = {
        "best_age_threshold": gpu_age_t,
        "best_ci_threshold":  gpu_ci_t,
        "mean_saving_vs_fixed2yr_pct": round(gpu_score, 4),
        "per_scenario_saving_vs_fixed_pct":  {k: round(v, 4) for k, v in gpu_per_sc.items()},
        "dp_savings_pct": {k: round(v, 4) for k, v in dp_savings_gpu_inf.items()},
        "heuristic_captures_pct_of_dp":  gpu_heur_dp_ratios,
        "grid_search_log": gpu_log,
    }

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"CPU best heuristic:  age ≥ {cpu_age_t} yr  AND  CI ≥ {cpu_ci_t} g/kWh")
    print(f"  Mean saving vs Fixed-5yr: {cpu_score:.1f}%")
    cpu_mean_ratio = np.mean([v for v in cpu_heur_dp_ratios.values() if v is not None])
    print(f"  Captures {cpu_mean_ratio:.0f}% of DP savings on average")

    print(f"\nGPU(inf) best heuristic: age ≥ {gpu_age_t} yr  AND  CI ≥ {gpu_ci_t} g/kWh")
    print(f"  Mean saving vs Fixed-2yr: {gpu_score:.1f}%")
    gpu_mean_ratio = np.mean([v for v in gpu_heur_dp_ratios.values() if v is not None])
    print(f"  Captures {gpu_mean_ratio:.0f}% of DP savings on average")

    output["summary"] = {
        "cpu_heuristic":  f"age >= {cpu_age_t} AND CI >= {cpu_ci_t} g/kWh",
        "gpu_heuristic":  f"age >= {gpu_age_t} AND CI >= {gpu_ci_t} g/kWh",
        "cpu_mean_saving_pct":  round(cpu_score, 2),
        "gpu_mean_saving_pct":  round(gpu_score, 2),
        "cpu_captures_dp_pct":  round(float(cpu_mean_ratio), 1),
        "gpu_captures_dp_pct":  round(float(gpu_mean_ratio), 1),
        "within_5pct_of_dp":    {
            "cpu": all(
                abs(dp_savings_cpu.get(sc, 0) - cpu_per_sc[sc]) <= 5.0
                for sc in CI_SCENARIOS if sc in dp_savings_cpu
            ),
            "gpu_inference": all(
                abs(dp_savings_gpu_inf.get(sc, 0) - gpu_per_sc[sc]) <= 5.0
                for sc in CI_SCENARIOS if sc in dp_savings_gpu_inf
            ),
        },
        "description": (
            "2-parameter threshold heuristic: replace server if age >= age_threshold "
            "AND current grid CI >= ci_threshold. No future knowledge required. "
            "max_useful_age hard ceiling still applies (enforced by operator constraint)."
        ),
    }

    out_path = out_dir / "heuristic-policy-results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    main()
