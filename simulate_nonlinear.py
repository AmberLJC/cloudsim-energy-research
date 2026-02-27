#!/usr/bin/env python3
"""
Extension Experiment: Non-Linear Power & PUE Models
Protocol Amendment PA-002 (logged in LOGBOX.md — 2026-02-27)

MOTIVATION:
  Primary experiment (linear P, linear PUE) produced a null result with a
  clean analytic explanation: for linear P(u) and linear PUE(u), D-PABFD's
  placement criterion is degenerate — ΔE_total_DC is identical for any active
  host. This is proven in analysis.md.

  This extension tests the pre-registered sensitivity parameter (protocol §2,
  §11): ASHRAE piecewise PUE and quadratic power model.

HYPOTHESIS (Extension H1):
  "Under non-linear power models (quadratic) or non-linear PUE (ASHRAE
  piecewise), D-PABFD-NL (with corrected marginal cost criterion) outperforms
  PABFD by > 2% total DC energy."

ANALYTIC PREDICTION:
  With quadratic power P(u) = P_idle + (P_max - P_idle) × u²:
    ΔP(host_h) = (P_max - P_idle) × [(u_h + δ)² − u_h²]
               = (P_max - P_idle) × [2 × u_h × δ + δ²]
  This INCREASES with u_h — unlike linear where ΔP = constant.
  Therefore D-PABFD-NL prefers LOWER utilization hosts (spreading),
  while PABFD prefers HIGHER utilization (consolidation).

  The spreading vs. consolidation trade-off:
    - Spreading: more active hosts → higher PUE overhead (worse)
    - Spreading: each host at lower u → lower quadratic power waste (better)
    - Net benefit depends on workload density and PUE curve steepness.

NEW ALGORITHM: D-PABFD-NL
  Corrected marginal cost criterion:
    cost(h) = [P_quad(u_h + δ) − P_quad(u_h)] × PUE(u_DC_after)
  (Since ΔPUE is identical for all host choices, the only differentiating
  term is the host-specific ΔP under non-linear power.)
  argmin cost(h) = argmin [P_quad(u_h + δ) − P_quad(u_h)]
                 = argmin u_h   (Spread-Fit under quadratic power)

PUE MODELS TESTED:
  1. Linear (original): PUE(u) = 1.8 − 0.6×u
  2. ASHRAE piecewise (non-linear): steeper benefit at low loads
       u < 0.2:  PUE = 1.9
       u < 0.4:  PUE = 1.7
       u < 0.6:  PUE = 1.5
       u < 0.8:  PUE = 1.35
       u ≥ 0.8:  PUE = 1.2

POWER MODELS TESTED:
  1. Linear (original): P(u) = 100 + 150×u
  2. Quadratic:         P(u) = 100 + 150×u²   (SPECpower-inspired)
"""

import numpy as np
import csv
import os
import statistics
import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from collections import defaultdict

# ─── Config ────────────────────────────────────────────────────────────────────

NUM_HOSTS = 10
HOST_CPU_CAP = 1.0
HOST_P_MAX = 250.0
HOST_P_IDLE = 100.0
HOST_RAM_GB = 8.0

SIM_DURATION = 3600
DT = 60
NUM_STEPS = SIM_DURATION // DT

VM_CPU_MU = 0.6
VM_CPU_SIGMA = 0.2
VM_CPU_CLAMP = (0.05, 1.0)
VM_ARRIVAL_RATE = 0.01
VM_LIFETIME_MEAN = 600

SCENARIOS = {
    "low":    0.10,
    "medium": 0.20,
    "high":   0.40,
}

# Experiment matrix: (power_model, pue_model)
EXPERIMENT_CONDITIONS = [
    ("linear",    "linear"),     # Replication: should reproduce null result
    ("quadratic", "linear"),     # Test: quadratic power only
    ("linear",    "ashrae"),     # Test: ASHRAE piecewise PUE only
    ("quadratic", "ashrae"),     # Test: both non-linear
]

