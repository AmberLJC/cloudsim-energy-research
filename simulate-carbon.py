#!/usr/bin/env python3
"""
Full Simulation — Direction #17: Carbon-Aware Temporal Deferral

Research claim: Batch jobs (30% of cloud workload) can be deferred to
low-carbon hours, reducing total operational carbon footprint by 5-15%
with near-zero energy overhead.

Policies:
  1. BASELINE  — run all jobs as they arrive (no deferral)
  2. THRESHOLD — defer batch if CI(t) > threshold; run when CI drops
  3. ADAPTIVE  — defer batch if CI(t) > rolling 4h mean; dynamic threshold
  4. ORACLE    — defer to global minimum CI slot within deadline window

Scenarios (3):
  - low_flex:    20% batch fraction, 4h max deferral, 150 gCO2/kWh threshold
  - medium_flex: 30% batch fraction, 6h max deferral, 120 gCO2/kWh threshold
  - high_flex:   40% batch fraction, 8h max deferral, 100 gCO2/kWh threshold

Experiment: 10 seeds × 4 policies × 3 scenarios = 120 runs

Primary metric: carbon saving % vs BASELINE
Secondary: energy overhead %, job wait time (mean hours)

Pre-registered: 2026-02-27
Null threshold: <2% carbon saving
Viable threshold: >5% carbon saving in 2/3 scenarios
"""

import numpy as np
import statistics
import csv
import json
import os
from collections import deque

# ─── Carbon intensity model ────────────────────────────────────────────────────
# Realistic US Midwest grid, 5-min resolution, 24h cycle
# Source: EIA 930 empirical pattern (synthetic approximation)

def carbon_intensity(t_hours: float) -> float:
    """gCO2/kWh as function of hour of day."""
    base = 150.0
    morning_peak = 200.0 * np.exp(-0.5 * ((t_hours - 8) / 1.5) ** 2)
    midday_dip   = -80.0  * np.exp(-0.5 * ((t_hours - 13) / 2.0) ** 2)
    evening_peak = 250.0  * np.exp(-0.5 * ((t_hours - 19) / 1.5) ** 2)
    overnight_dip = -60.0 * np.exp(-0.5 * ((t_hours - 2) / 2.0) ** 2)
    return max(base + morning_peak + midday_dip + evening_peak + overnight_dip, 30.0)

# Precompute CI curve at 5-min resolution
TIMESTEPS = 288  # 24h × 12 steps/h (5 min each)
DT_HOURS = 24.0 / TIMESTEPS
CI_CURVE = [carbon_intensity(i * DT_HOURS) for i in range(TIMESTEPS)]

# ─── Host power model (50-host DC, same as scale experiment) ──────────────────
NUM_HOSTS    = 50
HOST_P_MEAN  = 175.0   # W mean power per host
TOTAL_P_KW   = NUM_HOSTS * HOST_P_MEAN / 1000  # 8.75 kW

def workload_intensity(t_step: int, seed_offset: float = 0.0) -> float:
    """Business-hours load pattern [0.3, 1.0] with small noise."""
    t_h = t_step * DT_HOURS + seed_offset
    t_h_mod = t_h % 24
    if 8 <= t_h_mod <= 20:
        biz = 0.55 + 0.45 * np.sin(np.pi * (t_h_mod - 8) / 12)
    else:
        biz = 0.30
    return max(biz, 0.30)

# ─── Policies ─────────────────────────────────────────────────────────────────
POLICIES = ["baseline", "threshold", "adaptive", "oracle"]

SCENARIOS = {
    "low_flex":    {'batch_frac': 0.20, 'max_defer_steps': 48,  'ci_threshold': 150.0},
    "medium_flex": {'batch_frac': 0.30, 'max_defer_steps': 72,  'ci_threshold': 120.0},
    "high_flex":   {'batch_frac': 0.40, 'max_defer_steps': 96,  'ci_threshold': 100.0},
}

SEEDS = list(range(10))


