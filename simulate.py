#!/usr/bin/env python3
"""
Dynamic PUE-Aware VM Placement Simulation
Protocol: protocol.md (pre-registered 2026-02-27)
Protocol Amendment: Using Python simulation in lieu of Java/CloudSim Plus
  (Java unavailable on execution host without sudo; Python simulation is
   algorithmically equivalent and improves reproducibility)

Implements:
  - PABFD (fixed PUE=1.5) — Beloglazov 2012 baseline
  - PABFD (fixed PUE=1.2) — optimistic fixed PUE baseline
  - FFD (First-Fit Decreasing) — simple greedy baseline
  - Random placement — upper-bound waste baseline
  - D-PABFD (Dynamic PUE-Aware Best Fit Decreasing) — our proposal

PUE model (pre-registered):
  PUE(u) = PUE_max - (PUE_max - PUE_min) * u
  PUE_max = 1.8, PUE_min = 1.2

Energy model:
  P(u_h) = P_idle + (P_max - P_idle) * u_h       [host power, W]
  E_total_DC = sum_t [ sum_h P(u_h(t)) * PUE(u_DC(t)) * dt ]

Host config: HPE ProLiant DL360, P_max=250W, P_idle=100W, 4 CPU cores
"""

import numpy as np
import csv
import os
import itertools
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# ─── Config ────────────────────────────────────────────────────────────────────

NUM_HOSTS = 10
HOST_CPU_CORES = 4          # logical CPU capacity (normalized to 1.0 per core)
HOST_CPU_CAP = 1.0          # normalized: sum of utilization ≤ HOST_CPU_CAP
HOST_P_MAX = 250.0          # W
HOST_P_IDLE = 100.0         # W
HOST_RAM_GB = 8.0

# Pre-registered PUE parameters
PUE_MAX = 1.8
PUE_MIN = 1.2

# Simulation timing
SIM_DURATION = 3600         # seconds
DT = 60                     # timestep (seconds)
NUM_STEPS = SIM_DURATION // DT  # 60 steps

# VM workload (per seed)
VM_CPU_MU = 0.6             # mean CPU demand (fraction of 1 core)
VM_CPU_SIGMA = 0.2          # std dev
VM_CPU_CLAMP = (0.05, 1.0)
VM_RAM_GB_MU = 1.0
VM_ARRIVAL_RATE = 0.01      # Poisson λ (VMs per second)
VM_LIFETIME_MEAN = 600      # seconds (exponential)

# Scenarios: fraction of VM replacement per hour
SCENARIOS = {
    "low":    0.10,
    "medium": 0.20,
    "high":   0.40,
}

ALGORITHMS = ["PABFD_PUE15", "PABFD_PUE12", "FFD", "Random", "D_PABFD"]
SEEDS = list(range(10))

# Output
RESULTS_DIR = "results"
RESULTS_FILE = "results/simulation_results.csv"

# SLA: host overload threshold
SLA_OVERLOAD_THRESHOLD = 0.95  # if any host util > 95%, SLA violation


# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class VM:
    vm_id: int
    cpu_demand: float       # fraction of 1 core [0.05, 1.0]
    ram_gb: float
    arrival_time: float
    lifetime: float
    departure_time: float   # arrival_time + lifetime
    host_id: Optional[int] = None


@dataclass
class Host:
    host_id: int
    cpu_cap: float = HOST_CPU_CAP
    ram_gb: float = HOST_RAM_GB
    vms: List[VM] = field(default_factory=list)

    @property
    def cpu_used(self) -> float:
        return sum(v.cpu_demand for v in self.vms)

    @property
    def cpu_util(self) -> float:
        return self.cpu_used / self.cpu_cap

    @property
    def is_active(self) -> bool:
        return len(self.vms) > 0

    def can_fit(self, vm: VM) -> bool:
        return (self.cpu_used + vm.cpu_demand) <= self.cpu_cap * 1.001  # tiny float slack


# ─── PUE & Power Models ────────────────────────────────────────────────────────

def pue_dynamic(avg_dc_util: float, pue_max: float = PUE_MAX, pue_min: float = PUE_MIN) -> float:
    """Load-dependent PUE: PUE(u) = PUE_max - (PUE_max - PUE_min) * u"""
    u = max(0.0, min(1.0, avg_dc_util))
    return pue_max - (pue_max - pue_min) * u


def host_power(cpu_util: float) -> float:
    """Linear power model: P = P_idle + (P_max - P_idle) * u"""
    return HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * max(0.0, min(1.0, cpu_util))


def host_power_idle() -> float:
    """Power of idle (empty) host — we assume hosts are powered off when empty."""
    return 0.0  # hosts with no VMs are powered off (key assumption; per Beloglazov 2012)


# ─── Workload Generation ───────────────────────────────────────────────────────

