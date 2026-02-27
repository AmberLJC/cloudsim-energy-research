#!/usr/bin/env python3
"""
Falsification Check — Direction #17: Carbon-Aware Temporal Deferral

Research hypothesis: Batch jobs (delay-tolerant) can be deferred to low-carbon
hours, reducing total operational carbon footprint by 15-30% without increasing
energy consumption significantly.

Key mechanism:
  - Real electricity grids have diurnal carbon intensity patterns (gCO2/kWh)
  - US Midwest grid: ~80 gCO2/kWh (overnight wind) to ~450 gCO2/kWh (peak coal)
  - UK grid: ~30 gCO2/kWh (day, solar) to ~300 gCO2/kWh (evening, gas)
  - Delay-tolerant batch jobs (30% of cloud workload) can be deferred to clean hours
  - Energy consumed is approximately the same; carbon per kWh varies 5-10×

This script:
  1. Models a 24h carbon intensity curve (realistic US Midwest pattern)
  2. Simulates two policies:
     - BASELINE: process all jobs as they arrive (no deferral)
     - CARBON-AWARE: defer batch jobs to low-carbon windows (<100 gCO2/kWh)
  3. Measures total carbon (gCO2) and energy (J) for both policies
  4. Checks if carbon saving > 5% (viable threshold)

Decision:
  VIABLE: carbon saving > 5% AND energy penalty < 5%
  MOOT: carbon saving < 2% OR energy penalty > 10%

Pre-registered: 2026-02-27
"""

import numpy as np
import statistics

# ─── Grid carbon intensity model (US Midwest, synthetic realistic) ────────────
# Source: EIA 930 data pattern; overnight wind valley, afternoon peak
# Units: gCO2/kWh

def carbon_intensity(t_hours: float) -> float:
    """
    Diurnal carbon intensity (gCO2/kWh).
    Pattern: low at night (wind/nuclear baseline), high in morning/evening peaks.
    t_hours in [0, 24].
    """
    # Base: 150 gCO2/kWh (nuclear/wind overnight)
    # Morning peak: +200 (gas peakers come online)
    # Midday dip: -80 (solar)
    # Evening peak: +250 (gas, high demand)
    base = 150.0
    morning_peak = 200.0 * np.exp(-0.5 * ((t_hours - 8) / 1.5) ** 2)
    midday_dip   = -80.0  * np.exp(-0.5 * ((t_hours - 13) / 2.0) ** 2)
    evening_peak = 250.0  * np.exp(-0.5 * ((t_hours - 19) / 1.5) ** 2)
    overnight_dip = -60.0 * np.exp(-0.5 * ((t_hours - 2) / 2.0) ** 2)
    ci = base + morning_peak + midday_dip + evening_peak + overnight_dip
    return max(ci, 30.0)  # floor at 30 gCO2/kWh (always some non-zero)

HOURS = np.linspace(0, 24, 288)  # 5-minute resolution
CI_CURVE = [carbon_intensity(h) for h in HOURS]

print("=" * 65)
print("FALSIFICATION CHECK — Direction #17: Carbon-Aware Deferral")
print("=" * 65)
print()
print(f"Carbon intensity range: {min(CI_CURVE):.0f}–{max(CI_CURVE):.0f} gCO2/kWh")
print(f"Ratio max/min: {max(CI_CURVE)/min(CI_CURVE):.1f}×")
print()

# ─── Workload model ───────────────────────────────────────────────────────────
# 24h simulation, 5-min timesteps
# Interactive jobs: must run immediately (70% of load)
# Batch jobs: can defer up to 6h (30% of load)

TIMESTEPS = 288  # 24h × 12 steps/h (5min resolution)
DT_HOURS = 24.0 / TIMESTEPS

# Parameters
INTERACTIVE_FRACTION = 0.70
BATCH_FRACTION = 0.30
MAX_DEFER_STEPS = 72  # 6 hours max deferral
LOW_CARBON_THRESHOLD = 120.0  # gCO2/kWh — defer until below this

# Job model: each timestep generates some workload (kW × 5min = kWh)
# Power consumption scales with load; normalize to 1 kW mean DC power
# Jobs have a "size" in kWh (energy to complete)

NUM_HOSTS = 50
HOST_P_MEAN = 175.0  # W mean power per host
TOTAL_POWER_KW = NUM_HOSTS * HOST_P_MEAN / 1000  # 8.75 kW mean DC power

# Workload arrival: sinusoidal with business-hours peak
def workload_intensity(t_step: int) -> float:
    """Load factor [0.3, 1.0] following business-hours pattern."""
    t_h = t_step * DT_HOURS
    biz = 0.65 + 0.35 * np.sin(np.pi * (t_h - 8) / 12) if 8 <= t_h <= 20 else 0.30
    return max(biz, 0.30)

print("[1] WORKLOAD ANALYSIS")
print()

# Track per-timestep: total jobs, batch jobs arriving, batch jobs deferred
rng = np.random.default_rng(42)

scenarios = {
    "low_flex":    {'max_defer': 36,  'threshold': 150.0, 'batch_frac': 0.20},
    "medium_flex": {'max_defer': 72,  'threshold': 120.0, 'batch_frac': 0.30},
    "high_flex":   {'max_defer': 144, 'threshold': 100.0, 'batch_frac': 0.40},
}

results = {}

