#!/usr/bin/env python3
"""
Full Simulation — Direction #8: VAR-PABFD vs PABFD
Variance-Aware Headroom Reduction

VAR-PABFD: U_HIGH = min(0.95, 0.80 + k*σ_vm)
  where σ_vm is the std-dev of demand for VMs currently on the host,
  measured over the last N timesteps.

Design:
  - Low-variance VMs (predictable demand) → higher ceiling → pack more
  - High-variance VMs → conservative ceiling → protect SLA
  - k: sensitivity coefficient (config sweep)
  - N: lookback window (config sweep)

Metrics:
  - total_energy_J: total energy (host power integral)
  - sla_violations: fraction of steps where host util > 1.0
  - migration_count: number of VM moves during consolidation

Experiment:
  10 seeds × 5 configs × 3 scenarios = 150 runs

Configs:
  0: PABFD baseline (k=0, effectively U_HIGH=0.80)
  1: VAR-PABFD k=1.0, N=5
  2: VAR-PABFD k=2.0, N=5
  3: VAR-PABFD k=1.0, N=10
  4: VAR-PABFD k=2.0, N=10

Stopping rule:
  VIABLE: >5% energy saving vs baseline in 2/3 scenarios
  NULL: <2% in all 3 scenarios

Pre-registered: 2026-02-27
"""

import numpy as np
import statistics
import csv
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Deque
from collections import defaultdict, deque

# ─── Simulation parameters ────────────────────────────────────────────────────
NUM_HOSTS      = 10
HOST_P_MAX     = 250.0
HOST_P_IDLE    = 100.0
HOST_CPU_CAP   = 1.0

SIM_DURATION   = 3600
DT             = 60
NUM_STEPS      = SIM_DURATION // DT

VM_CPU_MU      = 0.6
VM_CPU_SIGMA   = 0.2
VM_CPU_CLAMP   = (0.05, 1.0)
VM_ARRIVAL     = 0.01
VM_LIFETIME    = 600.0

U_HIGH_BASE    = 0.80
U_LOW          = 0.30

CONSOL_INTERVAL = 300  # seconds

SCENARIOS = {
    "low":    0.10,
    "medium": 0.20,
    "high":   0.40,
}

CONFIGS = {
    # (k, N) — k=0 means baseline PABFD
    "PABFD_baseline":   (0.0,  5),
    "VAR_k1_N5":        (1.0,  5),
    "VAR_k2_N5":        (2.0,  5),
    "VAR_k1_N10":       (1.0, 10),
    "VAR_k2_N10":       (2.0, 10),
}

SEEDS = list(range(10))

# ─── Data structures ──────────────────────────────────────────────────────────
@dataclass
class VM:
    vm_id: int
    base_cpu: float          # mean demand
    arrival_time: int
    lifetime: int
    host_id: Optional[int]  = None
    # Per-VM demand history (last N timesteps)
    demand_history: Deque   = field(default_factory=lambda: deque(maxlen=10))

    @property
    def current_demand(self):
        if self.demand_history:
            return self.demand_history[-1]
        return self.base_cpu

    @property
    def demand_variance(self):
        if len(self.demand_history) < 2:
            return 0.0
        return float(np.std(list(self.demand_history)))


@dataclass
class Host:
    host_id: int
    vms: List = field(default_factory=list)
    active: bool = False

    @property
    def util(self):
        return min(sum(v.current_demand for v in self.vms) / HOST_CPU_CAP, 1.0)

    @property
    def free(self):
        return HOST_CPU_CAP - sum(v.current_demand for v in self.vms)

    @property
    def mean_vm_variance(self):
        """Mean variance of VMs on this host."""
        if not self.vms:
            return 0.0
        return statistics.mean(v.demand_variance for v in self.vms)

    def effective_u_high(self, k: float) -> float:
        """VAR-PABFD: U_HIGH = min(0.95, 0.80 + k * mean_variance_of_VMs_on_host)."""
        if k == 0.0:
            return U_HIGH_BASE
        sigma = self.mean_vm_variance
        return min(0.95, U_HIGH_BASE + k * sigma)

    def can_host(self, vm: 'VM', k: float) -> bool:
        u_high = self.effective_u_high(k)
        projected_util = sum(v.current_demand for v in self.vms) / HOST_CPU_CAP + vm.base_cpu
        return projected_util <= u_high


# ─── Placement ────────────────────────────────────────────────────────────────
def place_bfd(vm: VM, hosts: List[Host], k: float) -> Optional[int]:
    """Best-Fit Decreasing with VAR-PABFD headroom."""
    candidates = []
    for h in hosts:
        if h.active and h.can_host(vm, k):
            candidates.append((h.free, h.host_id))
    if candidates:
        candidates.sort(key=lambda x: x[0])  # smallest free → tightest fit
        return candidates[0][1]
    # Try to activate an idle host
    for h in hosts:
        if not h.active:
            h.active = True
            h.vms = []
            return h.host_id
    return None