def simulate_scenario(seed: int, scenario: dict, policy: str) -> dict:
    """Run a 24h simulation for one seed, scenario, policy combo."""
    rng = np.random.default_rng(seed)
    batch_frac = scenario['batch_frac']
    max_defer  = scenario['max_defer_steps']
    ci_thresh  = scenario['ci_threshold']

    # Precompute rolling mean CI for adaptive policy
    window = 48  # 4-hour rolling window
    rolling_mean_ci = []
    for i in range(TIMESTEPS):
        start = max(0, i - window)
        rolling_mean_ci.append(statistics.mean(CI_CURVE[start:i+1]))

    # For oracle: precompute best future slot within window
    def best_future_ci(step, max_future):
        end = min(TIMESTEPS, step + max_future)
        best_step = step
        best_ci = CI_CURVE[step]
        for s in range(step, end):
            if CI_CURVE[s] < best_ci:
                best_ci = CI_CURVE[s]
                best_step = s
        return best_step, best_ci

    total_energy_kwh = 0.0  # kWh
    total_carbon = 0.0       # gCO2

    # Deferred queue: list of (energy_kwh, deadline_step)
    deferred_queue = []
    wait_times = []  # hours waited per deferred batch job

    # Small random offset per seed for workload noise
    seed_offset = rng.uniform(0, 2)  # up to 2h phase shift

    for step in range(TIMESTEPS):
        ci = CI_CURVE[step]
        load = workload_intensity(step, seed_offset)

        # Add small per-step demand noise
        noisy_load = float(np.clip(load + rng.normal(0, 0.03), 0.25, 1.0))
        power_kw = TOTAL_P_KW * noisy_load
        job_kwh  = power_kw * DT_HOURS

        interactive_kwh = job_kwh * (1.0 - batch_frac)
        batch_kwh       = job_kwh * batch_frac

        # Interactive always runs now
        total_energy_kwh += interactive_kwh
        total_carbon     += interactive_kwh * ci

        # Determine what to do with batch based on policy
        if policy == "baseline":
            # Run immediately
            total_energy_kwh += batch_kwh
            total_carbon     += batch_kwh * ci

        elif policy == "threshold":
            if ci <= ci_thresh:
                total_energy_kwh += batch_kwh
                total_carbon     += batch_kwh * ci
            else:
                deadline = step + max_defer
                deferred_queue.append((batch_kwh, deadline, step))

        elif policy == "adaptive":
            # Defer if current CI > rolling mean (dynamic threshold)
            dyn_thresh = rolling_mean_ci[step]
            if ci <= dyn_thresh:
                total_energy_kwh += batch_kwh
                total_carbon     += batch_kwh * ci
            else:
                deadline = step + max_defer
                deferred_queue.append((batch_kwh, deadline, step))

        elif policy == "oracle":
            # Look ahead: if current is not near minimum, defer
            best_step, best_ci = best_future_ci(step, max_defer)
            if step == best_step or best_ci >= ci:
                # Current is already best or no better slot
                total_energy_kwh += batch_kwh
                total_carbon     += batch_kwh * ci
            else:
                # Defer to best future slot (model: will run at best_ci)
                total_energy_kwh += batch_kwh
                total_carbon     += batch_kwh * best_ci
                wait_times.append((best_step - step) * DT_HOURS)

        # Run expired deferred jobs (deadline reached)
        still_deferred = []
        for (energy, deadline, submit_step) in deferred_queue:
            if step >= deadline:
                total_energy_kwh += energy
                total_carbon     += energy * ci
                wait_times.append((step - submit_step) * DT_HOURS)
            elif ci <= ci_thresh * 0.9:
                # Low-carbon window — run now
                total_energy_kwh += energy
                total_carbon     += energy * ci
                wait_times.append((step - submit_step) * DT_HOURS)
            else:
                still_deferred.append((energy, deadline, submit_step))
        deferred_queue = still_deferred

    # Run all remaining deferred jobs at last step
    for (energy, _, submit_step) in deferred_queue:
        ci_last = CI_CURVE[-1]
        total_energy_kwh += energy
        total_carbon     += energy * ci_last
        wait_times.append((TIMESTEPS - 1 - submit_step) * DT_HOURS)

    mean_wait = statistics.mean(wait_times) if wait_times else 0.0

    return {
        'energy_kwh':   total_energy_kwh,
        'carbon_gCO2':  total_carbon,
        'mean_wait_h':  mean_wait,
        'n_deferred':   len(wait_times),
    }


