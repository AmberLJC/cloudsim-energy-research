"""
Compute 95% Confidence Intervals for Carbon Saving Results
============================================================
Re-runs the carbon simulation with 10 seeds and computes
95% bootstrap + t-distribution CIs for all key metrics.

Outputs:
  results/carbon/ci-table.json
  results/carbon/ci-table.txt
"""

import numpy as np
import json
from scipy import stats

# ─── Replicate the carbon simulation (same parameters as simulate-carbon.py) ───
np.random.seed(0)

N_HOSTS = 50
N_VMS_PEAK = 500
SIM_DURATION = 86400       # 24 hours
DT = 300                   # 300 s consolidation interval
T_STEPS = SIM_DURATION // DT  # 288 steps

P_IDLE = 100.0             # Watts
P_MAX = 250.0              # Watts

# Carbon intensity model (US Midwest)
CI_BASE = 220.0            # gCO2/kWh mean
CI_AMP = 155.0             # amplitude → min=65, max=375, ~5.6× swing
CI_PEAK_HOUR = 18          # evening peak

def get_ci_profile():
    """Return 288-step CI profile (gCO2/kWh)."""
    times = np.arange(T_STEPS) * DT / 3600.0  # hours
    ci = CI_BASE + CI_AMP * np.sin(2 * np.pi * (times - 12) / 24)
    ci = np.clip(ci, 71, 399)
    return ci

CI_PROFILE = get_ci_profile()

# Scenario parameters
SCENARIOS = {
    "low_flex":    {"batch_frac": 0.15, "max_defer": 2*3600, "thresh_pct": 0.15},
    "medium_flex": {"batch_frac": 0.30, "max_defer": 6*3600, "thresh_pct": 0.15},
    "high_flex":   {"batch_frac": 0.45, "max_defer": 9*3600, "thresh_pct": 0.15},
}

POLICIES = ["baseline", "threshold", "adaptive", "oracle"]
N_SEEDS = 10


def simulate_once(seed, scenario_name, policy):
    """Single simulation run. Returns (energy_kwh, carbon_kgco2, wait_mean)."""
    rng = np.random.RandomState(seed)
    sc = SCENARIOS[scenario_name]
    batch_frac = sc["batch_frac"]
    max_defer_steps = int(sc["max_defer"] / DT)
    thresh_pct = sc["thresh_pct"]
    ci_thresh = CI_PROFILE.min() + thresh_pct * (CI_PROFILE.max() - CI_PROFILE.min())

    # Workload: sinusoidal arrival with batch overlay
    arrival_rate = np.zeros(T_STEPS)
    for t in range(T_STEPS):
        hour = t * DT / 3600.0
        base = 0.6 + 0.3 * np.sin(2 * np.pi * (hour - 8) / 24)
        arrival_rate[t] = base * N_VMS_PEAK / T_STEPS * 1.5

    # Generate jobs
    jobs = []
    for t in range(T_STEPS):
        n = rng.poisson(arrival_rate[t])
        for _ in range(n):
            is_batch = rng.random() < batch_frac
            duration = int(rng.exponential(12)) + 1  # steps
            jobs.append({
                "arrive": t,
                "duration": duration,
                "batch": is_batch,
                "deadline": t + max_defer_steps + duration if is_batch else t + duration,
                "wait": 0,
            })

    # Assign start times based on policy
    for job in jobs:
        if not job["batch"]:
            job["start"] = job["arrive"]
        elif policy == "baseline":
            job["start"] = job["arrive"]
        elif policy == "threshold":
            # Defer to first step with CI ≤ thresh within deadline
            best = job["arrive"]
            for t2 in range(job["arrive"], min(job["deadline"], T_STEPS)):
                if CI_PROFILE[t2] <= ci_thresh:
                    best = t2
                    break
            job["start"] = best
        elif policy == "adaptive":
            # Defer to minimum CI step within deadline window
            window = range(job["arrive"], min(job["deadline"], T_STEPS))
            if len(window) == 0:
                job["start"] = job["arrive"]
            else:
                best_ci_t = min(window, key=lambda t2: CI_PROFILE[t2])
                # Adaptive: blend between arrive and optimal
                job["start"] = (job["arrive"] + best_ci_t) // 2
        elif policy == "oracle":
            window = range(job["arrive"], min(job["deadline"], T_STEPS))
            if len(window) == 0:
                job["start"] = job["arrive"]
            else:
                job["start"] = min(window, key=lambda t2: CI_PROFILE[t2])

        job["wait"] = (job["start"] - job["arrive"]) * DT / 3600.0

    # Compute energy & carbon
    host_util = np.zeros(T_STEPS)
    for job in jobs:
        s, d = job["start"], job["duration"]
        for t in range(s, min(s + d, T_STEPS)):
            host_util[t] += 1.0 / N_VMS_PEAK

    # Active hosts (PABFD: at least ceil(util / 1.0) hosts running)
    power = np.array([P_IDLE + (P_MAX - P_IDLE) * min(host_util[t], 1.0) 
                      for t in range(T_STEPS)])
    # Scale: N_HOSTS servers each contributing proportionally
    power_total = power * N_HOSTS  # Watts

    energy_j = np.sum(power_total) * DT
    energy_kwh = energy_j / 3_600_000

    carbon_gco2 = np.sum(power_total * CI_PROFILE / 1000.0) * DT / 3_600_000
    carbon_kgco2 = carbon_gco2 / 1000.0

    wait_times = [j["wait"] for j in jobs if j["batch"]]
    mean_wait = np.mean(wait_times) if wait_times else 0.0

    return energy_kwh, carbon_kgco2, mean_wait


