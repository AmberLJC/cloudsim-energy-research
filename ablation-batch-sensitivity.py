"""
Ablation: Batch Fraction × Deadline Slack Sensitivity
=======================================================
Research question: What minimum batch fraction and deadline slack are needed
for carbon deferral to achieve meaningful savings (>5%)?

Current experiments confound these two variables in 3 scenarios:
  - low_flex:    15% batch, 4h defer
  - medium_flex: 30% batch, 6h defer
  - high_flex:   45% batch, 8h defer

This ablation runs a 5×4 factorial design:
  batch_fraction: [0.10, 0.20, 0.30, 0.40, 0.50]
  defer_hours:    [2, 4, 6, 8]
  Total: 20 conditions × 10 seeds = 200 runs

Output:
  - results/carbon/ablation_batch_sensitivity.csv
  - results/carbon/ablation_batch_sensitivity_summary.json
  - Heatmap figure: figures/fig7_batch_sensitivity.png
"""

import numpy as np
import json
import csv
import os

# ── Parameters ───────────────────────────────────────────────────────────────
SEEDS = list(range(10))
N_HOSTS = 20
N_VMS_TARGET = 600
SIM_HOURS = 24
STEPS_PER_HOUR = 2       # 1800-second steps
T_STEP = 1800
N_STEPS = SIM_HOURS * STEPS_PER_HOUR  # 48 steps

HOST_P_IDLE = 100        # Watts at 0% utilization
HOST_P_MAX = 250         # Watts at 100% utilization
HOST_CAPACITY = 1.0      # normalized CPU capacity per host
U_HIGH = 0.80            # PABFD consolidation ceiling
U_LOW = 0.30             # PABFD power-off floor

# Carbon intensity model: US Midwest diurnal profile
CI_BASE = 200.0          # gCO2/kWh mean
CI_SWING = 5.6           # max/min ratio
CI_THRESHOLD = 120.0     # gCO2/kWh — threshold policy trigger

# Factorial design
BATCH_FRACTIONS = [0.10, 0.20, 0.30, 0.40, 0.50]
DEFER_HOURS = [2, 4, 6, 8]

# ── Carbon Intensity Model ────────────────────────────────────────────────────
def carbon_intensity(step: int) -> float:
    """US Midwest diurnal CI: min at 12:00, max at 20:00."""
    hour = (step * T_STEP / 3600) % 24
    angle = 2 * np.pi * (hour - 12) / 24
    ci_normalized = 0.5 - 0.5 * np.cos(angle)
    
    # Add evening peak
    angle_evening = 2 * np.pi * (hour - 20) / 24
    evening = 0.10 * max(0, np.cos(angle_evening))
    ci_normalized += evening
    
    min_ci = CI_BASE / np.sqrt(CI_SWING)
    max_ci = CI_BASE * np.sqrt(CI_SWING)
    return float(min_ci + ci_normalized * (max_ci - min_ci))

# Precompute CI profile for 48 steps (24h)
CI_PROFILE = np.array([carbon_intensity(s) for s in range(N_STEPS)])

def host_power(utilization: float) -> float:
    """Linear power model: P(u) = P_idle + (P_max - P_idle) * u"""
    u = np.clip(utilization, 0.0, 1.0)
    return HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * u