def main():
    out_dir = "results/carbon"
    os.makedirs(out_dir, exist_ok=True)

    all_results = []
    total_runs = len(SEEDS) * len(POLICIES) * len(SCENARIOS)
    run_num = 0

    print("=" * 75)
    print("Carbon-Aware Temporal Deferral — Full Simulation (120 runs)")
    print("=" * 75)
    print()

    for sc_name, scenario in SCENARIOS.items():
        for policy in POLICIES:
            seed_runs = []
            for seed in SEEDS:
                r = simulate_scenario(seed, scenario, policy)
                row = {
                    'scenario': sc_name,
                    'policy':   policy,
                    'seed':     seed,
                    **r,
                }
                all_results.append(row)
                seed_runs.append(r)
                run_num += 1

    # Write CSV
    csv_path = f"{out_dir}/results.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
        writer.writeheader()
        writer.writerows(all_results)
    print(f"CSV written: {csv_path}")
    print()

    # ── Analysis
    print("=" * 75)
    print("RESULTS SUMMARY")
    print("=" * 75)
    print()

    # Baseline energy/carbon per scenario
    baseline_carbon = {}
    baseline_energy = {}
    for sc_name in SCENARIOS:
        rows = [r for r in all_results if r['scenario'] == sc_name and r['policy'] == 'baseline']
        baseline_carbon[sc_name] = statistics.mean(r['carbon_gCO2'] for r in rows)
        baseline_energy[sc_name] = statistics.mean(r['energy_kwh'] for r in rows)

    print(f"{'Policy':<12} {'Scenario':<14} {'Energy (kWh)':>13} {'Carbon (kgCO2)':>15} {'C saving':>9} {'E overhead':>11} {'Wait (h)':>9}")
    print("-" * 90)

    scenario_carbon_savings = {sc: [] for sc in SCENARIOS}

    for policy in POLICIES:
        for sc_name in SCENARIOS:
            rows = [r for r in all_results if r['scenario'] == sc_name and r['policy'] == policy]
            mean_e  = statistics.mean(r['energy_kwh'] for r in rows)
            mean_c  = statistics.mean(r['carbon_gCO2'] for r in rows)
            mean_w  = statistics.mean(r['mean_wait_h'] for r in rows)
            c_save  = (baseline_carbon[sc_name] - mean_c) / baseline_carbon[sc_name] * 100
            e_delta = (mean_e - baseline_energy[sc_name]) / baseline_energy[sc_name] * 100
            if policy != 'baseline':
                scenario_carbon_savings[sc_name].append(c_save)
            print(f"{policy:<12} {sc_name:<14} {mean_e:>13.2f} {mean_c/1e3:>15.3f} {c_save:>8.2f}% {e_delta:>10.2f}% {mean_w:>9.2f}")
        print()

    # ── Verdict
    print("=" * 75)
    print("STOPPING RULE EVALUATION")
    print("=" * 75)
    print()

    best_per_scenario = {}
    for sc_name, savings_list in scenario_carbon_savings.items():
        best = max(savings_list) if savings_list else 0
        best_per_scenario[sc_name] = best
        best_policy = POLICIES[1 + savings_list.index(best)]  # skip baseline
        print(f"  {sc_name}: best carbon saving = {best:.2f}% (policy: {best_policy})")

    scenarios_above_5 = sum(1 for v in best_per_scenario.values() if v >= 5.0)
    scenarios_above_2 = sum(1 for v in best_per_scenario.values() if v >= 2.0)
    mean_best = statistics.mean(best_per_scenario.values())

    print()
    print(f"  Scenarios with ≥5% carbon saving: {scenarios_above_5}/3")
    print(f"  Scenarios with ≥2% carbon saving: {scenarios_above_2}/3")
    print(f"  Mean best carbon saving: {mean_best:.2f}%")
    print()

    if scenarios_above_5 >= 2:
        verdict = "✅ VIABLE — Carbon saving ≥ 5% in ≥2/3 scenarios. Proceed to write-up."
    elif scenarios_above_2 >= 2:
        verdict = "⚠️  BORDERLINE — Carbon saving 2–5%. May need additional angles."
    else:
        verdict = "❌ NULL — Carbon saving < 2%. Pivot."

    print(f"  VERDICT: {verdict}")
    print()

    # ── Energy overhead check
    print("ENERGY OVERHEAD (key safety check):")
    for policy in ['threshold', 'adaptive', 'oracle']:
        rows = [r for r in all_results if r['policy'] == policy]
        all_base_rows = [r for r in all_results if r['policy'] == 'baseline' and r['scenario'] == r['scenario']]
        delta_list = []
        for sc_name in SCENARIOS:
            p_rows = [r for r in all_results if r['scenario'] == sc_name and r['policy'] == policy]
            b_rows = [r for r in all_results if r['scenario'] == sc_name and r['policy'] == 'baseline']
            pe = statistics.mean(r['energy_kwh'] for r in p_rows)
            be = statistics.mean(r['energy_kwh'] for r in b_rows)
            delta_list.append((pe - be) / be * 100)
        print(f"  {policy}: mean energy overhead = {statistics.mean(delta_list):.2f}%")

    print()

    # ── Summary JSON
    summary = {
        'total_runs': len(all_results),
        'verdict': verdict,
        'best_per_scenario': best_per_scenario,
        'mean_best_carbon_saving_pct': mean_best,
        'scenarios_above_5pct': scenarios_above_5,
        'scenarios_above_2pct': scenarios_above_2,
    }
    with open(f"{out_dir}/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Summary JSON written: {out_dir}/summary.json")


if __name__ == '__main__':
    main()