# ─── Main simulation ──────────────────────────────────────────────────────────
def simulate(seed: int, scenario_churn: float, k: float, lookback_N: int) -> Dict:
    rng = np.random.default_rng(seed)

    # Set lookback window for all VMs
    hosts = [Host(i) for i in range(NUM_HOSTS)]

    # Generate VMs
    all_vms = []
    vm_id = 0
    t = 0.0
    while t < SIM_DURATION:
        dt_next = rng.exponential(1.0 / VM_ARRIVAL)
        t += dt_next
        if t >= SIM_DURATION:
            break
        base_cpu = float(np.clip(rng.normal(VM_CPU_MU, VM_CPU_SIGMA), *VM_CPU_CLAMP))
        life = int(rng.exponential(VM_LIFETIME))
        vm = VM(vm_id, base_cpu, int(t), life,
                demand_history=deque(maxlen=lookback_N))
        all_vms.append(vm)
        vm_id += 1

    # Apply churn: shorten lifetime of a fraction of VMs
    n_churn = int(len(all_vms) * scenario_churn)
    churn_ids = rng.choice(len(all_vms), size=min(n_churn, len(all_vms)), replace=False)
    for idx in churn_ids:
        all_vms[idx].lifetime = int(all_vms[idx].lifetime * rng.uniform(0.1, 0.5))

    all_vms.sort(key=lambda v: v.arrival_time)
    arrival_queue = list(all_vms)

    active_vms: Dict[int, VM] = {}
    total_energy = 0.0
    sla_violations = 0
    total_host_steps = 0
    migration_count = 0
    last_consol = -CONSOL_INTERVAL
    active_host_counts = []

    for step in range(NUM_STEPS):
        t_now = step * DT

        # ── Arrivals
        while arrival_queue and arrival_queue[0].arrival_time <= t_now:
            vm = arrival_queue.pop(0)
            hid = place_bfd(vm, hosts, k)
            if hid is not None:
                vm.host_id = hid
                hosts[hid].vms.append(vm)
                active_vms[vm.vm_id] = vm

        # ── Update demand history (add noise around base)
        for vm in active_vms.values():
            # Small per-step variance: ±15% of base
            noisy = float(np.clip(rng.normal(vm.base_cpu, vm.base_cpu * 0.15), *VM_CPU_CLAMP))
            vm.demand_history.append(noisy)

        # ── Departures
        departed = [v for v in active_vms.values() if v.arrival_time + v.lifetime <= t_now]
        for vm in departed:
            if vm.host_id is not None and 0 <= vm.host_id < NUM_HOSTS:
                hosts[vm.host_id].vms = [v for v in hosts[vm.host_id].vms if v.vm_id != vm.vm_id]
            del active_vms[vm.vm_id]

        # ── Energy accounting + SLA check
        active_count = 0
        for h in hosts:
            if h.active or h.vms:
                h.active = True
                power = HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * h.util
                total_energy += power * DT
                active_count += 1
                total_host_steps += 1
                if h.util > 1.0:
                    sla_violations += 1
            elif not h.vms:
                h.active = False
        active_host_counts.append(active_count)

        # ── Consolidation (every 300s)
        if t_now - last_consol >= CONSOL_INTERVAL:
            last_consol = t_now
            for h in hosts:
                if h.active and h.util < U_LOW and h.vms:
                    vms_to_move = list(h.vms)
                    h.vms = []
                    h.active = False
                    for vm in vms_to_move:
                        other_hosts = [oh for oh in hosts if oh.host_id != h.host_id]
                        hid = place_bfd(vm, other_hosts, k)
                        if hid is not None:
                            vm.host_id = hid
                            hosts[hid].vms.append(vm)
                            migration_count += 1
                        else:
                            # Can't place: put back
                            h.active = True
                            h.vms.append(vm)
                            vm.host_id = h.host_id

        # ── Shut down empty active hosts
        for h in hosts:
            if h.active and not h.vms:
                h.active = False

    sla_viol_rate = sla_violations / max(1, total_host_steps)
    mean_active = statistics.mean(active_host_counts) if active_host_counts else 0

    return {
        'total_energy_J':   total_energy,
        'sla_violations':   sla_violations,
        'sla_viol_rate':    sla_viol_rate,
        'migration_count':  migration_count,
        'mean_active_hosts': mean_active,
        'total_vms':        len(all_vms),
    }