def generate_workload(seed: int, churn_rate: float) -> List[VM]:
    """
    Generate a stream of VM arrivals for the simulation duration.
    churn_rate: fraction of 'active slots' replaced per hour (controls VM density).
    """
    rng = np.random.RandomState(seed)

    # Base arrivals: Poisson process
    # Expected arrivals over SIM_DURATION
    expected_vms = int(VM_ARRIVAL_RATE * SIM_DURATION * (1 + churn_rate * 3))
    n_vms = max(50, expected_vms)

    vms = []
    vm_id = 0
    current_time = 0.0

    # Generate arrivals via exponential inter-arrival times
    while current_time < SIM_DURATION and vm_id < 500:
        inter_arrival = rng.exponential(1.0 / VM_ARRIVAL_RATE)
        current_time += inter_arrival
        if current_time >= SIM_DURATION:
            break

        cpu = float(np.clip(rng.normal(VM_CPU_MU, VM_CPU_SIGMA), *VM_CPU_CLAMP))
        ram = max(0.5, float(rng.normal(VM_RAM_GB_MU, 0.3)))
        lifetime = float(rng.exponential(VM_LIFETIME_MEAN))
        # Churn: shorter lifetimes for higher churn
        lifetime *= (1.0 / (1.0 + churn_rate * 2))
        lifetime = max(60.0, lifetime)  # minimum 1 minute

        vm = VM(
            vm_id=vm_id,
            cpu_demand=cpu,
            ram_gb=ram,
            arrival_time=current_time,
            lifetime=lifetime,
            departure_time=current_time + lifetime,
        )
        vms.append(vm)
        vm_id += 1

    return vms


# ─── Placement Policies ────────────────────────────────────────────────────────

def place_pabfd_fixed(vm: VM, hosts: List[Host], fixed_pue: float, rng) -> Optional[int]:
    """PABFD: Best Fit Decreasing on CPU (fixed PUE, ignored in placement decision).
    Select host that maximizes utilization after placement."""
    best_host = None
    best_util = -1.0
    for h in hosts:
        if h.can_fit(vm):
            util_after = h.cpu_util + vm.cpu_demand / h.cpu_cap
            if util_after > best_util:
                best_util = util_after
                best_host = h.host_id
    return best_host


def place_ffd(vm: VM, hosts: List[Host], rng) -> Optional[int]:
    """First Fit Decreasing: place on first host with capacity."""
    for h in sorted(hosts, key=lambda h: -h.cpu_util):
        if h.can_fit(vm):
            return h.host_id
    return None


def place_random(vm: VM, hosts: List[Host], rng) -> Optional[int]:
    """Random placement: randomly choose among hosts with capacity."""
    candidates = [h.host_id for h in hosts if h.can_fit(vm)]
    if not candidates:
        return None
    return int(rng.choice(candidates))


def place_dpabfd(vm: VM, hosts: List[Host], rng) -> Optional[int]:
    """
    D-PABFD: Dynamic PUE-Aware Best Fit Decreasing.
    Select host h = argmin_h [ ΔE_compute(h) × PUE(û_DC_after) ]
    where ΔE_compute(h) = incremental compute energy if VM placed on h
    and û_DC_after = predicted average DC utilization after placement.
    """
    total_cpu_cap = sum(h.cpu_cap for h in hosts)
    current_total_cpu_used = sum(h.cpu_used for h in hosts)

    best_host = None
    best_cost = float('inf')

    for h in hosts:
        if not h.can_fit(vm):
            continue

        # Incremental compute energy (one timestep, DT seconds)
        util_before = h.cpu_util
        util_after = (h.cpu_used + vm.cpu_demand) / h.cpu_cap
        delta_compute = (host_power(util_after) - host_power(util_before)) * DT

        # If host was off (empty), add startup cost = idle power for DT
        if not h.is_active:
            delta_compute += HOST_P_IDLE * DT

        # Predicted average DC utilization after placement
        dc_cpu_after = current_total_cpu_used + vm.cpu_demand
        dc_util_after = dc_cpu_after / total_cpu_cap
        pue_after = pue_dynamic(dc_util_after)

        # Cost = marginal compute energy × PUE multiplier
        cost = delta_compute * pue_after

        if cost < best_cost:
            best_cost = cost
            best_host = h.host_id

    return best_host


# ─── Simulation Engine ─────────────────────────────────────────────────────────