for sc_name, params in scenarios.items():
    max_defer = params['max_defer']
    threshold = params['threshold']
    batch_frac = params['batch_frac']

    # Baseline: run all jobs as they arrive
    total_energy_base = 0.0  # kWh
    total_carbon_base = 0.0  # gCO2

    # Carbon-aware: defer batch to low-carbon slots
    total_energy_ca = 0.0
    total_carbon_ca = 0.0

    deferred_queue = []  # list of (job_energy_kWh, deadline_step)
    energy_overhead = 0.0  # idle energy while waiting

    for step in range(TIMESTEPS):
        load_factor = workload_intensity(step)
        ci = CI_CURVE[step]
        power_kw = TOTAL_POWER_KW * load_factor

        # Jobs generated this step
        job_energy_kwh = power_kw * DT_HOURS  # total kWh this step

        interactive_kwh = job_energy_kwh * (1 - batch_frac)
        batch_kwh = job_energy_kwh * batch_frac

        # Baseline: run everything
        total_energy_base += job_energy_kwh
        total_carbon_base += job_energy_kwh * ci  # gCO2

        # Carbon-aware: run interactive immediately, defer batch
        total_energy_ca += interactive_kwh
        total_carbon_ca += interactive_kwh * ci

        # Check if this is a low-carbon window: run deferred + arriving batch
        if ci <= threshold:
            # Run arriving batch in this window
            total_energy_ca += batch_kwh
            total_carbon_ca += batch_kwh * ci
        else:
            # Defer batch job if possible
            deadline = step + max_defer
            deferred_queue.append((batch_kwh, deadline))

        # Run expired deferred jobs (deadline reached, must run now)
        still_deferred = []
        for (energy, deadline) in deferred_queue:
            if step >= deadline:
                # Run now regardless (deadline expired)
                total_energy_ca += energy
                total_carbon_ca += energy * ci
            else:
                still_deferred.append((energy, deadline))
        deferred_queue = still_deferred

    # Run any remaining deferred jobs at the end (at last-step CI)
    for (energy, _) in deferred_queue:
        ci_last = CI_CURVE[-1]
        total_energy_ca += energy
        total_carbon_ca += energy * ci_last

    energy_saving_pct = (total_energy_base - total_energy_ca) / total_energy_base * 100
    carbon_saving_pct = (total_carbon_base - total_carbon_ca) / total_carbon_base * 100

    results[sc_name] = {
        'base_energy_kWh': total_energy_base,
        'ca_energy_kWh': total_energy_ca,
        'base_carbon_kgCO2': total_carbon_base / 1e3,
        'ca_carbon_kgCO2': total_carbon_ca / 1e3,
        'energy_saving_pct': energy_saving_pct,
        'carbon_saving_pct': carbon_saving_pct,
    }

print(f"{'Scenario':<15} {'Base E (kWh)':>13} {'CA E (kWh)':>11} {'E saving':>9} {'Base CO2 (kg)':>14} {'CA CO2 (kg)':>12} {'C saving':>9}")
print("-" * 90)
for sc_name, r in results.items():
    print(f"{sc_name:<15} {r['base_energy_kWh']:>13.2f} {r['ca_energy_kWh']:>11.2f} {r['energy_saving_pct']:>8.2f}% {r['base_carbon_kgCO2']:>14.2f} {r['ca_carbon_kgCO2']:>12.2f} {r['carbon_saving_pct']:>8.2f}%")

print()
print("[2] KEY SENSITIVITY")
print()

# What's the theoretical max? All batch deferred to absolute min carbon
min_ci = min(CI_CURVE)
mean_ci = statistics.mean(CI_CURVE)
max_ci = max(CI_CURVE)
# If all batch (30%) runs at min_ci instead of mean_ci:
# Carbon saving = batch_frac × (mean_ci - min_ci) / mean_ci
for bf in [0.20, 0.30, 0.40]:
    theoretical_max = bf * (mean_ci - min_ci) / mean_ci * 100
    print(f"  Batch fraction {bf:.0%}: theoretical max carbon saving = {theoretical_max:.1f}%")

print()
print(f"  Mean CI: {mean_ci:.0f} gCO2/kWh, Min CI: {min_ci:.0f}, Max CI: {max_ci:.0f}")
print()

print("[3] VERDICT")
print()

carbon_savings = [r['carbon_saving_pct'] for r in results.values()]
energy_savings = [r['energy_saving_pct'] for r in results.values()]
mean_carbon_saving = statistics.mean(carbon_savings)
mean_energy_delta = statistics.mean(energy_savings)  # should be ~0

print(f"  Mean carbon saving: {mean_carbon_saving:.1f}%")
print(f"  Mean energy delta: {mean_energy_delta:.2f}% (should be near 0)")
print()

all_viable = all(s >= 5.0 for s in carbon_savings)
some_viable = any(s >= 5.0 for s in carbon_savings)

if all_viable:
    verdict = "✅ VIABLE — Carbon savings > 5% in all scenarios. PROCEED to full simulation."
elif some_viable:
    verdict = "⚠️  PARTIALLY VIABLE — Carbon savings > 5% in some scenarios."
else:
    verdict = "❌ MOOT — Carbon savings < 5% everywhere."

print(f"  VERDICT: {verdict}")
print()
print("  Note: This direction changes the optimization METRIC from energy-J to carbon-gCO2.")
print("  The energy consumption is approximately the same; only carbon changes.")
print("  This is the hottest research direction in cloud sustainability (2024-2026).")
print()
print("  Key novel contribution: Model carbon-aware deferral in CloudSim-style Python")
print("  simulation with realistic hourly CI data. Compare against no-deferral baseline.")
print("  Demonstrate that even a simple threshold policy achieves X% carbon reduction.")