ALGORITHMS = ["PABFD", "D_PABFD_NL", "SpreadFit", "Random"]
SEEDS = list(range(10))

RESULTS_DIR = "results"
RESULTS_FILE = "results/nonlinear_results.csv"
SLA_OVERLOAD_THRESHOLD = 0.95


# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class VM:
    vm_id: int
    cpu_demand: float
    ram_gb: float
    arrival_time: float
    lifetime: float
    departure_time: float
    host_id: Optional[int] = None


@dataclass
class Host:
    host_id: int
    cpu_cap: float = HOST_CPU_CAP
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
        return (self.cpu_used + vm.cpu_demand) <= self.cpu_cap * 1.001


# ─── Power & PUE Models ────────────────────────────────────────────────────────

def pue_linear(u: float) -> float:
    """Linear PUE: PUE(u) = 1.8 − 0.6×u"""
    u = max(0.0, min(1.0, u))
    return 1.8 - 0.6 * u


def pue_ashrae(u: float) -> float:
    """
    ASHRAE piecewise PUE (non-linear).
    Based on typical measured datacenter PUE vs load curves.
    Steeper efficiency gain at low loads; plateau at high loads.
    """
    u = max(0.0, min(1.0, u))
    if u < 0.20:
        return 1.90
    elif u < 0.40:
        return 1.70
    elif u < 0.60:
        return 1.50
    elif u < 0.80:
        return 1.35
    else:
        return 1.20


def power_linear(u: float) -> float:
    """Linear power: P(u) = P_idle + (P_max - P_idle) × u"""
    return HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * max(0.0, min(1.0, u))


def power_quadratic(u: float) -> float:
    """Quadratic power: P(u) = P_idle + (P_max - P_idle) × u²
    Models super-linear power growth at high utilization.
    Note: P(0)=P_idle=100W, P(1.0)=P_max=250W (same endpoints as linear).
    Difference: less power at mid-range (u=0.5 → 137.5W vs 175W linear).
    """
    return HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * max(0.0, min(1.0, u)) ** 2


def get_pue_fn(pue_model: str):
    if pue_model == "linear":
        return pue_linear
    elif pue_model == "ashrae":
        return pue_ashrae
    raise ValueError(f"Unknown PUE model: {pue_model}")


def get_power_fn(power_model: str):
    if power_model == "linear":
        return power_linear
    elif power_model == "quadratic":
        return power_quadratic
    raise ValueError(f"Unknown power model: {power_model}")


# ─── Workload Generation (identical to simulate.py) ───────────────────────────

def generate_workload(seed: int, churn_rate: float) -> List[VM]:
    rng = np.random.RandomState(seed)
    vms = []
    vm_id = 0
    current_time = 0.0

    while current_time < SIM_DURATION and vm_id < 500:
        inter_arrival = rng.exponential(1.0 / VM_ARRIVAL_RATE)
        current_time += inter_arrival
        if current_time >= SIM_DURATION:
            break

        cpu = float(np.clip(rng.normal(VM_CPU_MU, VM_CPU_SIGMA), *VM_CPU_CLAMP))
        ram = max(0.5, float(rng.normal(1.0, 0.3)))
        lifetime = float(rng.exponential(VM_LIFETIME_MEAN))
        lifetime *= (1.0 / (1.0 + churn_rate * 2))
        lifetime = max(60.0, lifetime)

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

def place_pabfd(vm: VM, hosts: List[Host], power_fn, pue_fn, rng) -> Optional[int]:
    """PABFD: Best Fit Decreasing (max util after placement).
    Ignores power/PUE models — pure consolidation heuristic."""
    best_host = None
    best_util = -1.0
    for h in hosts:
        if h.can_fit(vm):
            util_after = h.cpu_util + vm.cpu_demand / h.cpu_cap
            if util_after > best_util:
                best_util = util_after
                best_host = h.host_id
    return best_host