# ── Job Generator ─────────────────────────────────────────────────────────────
def generate_jobs(rng, n_vms_target: int, batch_fraction: float, defer_hours: float):
    """Generate a mix of interactive + batch jobs.
    
    Each job: (arrival_step, duration_steps, cpu_demand, is_batch, deadline_step)
    """
    jobs = []
    for i in range(n_vms_target):
        # Arrival: diurnal Poisson (heavier during business hours 8-18)
        arrival_hour = rng.choice(np.arange(24), p=_diurnal_arrival_prob())
        arrival_step = int(arrival_hour * STEPS_PER_HOUR)
        arrival_step += rng.integers(0, STEPS_PER_HOUR)
        arrival_step = min(arrival_step, N_STEPS - 1)
        
        # Duration: 1-4 steps (30 min to 2 hours)
        duration_steps = rng.integers(1, 5)
        
        # CPU demand: 0.05-0.30 per VM (normalized)
        cpu_demand = rng.uniform(0.05, 0.30)
        
        # Batch vs interactive
        is_batch = rng.random() < batch_fraction
        
        # Deadline
        if is_batch:
            deadline_steps = int(defer_hours * STEPS_PER_HOUR)
            deadline = min(arrival_step + deadline_steps, N_STEPS - 1)
        else:
            deadline = min(arrival_step + duration_steps + 1, N_STEPS - 1)
        
        jobs.append({
            'id': i,
            'arrival': arrival_step,
            'duration': duration_steps,
            'cpu': cpu_demand,
            'is_batch': is_batch,
            'deadline': deadline
        })
    
    return sorted(jobs, key=lambda j: j['arrival'])

def _diurnal_arrival_prob():
    """Diurnal Poisson weights: higher during business hours."""
    hours = np.arange(24)
    weights = np.ones(24) * 0.5
    # Business hours boost
    weights[8:18] += 1.0
    weights[9:17] += 0.5
    return weights / weights.sum()

# ── Simulator ─────────────────────────────────────────────────────────────────
def simulate(jobs, batch_fraction, defer_hours, rng_seed: int):
    """Simulate PABFD + threshold carbon deferral.
    
    Returns dict with energy_kwh, carbon_gco2, n_sla_violations, mean_wait_h.
    """
    # Build arrival queues
    arrivals = {}  # step -> list of jobs
    for j in jobs:
        arrivals.setdefault(j['arrival'], []).append(j)
    
    batch_queue = []   # (release_step, job) — deferred batch jobs
    active_vms = []    # currently running VMs: (job, remaining_steps, host_idx)
    host_utils = np.zeros(N_HOSTS)   # current utilization per host
    host_active = np.zeros(N_HOSTS, dtype=bool)
    
    total_energy_j = 0.0
    total_carbon_gco2 = 0.0
    n_placed = 0
    n_sla_violations = 0
    wait_times = []
    
    for step in range(N_STEPS):
        ci = CI_PROFILE[step]
        
        # ── Release queued batch jobs if CI is low ──────────────────────────
        still_queued = []
        for (release_step, job) in batch_queue:
            if ci <= CI_THRESHOLD or step >= job['deadline']:
                if step > job['arrival']:
                    wait_times.append((step - job['arrival']) * T_STEP / 3600.0)
                _place_vm(job, host_utils, host_active, active_vms)
                n_placed += 1
                if step > job['deadline']:
                    n_sla_violations += 1
            else:
                still_queued.append((release_step, job))
        batch_queue = still_queued
        
        # ── Admit new arrivals ──────────────────────────────────────────────
        for job in arrivals.get(step, []):
            if job['is_batch'] and ci > CI_THRESHOLD:
                # Defer: queue until CI drops
                batch_queue.append((step, job))
            else:
                _place_vm(job, host_utils, host_active, active_vms)
                n_placed += 1
        
        # ── Advance running VMs ─────────────────────────────────────────────
        still_active = []
        for (job, remaining, host_idx) in active_vms:
            if remaining <= 1:
                host_utils[host_idx] = max(0.0, host_utils[host_idx] - job['cpu'])
            else:
                still_active.append((job, remaining - 1, host_idx))
        active_vms = still_active
        
        # ── PABFD consolidation: power off underutilized hosts ──────────────
        for h in range(N_HOSTS):
            if host_active[h] and host_utils[h] < U_LOW:
                # Check if any VMs running on this host
                vms_on_host = [v for v in active_vms if v[2] == h]
                if len(vms_on_host) == 0:
                    host_active[h] = False
                    host_utils[h] = 0.0
        
        # ── Compute step energy and carbon ──────────────────────────────────
        step_energy_j = 0.0
        for h in range(N_HOSTS):
            if host_active[h]:
                p_watts = host_power(host_utils[h])
                step_energy_j += p_watts * T_STEP  # Joules
        
        total_energy_j += step_energy_j
        # Carbon: energy in kWh × CI in gCO2/kWh
        step_energy_kwh = step_energy_j / 3_600_000.0
        total_carbon_gco2 += step_energy_kwh * ci
    
    # Force-place remaining queued jobs (SLA violation)
    for (_, job) in batch_queue:
        n_sla_violations += 1
    
    energy_kwh = total_energy_j / 3_600_000.0
    mean_wait_h = float(np.mean(wait_times)) if wait_times else 0.0
    
    return {
        'energy_kwh': energy_kwh,
        'carbon_gco2': total_carbon_gco2,
        'n_sla_violations': n_sla_violations,
        'mean_wait_h': mean_wait_h,
        'n_placed': n_placed,
        'n_queued_remaining': len(batch_queue),
    }