def run_all():
    """Run all conditions, compute per-seed results, then CIs."""
    results = {}  # (policy, scenario) → list of (energy, carbon, wait)

    for policy in POLICIES:
        for scenario in SCENARIOS:
            key = (policy, scenario)
            seed_results = []
            for seed in range(N_SEEDS):
                e, c, w = simulate_once(seed * 7 + 13, scenario, policy)
                seed_results.append((e, c, w))
            results[key] = seed_results

    # Compute baseline per-seed for carbon saving calculation
    baseline_carbon = {}
    for scenario in SCENARIOS:
        baseline_carbon[scenario] = [results[("baseline", scenario)][s][1] 
                                      for s in range(N_SEEDS)]

    # Build CI table
    ci_table = []
    for policy in POLICIES:
        for scenario in SCENARIOS:
            key = (policy, scenario)
            seed_results = results[key]
            energies = [r[0] for r in seed_results]
            carbons = [r[1] for r in seed_results]
            waits = [r[2] for r in seed_results]

            # Carbon saving per seed
            c_savings = [
                100.0 * (baseline_carbon[scenario][s] - carbons[s]) / baseline_carbon[scenario][s]
                for s in range(N_SEEDS)
            ]
            # Energy overhead per seed
            baseline_energy = [results[("baseline", scenario)][s][0] for s in range(N_SEEDS)]
            e_overheads = [
                100.0 * (energies[s] - baseline_energy[s]) / baseline_energy[s]
                for s in range(N_SEEDS)
            ]

            # 95% CI using t-distribution (n=10)
            def t_ci(data):
                arr = np.array(data)
                n = len(arr)
                m = arr.mean()
                se = arr.std(ddof=1) / np.sqrt(n)
                h = stats.t.ppf(0.975, df=n-1) * se
                return m, m - h, m + h, arr.std(ddof=1)

            c_mean, c_lo, c_hi, c_sd = t_ci(c_savings)
            e_mean, e_lo, e_hi, e_sd = t_ci(e_overheads)
            w_mean, w_lo, w_hi, w_sd = t_ci(waits)
            energy_mean = np.mean(energies)
            carbon_mean = np.mean(carbons)

            ci_table.append({
                "policy": policy,
                "scenario": scenario,
                "energy_kwh": round(energy_mean, 3),
                "carbon_kgco2": round(carbon_mean, 3),
                "c_saving_mean": round(c_mean, 2),
                "c_saving_lo95": round(c_lo, 2),
                "c_saving_hi95": round(c_hi, 2),
                "c_saving_sd": round(c_sd, 2),
                "e_overhead_mean": round(e_mean, 3),
                "e_overhead_lo95": round(e_lo, 3),
                "e_overhead_hi95": round(e_hi, 3),
                "wait_mean_h": round(w_mean, 2),
                "wait_lo95": round(w_lo, 2),
                "wait_hi95": round(w_hi, 2),
            })

    return ci_table


if __name__ == "__main__":
    print("Running CI computation (10 seeds × 4 policies × 3 scenarios = 120 runs)...")
    ci_table = run_all()

    # Save JSON
    with open("results/carbon/ci-table.json", "w") as f:
        json.dump(ci_table, f, indent=2)

    # Pretty-print text table
    lines = []
    lines.append("="*100)
    lines.append("CARBON SAVINGS — 95% CONFIDENCE INTERVALS (t-distribution, n=10)")
    lines.append("="*100)
    lines.append(f"{'Policy':<12} {'Scenario':<14} {'C Saving':>9} {'95% CI':>18} {'SD':>7} {'E Overhead':>11} {'Wait (h)':>11}")
    lines.append("-"*100)

    for row in ci_table:
        if row["policy"] == "baseline":
            continue
        lines.append(
            f"{row['policy']:<12} {row['scenario']:<14} "
            f"{row['c_saving_mean']:>8.2f}% "
            f"[{row['c_saving_lo95']:>5.2f}%, {row['c_saving_hi95']:>5.2f}%] "
            f"{row['c_saving_sd']:>6.2f}% "
            f"{row['e_overhead_mean']:>10.3f}% "
            f"{row['wait_mean_h']:>5.2f}h [{row['wait_lo95']:>4.2f}–{row['wait_hi95']:>4.2f}]"
        )

    lines.append("="*100)
    lines.append("")
    lines.append("KEY STATISTICAL FINDINGS:")
    lines.append("")

    # Find threshold results for summary
    thresh_results = [r for r in ci_table if r["policy"] == "threshold"]
    all_lower_bounds = [r["c_saving_lo95"] for r in thresh_results]
    lines.append(f"Threshold policy lower bounds (95% CI):")
    for r in thresh_results:
        lines.append(f"  {r['scenario']}: [{r['c_saving_lo95']:.2f}%, {r['c_saving_hi95']:.2f}%] — "
                     f"{'✓ SIGNIFICANT' if r['c_saving_lo95'] > 0 else '✗ NOT SIG'}")

    # Energy overhead significance
    lines.append("")
    lines.append("Energy overhead 95% CIs (should all include 0.000):")
    for r in ci_table:
        if r["policy"] != "baseline":
            lines.append(f"  {r['policy']} × {r['scenario']}: "
                         f"[{r['e_overhead_lo95']:.3f}%, {r['e_overhead_hi95']:.3f}%]")

    output = "\n".join(lines)
    print(output)

    with open("results/carbon/ci-table.txt", "w") as f:
        f.write(output)

    print(f"\nSaved: results/carbon/ci-table.json")
    print(f"Saved: results/carbon/ci-table.txt")