def place_dpabfd_nl(vm: VM, hosts: List[Host], power_fn, pue_fn, rng) -> Optional[int]:
    """
    D-PABFD-NL: Corrected marginal total DC energy criterion.

    cost(h) = ΔP(h) × PUE(u_DC_after)
    where ΔP(h) = power_fn(u_h + δ) - power_fn(u_h)

    Since PUE(u_DC_after) is identical for all host choices (u_DC changes by
    same δ/total_cap regardless of which host), we can omit it from argmin.
    This simplifies to: argmin ΔP(h) = argmin marginal_power(h).

    For quadratic P: ΔP(h) increases with u_h → prefer low-utilization hosts.
    For linear P: ΔP(h) is constant → all hosts tied (replicates null result).

    If host was powered off (no VMs), startup cost = P_idle × DT added.
    """
    total_cpu_cap = len(hosts) * HOST_CPU_CAP
    current_total_cpu_used = sum(h.cpu_used for h in hosts)
    dc_util_after = (current_total_cpu_used + vm.cpu_demand) / total_cpu_cap
    pue_after = pue_fn(dc_util_after)

    best_host = None
    best_cost = float('inf')

    for h in hosts:
        if not h.can_fit(vm):
            continue

        u_before = h.cpu_util
        u_after = (h.cpu_used + vm.cpu_demand) / h.cpu_cap
        delta_p = power_fn(u_after) - power_fn(u_before)

        # Startup cost: if host was off, add idle power for one timestep
        if not h.is_active:
            delta_p += HOST_P_IDLE  # W × DT will be applied to energy

        cost = delta_p * pue_after

        if cost < best_cost:
            best_cost = cost
            best_host = h.host_id

    return best_host


def place_spreadfit(vm: VM, hosts: List[Host], power_fn, pue_fn, rng) -> Optional[int]:
    """SpreadFit: Worst Fit Decreasing (min util after placement).
    Explicit spreading policy — baseline for comparison with D-PABFD-NL."""
    best_host = None
    best_util = float('inf')
    for h in hosts:
        if h.can_fit(vm):
            util_after = h.cpu_util + vm.cpu_demand / h.cpu_cap
            if util_after < best_util:
                best_util = util_after
                best_host = h.host_id
    return best_host


def place_random(vm: VM, hosts: List[Host], power_fn, pue_fn, rng) -> Optional[int]:
    candidates = [h.host_id for h in hosts if h.can_fit(vm)]
    if not candidates:
        return None
    return int(rng.choice(candidates))


PLACEMENT_FNS = {
    "PABFD":      place_pabfd,
    "D_PABFD_NL": place_dpabfd_nl,
    "SpreadFit":  place_spreadfit,
    "Random":     place_random,
}


# ─── Simulation Engine ─────────────────────────────────────────────────────────