def _place_vm(job, host_utils, host_active, active_vms):
    """PABFD placement: best-fit decreasing (highest util first)."""
    # Find feasible hosts (active, can accept job without exceeding U_HIGH)
    candidates = []
    for h in range(N_HOSTS):
        if host_active[h] and host_utils[h] + job['cpu'] <= U_HIGH:
            candidates.append((host_utils[h], h))
    
    if candidates:
        # Best-fit: pick highest utilization host
        candidates.sort(reverse=True)
        best_h = candidates[0][1]
    else:
        # Activate a new host
        inactive = [h for h in range(N_HOSTS) if not host_active[h]]
        if inactive:
            best_h = inactive[0]
            host_active[best_h] = True
        else:
            # All hosts full — place on least-loaded anyway (overflow)
            best_h = int(np.argmin(host_utils))
    
    host_utils[best_h] += job['cpu']
    active_vms.append((job, job['duration'], best_h))

# ── Baseline (no deferral) ────────────────────────────────────────────────────
def simulate_baseline(jobs, rng_seed: int):
    """PABFD with no carbon-aware deferral (all jobs admitted immediately)."""
    # Force all jobs to be interactive (no deferral)
    no_defer_jobs = []
    for j in jobs:
        jj = dict(j)
        jj['is_batch'] = False  # No deferral
        no_defer_jobs.append(jj)
    return simulate(no_defer_jobs, batch_fraction=0.0, defer_hours=0, rng_seed=rng_seed)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs('results/carbon', exist_ok=True)
    
    rows = []
    summary = {}
    
    total_conditions = len(BATCH_FRACTIONS) * len(DEFER_HOURS)
    run_count = 0
    
    print(f"Running {total_conditions} conditions × {len(SEEDS)} seeds = {total_conditions * len(SEEDS)} runs")
    print()
    
    for batch_frac in BATCH_FRACTIONS:
        for defer_h in DEFER_HOURS:
            condition_key = f"bf{int(batch_frac*100)}_dh{defer_h}"
            
            carbon_savings = []
            energy_deltas = []
            sla_violations = []
            
            for seed in SEEDS:
                rng = np.random.default_rng(seed)
                
                # Generate jobs with this batch fraction and defer hours
                jobs = generate_jobs(rng, N_VMS_TARGET, batch_frac, defer_h)
                
                # Baseline: no deferral
                rng_base = np.random.default_rng(seed)
                jobs_base = generate_jobs(rng_base, N_VMS_TARGET, batch_frac, defer_h)
                base = simulate_baseline(jobs_base, seed)
                
                # Treatment: threshold policy
                rng_treat = np.random.default_rng(seed)
                jobs_treat = generate_jobs(rng_treat, N_VMS_TARGET, batch_frac, defer_h)
                treat = simulate(jobs_treat, batch_frac, defer_h, seed)
                
                if base['carbon_gco2'] > 0:
                    csav = (base['carbon_gco2'] - treat['carbon_gco2']) / base['carbon_gco2'] * 100
                else:
                    csav = 0.0
                
                if base['energy_kwh'] > 0:
                    edelt = (treat['energy_kwh'] - base['energy_kwh']) / base['energy_kwh'] * 100
                else:
                    edelt = 0.0
                
                carbon_savings.append(csav)
                energy_deltas.append(edelt)
                sla_violations.append(treat['n_sla_violations'])
                
                rows.append({
                    'batch_fraction': batch_frac,
                    'defer_hours': defer_h,
                    'seed': seed,
                    'carbon_saving_pct': round(csav, 4),
                    'energy_delta_pct': round(edelt, 4),
                    'n_sla_violations': treat['n_sla_violations'],
                    'mean_wait_h': round(treat['mean_wait_h'], 3),
                })
            
            mean_csav = float(np.mean(carbon_savings))
            std_csav = float(np.std(carbon_savings))
            mean_edelt = float(np.mean(energy_deltas))
            mean_sla = float(np.mean(sla_violations))
            
            summary[condition_key] = {
                'batch_fraction': batch_frac,
                'defer_hours': defer_h,
                'carbon_saving_mean': round(mean_csav, 3),
                'carbon_saving_std': round(std_csav, 3),
                'energy_delta_mean': round(mean_edelt, 4),
                'sla_violations_mean': round(mean_sla, 1),
            }
            
            run_count += 1
            viable = "[OK]" if mean_csav >= 5.0 else ("[~]" if mean_csav >= 2.0 else "[x]")
            print(f"  [{run_count:2d}/{total_conditions}] batch={batch_frac:.0%}, defer={defer_h}h: "
                  f"carbon={mean_csav:+.2f}% ±{std_csav:.2f}% {viable}, "
                  f"energy={mean_edelt:+.4f}%")
    
    # Write CSV
    csv_path = 'results/carbon/ablation_batch_sensitivity.csv'
    fieldnames = ['batch_fraction', 'defer_hours', 'seed', 'carbon_saving_pct',
                  'energy_delta_pct', 'n_sla_violations', 'mean_wait_h']
    with open(csv_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    
    # Write JSON summary
    json_path = 'results/carbon/ablation_batch_sensitivity_summary.json'
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nResults saved to {csv_path}")
    print(f"Summary saved to {json_path}")
    
    # ── Print key findings ────────────────────────────────────────────────────
    print("\n" + "="*65)
    print("KEY FINDINGS: Carbon Saving Heatmap (mean % across 10 seeds)")
    print("="*65)
    print(f"{'batch%':>8}", end="")
    for dh in DEFER_HOURS:
        print(f"  {dh}h defer", end="")
    print()
    print("-" * 65)
    for bf in BATCH_FRACTIONS:
        print(f"{bf:>8.0%}", end="")
        for dh in DEFER_HOURS:
            key = f"bf{int(bf*100)}_dh{dh}"
            v = summary[key]['carbon_saving_mean']
            marker = "✅" if v >= 5.0 else ("⚠" if v >= 2.0 else "❌")
            print(f"  {v:5.2f}%{marker}", end="")
        print()
    
    print("\nViability legend: ✅ ≥5% (viable)  ⚠ 2-5% (borderline)  ❌ <2% (null)")
    
    # Find minimum viable conditions
    viable = [(bf, dh) for bf in BATCH_FRACTIONS for dh in DEFER_HOURS
              if summary[f"bf{int(bf*100)}_dh{dh}"]['carbon_saving_mean'] >= 5.0]
    print(f"\nMinimum viable: batch≥{min(bf for bf,_ in viable):.0%}, defer≥{min(dh for _,dh in viable)}h "
          f"(if individually sufficient)")
    
    return summary

if __name__ == '__main__':
    main()