# ─── Experiment runner ────────────────────────────────────────────────────────
def main():
    import os
    out_dir = "results/slo"
    os.makedirs(out_dir, exist_ok=True)

    all_results = []

    print("=" * 75)
    print("VAR-PABFD vs PABFD — Full Simulation (150 runs)")
    print("=" * 75)
    print()

    run_num = 0
    for sc_name, churn in SCENARIOS.items():
        for cfg_name, (k, N) in CONFIGS.items():
            seed_results = []
            for seed in SEEDS:
                res = simulate(seed, churn, k, N)
                row = {
                    'scenario':    sc_name,
                    'config':      cfg_name,
                    'k':           k,
                    'N':           N,
                    'seed':        seed,
                    **res,
                }
                all_results.append(row)
                seed_results.append(res)
                run_num += 1
                if run_num % 15 == 0:
                    print(f"  [{run_num}/150] {sc_name}/{cfg_name} seed {seed} done")

            # Per-config summary
            mean_e = statistics.mean(r['total_energy_J'] for r in seed_results)
            mean_sla = statistics.mean(r['sla_viol_rate'] for r in seed_results)
            mean_mig = statistics.mean(r['migration_count'] for r in seed_results)
            mean_h = statistics.mean(r['mean_active_hosts'] for r in seed_results)
            # print(f"  {sc_name}/{cfg_name}: E={mean_e/1e6:.4f}MJ sla={mean_sla:.4f} mig={mean_mig:.1f} hosts={mean_h:.2f}")

    # ── Write CSV
    csv_path = f"{out_dir}/results.csv"
    fieldnames = list(all_results[0].keys())
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\nCSV written: {csv_path}")

    # ── Analysis
    print()
    print("=" * 75)
    print("RESULTS SUMMARY")
    print("=" * 75)
    print()
    print(f"{'Config':<20} {'Scenario':<10} {'Energy (MJ)':>12} {'vs baseline':>12} {'SLA viol %':>11} {'Migrations':>12} {'Hosts':>7}")
    print("-" * 85)

    # Collect baseline per scenario
    baseline_energy = {}
    for sc_name in SCENARIOS:
        rows = [r for r in all_results if r['scenario'] == sc_name and r['config'] == 'PABFD_baseline']
        baseline_energy[sc_name] = statistics.mean(r['total_energy_J'] for r in rows)

    scenario_savings = {sc: [] for sc in SCENARIOS}

    for cfg_name in CONFIGS:
        for sc_name in SCENARIOS:
            rows = [r for r in all_results if r['scenario'] == sc_name and r['config'] == cfg_name]
            mean_e = statistics.mean(r['total_energy_J'] for r in rows)
            mean_sla = statistics.mean(r['sla_viol_rate'] for r in rows) * 100
            mean_mig = statistics.mean(r['migration_count'] for r in rows)
            mean_h = statistics.mean(r['mean_active_hosts'] for r in rows)
            delta_pct = (baseline_energy[sc_name] - mean_e) / baseline_energy[sc_name] * 100
            if cfg_name != 'PABFD_baseline':
                scenario_savings[sc_name].append(delta_pct)
            print(f"{cfg_name:<20} {sc_name:<10} {mean_e/1e6:>12.4f} {delta_pct:>11.2f}% {mean_sla:>10.4f}% {mean_mig:>12.1f} {mean_h:>7.2f}")
        print()

    # ── Verdict
    print("=" * 75)
    print("STOPPING RULE EVALUATION")
    print("=" * 75)
    print()

    best_savings_per_scenario = {}
    for sc_name, savings_list in scenario_savings.items():
        best = max(savings_list) if savings_list else 0
        best_savings_per_scenario[sc_name] = best
        print(f"  {sc_name}: best VAR-PABFD saving = {best:.2f}%")

    scenarios_above_5pct = sum(1 for v in best_savings_per_scenario.values() if v >= 5.0)
    scenarios_above_2pct = sum(1 for v in best_savings_per_scenario.values() if v >= 2.0)
    mean_best = statistics.mean(best_savings_per_scenario.values())

    print()
    print(f"  Scenarios with ≥5% saving: {scenarios_above_5pct}/3")
    print(f"  Scenarios with ≥2% saving: {scenarios_above_2pct}/3")
    print(f"  Mean best saving: {mean_best:.2f}%")
    print()

    if scenarios_above_5pct >= 2:
        verdict = "✅ VIABLE — Proceed to full lit review + write-up for #8"
    elif scenarios_above_2pct >= 2:
        verdict = "⚠️  BORDERLINE — Modest effect, may not be publishable standalone"
    else:
        verdict = "❌ NULL — Savings < 2% in all scenarios. Pivot to next direction."

    print(f"  VERDICT: {verdict}")
    print()

    # ── SLA impact check
    print("SLA VIOLATION IMPACT:")
    for cfg_name in CONFIGS:
        if cfg_name == 'PABFD_baseline':
            continue
        rows = [r for r in all_results if r['config'] == cfg_name]
        mean_sla = statistics.mean(r['sla_viol_rate'] for r in rows) * 100
        base_rows = [r for r in all_results if r['config'] == 'PABFD_baseline']
        base_sla = statistics.mean(r['sla_viol_rate'] for r in base_rows) * 100
        delta_sla = mean_sla - base_sla
        print(f"  {cfg_name}: SLA viol rate {mean_sla:.4f}% (Δ={delta_sla:+.4f}% vs baseline)")

    print()

    # ── Save summary JSON
    summary = {
        'total_runs': len(all_results),
        'verdict': verdict,
        'mean_best_saving_pct': mean_best,
        'scenarios_above_5pct': scenarios_above_5pct,
        'scenarios_above_2pct': scenarios_above_2pct,
        'best_savings_per_scenario': best_savings_per_scenario,
    }
    with open(f"{out_dir}/summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Summary JSON written: {out_dir}/summary.json")


if __name__ == '__main__':
    main()