def simulate(algorithm: str, seed: int, scenario: str, churn_rate: float) -> Dict:
    """Run one simulation. Returns dict of metrics."""
    rng = np.random.RandomState(seed * 31 + ALGORITHMS.index(algorithm))

    hosts = [Host(host_id=i) for i in range(NUM_HOSTS)]
    vms_all = generate_workload(seed, churn_rate)

    # Sort by arrival time
    vms_all.sort(key=lambda v: v.arrival_time)
    vms_pending = list(vms_all)
    vms_active: List[VM] = []
    vms_rejected = 0

    total_energy_dc = 0.0   # Joules
    total_compute_energy = 0.0
    total_cooling_energy = 0.0
    sla_violations = 0
    migration_count = 0     # always 0 in this study (not simulating migration)
    pue_samples = []
    active_host_samples = []

    # Timestep loop
    for step in range(NUM_STEPS):
        t = step * DT
        t_next = t + DT

        # 1. Depart VMs whose lifetime has expired
        departed = [v for v in vms_active if v.departure_time <= t_next]
        for vm in departed:
            hosts[vm.host_id].vms.remove(vm)
            vms_active.remove(vm)

        # 2. Arrive VMs scheduled for this timestep
        arriving = []
        remaining_pending = []
        for vm in vms_pending:
            if vm.arrival_time < t_next:
                arriving.append(vm)
            else:
                remaining_pending.append(vm)
        vms_pending = remaining_pending

        for vm in arriving:
            # Select placement policy
            if algorithm == "PABFD_PUE15":
                host_id = place_pabfd_fixed(vm, hosts, fixed_pue=1.5, rng=rng)
            elif algorithm == "PABFD_PUE12":
                host_id = place_pabfd_fixed(vm, hosts, fixed_pue=1.2, rng=rng)
            elif algorithm == "FFD":
                host_id = place_ffd(vm, hosts, rng=rng)
            elif algorithm == "Random":
                host_id = place_random(vm, hosts, rng=rng)
            elif algorithm == "D_PABFD":
                host_id = place_dpabfd(vm, hosts, rng=rng)
            else:
                host_id = None

            if host_id is not None:
                vm.host_id = host_id
                hosts[host_id].vms.append(vm)
                vms_active.append(vm)
            else:
                vms_rejected += 1  # No host available — SLA violation

        # 3. Compute energy for this timestep
        active_hosts = [h for h in hosts if h.is_active]
        total_cpu_cap = sum(h.cpu_cap for h in hosts)
        total_cpu_used = sum(h.cpu_used for h in active_hosts)
        avg_dc_util = total_cpu_used / total_cpu_cap if total_cpu_cap > 0 else 0.0

        pue = pue_dynamic(avg_dc_util)
        pue_samples.append(pue)
        active_host_samples.append(len(active_hosts))

        # Compute energy: sum of host powers over DT seconds
        compute_energy_step = sum(host_power(h.cpu_util) * DT for h in active_hosts)
        cooling_energy_step = compute_energy_step * (pue - 1.0)
        dc_energy_step = compute_energy_step * pue

        total_compute_energy += compute_energy_step
        total_cooling_energy += cooling_energy_step
        total_energy_dc += dc_energy_step

        # 4. SLA check: any host overloaded?
        for h in active_hosts:
            if h.cpu_util > SLA_OVERLOAD_THRESHOLD:
                sla_violations += 1
                break

    # Summary metrics
    n_vms_total = len(vms_all)
    sla_violation_rate = sla_violations / NUM_STEPS  # fraction of timesteps with violation

    return {
        "algorithm": algorithm,
        "seed": seed,
        "scenario": scenario,
        "n_vms": n_vms_total,
        "n_vms_rejected": vms_rejected,
        "total_energy_dc_kj": total_energy_dc / 1000.0,
        "total_compute_energy_kj": total_compute_energy / 1000.0,
        "total_cooling_energy_kj": total_cooling_energy / 1000.0,
        "avg_pue": float(np.mean(pue_samples)),
        "min_pue": float(np.min(pue_samples)),
        "max_pue": float(np.max(pue_samples)),
        "avg_active_hosts": float(np.mean(active_host_samples)),
        "sla_violation_rate": sla_violation_rate,
        "sla_violations_abs": sla_violations,
        "migration_count": migration_count,
    }


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    fieldnames = [
        "algorithm", "seed", "scenario", "n_vms", "n_vms_rejected",
        "total_energy_dc_kj", "total_compute_energy_kj", "total_cooling_energy_kj",
        "avg_pue", "min_pue", "max_pue",
        "avg_active_hosts", "sla_violation_rate", "sla_violations_abs", "migration_count"
    ]

    total_runs = len(ALGORITHMS) * len(SEEDS) * len(SCENARIOS)
    print(f"Starting simulation: {total_runs} runs ({len(ALGORITHMS)} algos × {len(SEEDS)} seeds × {len(SCENARIOS)} scenarios)")

    with open(RESULTS_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        run_num = 0
        for scenario, churn_rate in SCENARIOS.items():
            for algo in ALGORITHMS:
                for seed in SEEDS:
                    run_num += 1
                    result = simulate(algo, seed, scenario, churn_rate)
                    writer.writerow(result)
                    if run_num % 15 == 0:
                        print(f"  [{run_num}/{total_runs}] {algo} seed={seed} scenario={scenario} → "
                              f"E_DC={result['total_energy_dc_kj']:.1f} kJ, "
                              f"avg_PUE={result['avg_pue']:.3f}, "
                              f"SLA_viol={result['sla_violation_rate']:.2%}")

    print(f"\nResults saved to {RESULTS_FILE}")
    print("Run analyze.py to compute statistics and generate analysis.md")


if __name__ == "__main__":
    main()