def simulate(algorithm: str, seed: int, scenario: str, churn_rate: float,
             power_model: str, pue_model: str) -> Dict:
    algo_idx = ALGORITHMS.index(algorithm)
    rng = np.random.RandomState(seed * 31 + algo_idx)
    power_fn = get_power_fn(power_model)
    pue_fn = get_pue_fn(pue_model)
    placement_fn = PLACEMENT_FNS[algorithm]

    hosts = [Host(host_id=i) for i in range(NUM_HOSTS)]
    vms_all = generate_workload(seed, churn_rate)
    vms_all.sort(key=lambda v: v.arrival_time)
    vms_pending = list(vms_all)
    vms_active: List[VM] = []
    vms_rejected = 0

    total_energy_dc = 0.0
    total_compute_energy = 0.0
    total_cooling_energy = 0.0
    sla_violations = 0
    pue_samples = []
    active_host_samples = []
    util_samples = []

    for step in range(NUM_STEPS):
        t = step * DT
        t_next = t + DT

        # Depart
        departed = [v for v in vms_active if v.departure_time <= t_next]
        for vm in departed:
            hosts[vm.host_id].vms.remove(vm)
            vms_active.remove(vm)

        # Arrive
        arriving = [v for v in vms_pending if v.arrival_time < t_next]
        vms_pending = [v for v in vms_pending if v.arrival_time >= t_next]

        for vm in arriving:
            host_id = placement_fn(vm, hosts, power_fn, pue_fn, rng)
            if host_id is not None:
                vm.host_id = host_id
                hosts[host_id].vms.append(vm)
                vms_active.append(vm)
            else:
                vms_rejected += 1

        # Energy accounting
        active_hosts = [h for h in hosts if h.is_active]
        total_cpu_cap = len(hosts) * HOST_CPU_CAP
        total_cpu_used = sum(h.cpu_used for h in active_hosts)
        avg_dc_util = total_cpu_used / total_cpu_cap

        pue = pue_fn(avg_dc_util)
        pue_samples.append(pue)
        active_host_samples.append(len(active_hosts))
        util_samples.append(avg_dc_util)

        compute_energy_step = sum(power_fn(h.cpu_util) * DT for h in active_hosts)
        cooling_energy_step = compute_energy_step * (pue - 1.0)
        dc_energy_step = compute_energy_step * pue

        total_compute_energy += compute_energy_step
        total_cooling_energy += cooling_energy_step
        total_energy_dc += dc_energy_step

        # SLA check
        for h in active_hosts:
            if h.cpu_util > SLA_OVERLOAD_THRESHOLD:
                sla_violations += 1
                break

    return {
        "algorithm": algorithm,
        "seed": seed,
        "scenario": scenario,
        "power_model": power_model,
        "pue_model": pue_model,
        "n_vms": len(vms_all),
        "n_vms_rejected": vms_rejected,
        "total_energy_dc_kj": total_energy_dc / 1000.0,
        "total_compute_energy_kj": total_compute_energy / 1000.0,
        "total_cooling_energy_kj": total_cooling_energy / 1000.0,
        "avg_pue": float(np.mean(pue_samples)),
        "avg_dc_util": float(np.mean(util_samples)),
        "avg_active_hosts": float(np.mean(active_host_samples)),
        "sla_violation_rate": sla_violations / NUM_STEPS,
        "sla_violations_abs": sla_violations,
    }


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    fieldnames = [
        "algorithm", "seed", "scenario", "power_model", "pue_model",
        "n_vms", "n_vms_rejected",
        "total_energy_dc_kj", "total_compute_energy_kj", "total_cooling_energy_kj",
        "avg_pue", "avg_dc_util", "avg_active_hosts",
        "sla_violation_rate", "sla_violations_abs",
    ]

    n_conditions = len(EXPERIMENT_CONDITIONS)
    total_runs = n_conditions * len(ALGORITHMS) * len(SEEDS) * len(SCENARIOS)
    print(f"Non-linear extension: {total_runs} runs "
          f"({n_conditions} conditions × {len(ALGORITHMS)} algos × "
          f"{len(SEEDS)} seeds × {len(SCENARIOS)} scenarios)")

    run_num = 0
    with open(RESULTS_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for power_model, pue_model in EXPERIMENT_CONDITIONS:
            for scenario, churn_rate in SCENARIOS.items():
                for algo in ALGORITHMS:
                    for seed in SEEDS:
                        run_num += 1
                        result = simulate(algo, seed, scenario, churn_rate,
                                          power_model, pue_model)
                        writer.writerow(result)
                        if run_num % 30 == 0:
                            print(f"  [{run_num}/{total_runs}] "
                                  f"{power_model}+{pue_model} {algo} "
                                  f"seed={seed} scen={scenario} → "
                                  f"E_DC={result['total_energy_dc_kj']:.1f} kJ "
                                  f"PUE={result['avg_pue']:.3f}")

    print(f"\nResults saved to {RESULTS_FILE}")
    print("Run analyze_nonlinear.py to compute statistics.")


if __name__ == "__main__":
    main()
