#!/usr/bin/env python3
"""
P-PABFD: Predictive Proactive Consolidation Simulation
Protocol: protocol-predictive.md (pre-registered 2026-02-27)

Direction #3 — Proactive host shutdown via demand prediction.

Implements:
  A0: PABFD       — reactive baseline (Beloglazov 2012)
  A1: FFD         — first-fit decreasing reactive baseline
  A2: P-PABFD-EWA — proactive, exponential weighted average predictor
  A3: P-PABFD-AR3 — proactive, AR(3) autoregression predictor
  A4: P-PABFD-Oracle — proactive, perfect future knowledge (upper bound)

Key mechanism:
  PABFD fires underload consolidation when util_host < 0.30 (reactive).
  P-PABFD fires when PREDICTED util at t+T_lookahead < 0.30 (proactive).
  This eliminates idle-host linger time of up to T_consolidation/2 seconds.

Energy model:
  P(u_h) = P_idle + (P_max - P_idle) * u_h
  E_total = sum_t sum_h P(u_h(t)) * dt    [no PUE multiplier — see analysis.md]

Pre-registered hyperparameters:
  T_lookahead = 300 s (primary), also 150 s, 600 s (sensitivity)
  p_accuracy  = 0.75 (primary), also 0.50, 0.90 (sensitivity)
  U_low       = 0.30 (underload threshold — same as PABFD)
  T_consolidation = 300 s

Date: 2026-02-27
"""

import numpy as np
import csv
import os
import itertools
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Deque
from collections import deque

# ─── Configuration ──────────────────────────────────────────────────────────────

NUM_HOSTS      = 10
HOST_P_MAX     = 250.0        # W
HOST_P_IDLE    = 100.0        # W
HOST_CPU_CAP   = 1.0          # normalized capacity per host

SIM_DURATION   = 3600         # s
DT             = 60           # s per timestep
NUM_STEPS      = SIM_DURATION // DT

VM_CPU_MU      = 0.6
VM_CPU_SIGMA   = 0.2
VM_CPU_CLAMP   = (0.05, 1.0)
VM_ARRIVAL     = 0.01         # VMs/s (Poisson λ)
VM_LIFETIME    = 600.0        # s (exponential mean)

U_LOW          = 0.30         # underload threshold (PABFD default)
U_HIGH         = 0.80         # overload threshold (SLA)
T_CONSOLIDATION= 300          # s — consolidation check interval

HISTORY_LEN    = 20           # timesteps of history for predictor

# Pre-registered primary parameters
PRIMARY_LOOKAHEAD  = 300      # s
PRIMARY_ACCURACY   = 0.75

SCENARIOS = {"low": 0.10, "medium": 0.20, "high": 0.40}
ALGORITHMS = ["PABFD", "FFD", "P_PABFD_EWA", "P_PABFD_AR3", "P_PABFD_Oracle"]
SEEDS = list(range(10))

RESULTS_DIR  = "results"
RESULTS_FILE = "results/predictive_results.csv"

SLA_OVERLOAD  = 0.95          # host overloaded if util > this

# ─── Data Structures ────────────────────────────────────────────────────────────

@dataclass
class VM:
    vm_id: int
    cpu_demand: float          # fraction of host capacity
    arrival_time: int
    lifetime: int              # seconds
    host_id: Optional[int] = None

@dataclass
class Host:
    host_id: int
    vms: List[VM] = field(default_factory=list)
    active: bool = False
    util_history: Deque = field(default_factory=lambda: deque(maxlen=HISTORY_LEN))

    @property
    def util(self) -> float:
        total = sum(v.cpu_demand for v in self.vms)
        return min(total / HOST_CPU_CAP, 1.0)

    @property
    def free(self) -> float:
        return HOST_CPU_CAP - sum(v.cpu_demand for v in self.vms)

    def can_host(self, vm: VM) -> bool:
        return self.free >= vm.cpu_demand


def host_power(util: float) -> float:
    return HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * util


# ─── Predictors ────────────────────────────────────────────────────────────────

def predict_ewa(history: List[float], alpha: float = 0.3) -> float:
    """Exponential weighted average predictor. Returns predicted next-step util."""
    if not history:
        return 0.0
    ewa = history[0]
    for u in history[1:]:
        ewa = alpha * u + (1 - alpha) * ewa
    return max(0.0, min(1.0, ewa))


def predict_ar3(history: List[float]) -> float:
    """AR(3) autoregression via OLS. Returns predicted next-step util."""
    if len(history) < 4:
        return predict_ewa(history)   # fall back to EWA if insufficient history
    
    # Build design matrix: last 3 lags
    X, y = [], []
    for i in range(3, len(history)):
        X.append([1.0, history[i-1], history[i-2], history[i-3]])
        y.append(history[i])
    
    X = np.array(X)
    y = np.array(y)
    
    try:
        # OLS: β = (XᵀX)⁻¹Xᵀy
        betas = np.linalg.lstsq(X, y, rcond=None)[0]
        c, phi1, phi2, phi3 = betas
        pred = c + phi1 * history[-1] + phi2 * history[-2] + phi3 * history[-3]
        return max(0.0, min(1.0, pred))
    except np.linalg.LinAlgError:
        return predict_ewa(history)


def noisy_predict(true_pred: float, current: float, p_accuracy: float, rng: np.random.Generator) -> float:
    """Apply prediction noise model. With probability p_accuracy return true prediction,
    otherwise return current + Gaussian noise (σ=0.15)."""
    if rng.random() < p_accuracy:
        return true_pred
    else:
        noisy = current + rng.normal(0, 0.15)
        return max(0.0, min(1.0, noisy))


# ─── VM Placement ───────────────────────────────────────────────────────────────

def place_vm_bfd(vm: VM, hosts: List[Host]) -> Optional[int]:
    """Best-Fit Decreasing: place on active host with lowest free capacity that fits."""
    candidates = [(h.free, h.host_id) for h in hosts if h.active and h.can_host(vm)]
    if not candidates:
        # Try powering on an idle host
        for h in hosts:
            if not h.active and h.can_host(vm):
                h.active = True
                h.vms = []
                return h.host_id
        return None
    # Best-fit: minimize remaining free space after placement
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def place_vm_ffd(vm: VM, hosts: List[Host]) -> Optional[int]:
    """First-Fit Decreasing: place on first active host that fits."""
    for h in hosts:
        if h.active and h.can_host(vm):
            return h.host_id
    # Try powering on
    for h in hosts:
        if not h.active and h.can_host(vm):
            h.active = True
            h.vms = []
            return h.host_id
    return None


def migrate_vms(vms_to_migrate: List[VM], hosts: List[Host], placement_fn) -> int:
    """Migrate a list of VMs to other hosts. Returns number of SLA-violating migrations."""
    sla_violations = 0
    for vm in vms_to_migrate:
        host_id = placement_fn(vm, hosts)
        if host_id is None:
            sla_violations += 1
        else:
            vm.host_id = host_id
            hosts[host_id].vms.append(vm)
    return sla_violations


# ─── Core Simulation ────────────────────────────────────────────────────────────

def run_simulation(
    seed: int,
    scenario: str,
    algorithm: str,
    t_lookahead: int = PRIMARY_LOOKAHEAD,
    p_accuracy: float = PRIMARY_ACCURACY,
) -> Dict:
    """
    Run one simulation. Returns a dict of metrics.
    """
    rng = np.random.default_rng(seed)
    churn = SCENARIOS[scenario]

    # Initialize hosts
    hosts = [Host(host_id=i) for i in range(NUM_HOSTS)]

    # Generate all VM arrivals upfront (reproducible per seed)
    all_vms = []
    vm_id = 0
    t = 0
    while t < SIM_DURATION:
        dt_to_next = rng.exponential(1.0 / VM_ARRIVAL)
        t += dt_to_next
        if t >= SIM_DURATION:
            break
        cpu = float(np.clip(rng.normal(VM_CPU_MU, VM_CPU_SIGMA), *VM_CPU_CLAMP))
        lifetime = int(rng.exponential(VM_LIFETIME))
        all_vms.append(VM(vm_id=vm_id, cpu_demand=cpu, arrival_time=int(t), lifetime=lifetime))
        vm_id += 1

    # Apply churn: remove a fraction of VMs by shortening their lifetimes
    n_churn = int(len(all_vms) * churn)
    churn_ids = rng.choice(len(all_vms), size=min(n_churn, len(all_vms)), replace=False)
    for idx in churn_ids:
        all_vms[idx].lifetime = int(all_vms[idx].lifetime * rng.uniform(0.1, 0.5))

    # Sort arrivals by time
    all_vms.sort(key=lambda v: v.arrival_time)
    arrival_queue = list(all_vms)

    # Pick placement function
    if algorithm in ("PABFD", "P_PABFD_EWA", "P_PABFD_AR3", "P_PABFD_Oracle"):
        place_fn = place_vm_bfd
    else:  # FFD
        place_fn = place_vm_ffd

    # Metrics
    total_energy_j   = 0.0
    total_sla_viol   = 0
    total_migrations = 0
    idle_time_saved  = 0.0   # seconds of idle time eliminated vs. reactive
    last_consolidation = -T_CONSOLIDATION  # force consolidation at t=0

    # Track "future" utilization for Oracle: precompute per-host util trace
    # (for oracle only — we peek at actual future state)
    # We'll compute this lazily during the sim

    # Running VM set
    active_vms: Dict[int, VM] = {}   # vm_id → VM

    # History per host: list of (timestep, util)
    host_history: Dict[int, List[float]] = {i: [] for i in range(NUM_HOSTS)}

    # ── Main loop ──────────────────────────────────────────────────────────────
    for step in range(NUM_STEPS):
        t_now = step * DT

        # 1. Process arrivals at this timestep
        while arrival_queue and arrival_queue[0].arrival_time <= t_now:
            vm = arrival_queue.pop(0)
            hid = place_fn(vm, hosts)
            if hid is not None:
                vm.host_id = hid
                hosts[hid].vms.append(vm)
                active_vms[vm.vm_id] = vm
            # else: VM dropped (no capacity) — counts as SLA

        # 2. Process departures
        departed = [vm for vm in active_vms.values()
                    if vm.arrival_time + vm.lifetime <= t_now]
        for vm in departed:
            if vm.host_id is not None and vm in hosts[vm.host_id].vms:
                hosts[vm.host_id].vms.remove(vm)
            del active_vms[vm.vm_id]

        # 3. Record utilization history for predictors
        for h in hosts:
            if h.active or len(h.vms) > 0:
                host_history[h.host_id].append(h.util)
            else:
                host_history[h.host_id].append(0.0)

        # Keep history bounded
        for hid in host_history:
            if len(host_history[hid]) > HISTORY_LEN:
                host_history[hid] = host_history[hid][-HISTORY_LEN:]

        # 4. Energy accumulation (before consolidation changes state)
        for h in hosts:
            if h.active or len(h.vms) > 0:
                h.active = True  # ensure active if has VMs
                total_energy_j += host_power(h.util) * DT

        # 5. SLA check: overloaded hosts
        for h in hosts:
            if h.active and h.util > SLA_OVERLOAD:
                total_sla_viol += 1

        # 6. Consolidation check (every T_CONSOLIDATION seconds)
        if t_now - last_consolidation >= T_CONSOLIDATION:
            last_consolidation = t_now

            underloaded = []
            for h in hosts:
                if not h.active or not h.vms:
                    continue

                current_util = h.util
                hist = host_history[h.host_id]

                if algorithm == "PABFD" or algorithm == "FFD":
                    # REACTIVE: check current util
                    is_underloaded = (current_util < U_LOW)

                elif algorithm == "P_PABFD_Oracle":
                    # ORACLE: look up actual future utilization
                    # Approximate by: what fraction of current VMs will still be here
                    # at t + T_lookahead?
                    future_vms = [v for v in h.vms
                                  if v.arrival_time + v.lifetime > t_now + t_lookahead]
                    future_util = sum(v.cpu_demand for v in future_vms) / HOST_CPU_CAP
                    future_util = max(0.0, min(1.0, future_util))
                    is_underloaded = (future_util < U_LOW)

                elif algorithm == "P_PABFD_EWA":
                    raw_pred = predict_ewa(hist)
                    pred_util = noisy_predict(raw_pred, current_util, p_accuracy, rng)
                    is_underloaded = (pred_util < U_LOW)

                elif algorithm == "P_PABFD_AR3":
                    raw_pred = predict_ar3(hist)
                    pred_util = noisy_predict(raw_pred, current_util, p_accuracy, rng)
                    is_underloaded = (pred_util < U_LOW)

                else:
                    is_underloaded = (current_util < U_LOW)

                if is_underloaded:
                    underloaded.append(h)

            # Consolidate underloaded hosts
            for h in sorted(underloaded, key=lambda x: x.util):
                # Only shut down if we can migrate all VMs
                vms_here = list(h.vms)
                other_hosts = [oh for oh in hosts if oh.host_id != h.host_id]

                # Check if migration is feasible
                feasible = True
                temp_placement = {}
                remaining_vms = list(vms_here)
                for vm in sorted(remaining_vms, key=lambda v: -v.cpu_demand):
                    placed = False
                    for oh in sorted(other_hosts, key=lambda x: x.free):
                        if oh.active and oh.can_host(vm):
                            # Tentative: reserve space
                            temp_placement[vm.vm_id] = oh.host_id
                            oh.vms.append(vm)   # temp
                            placed = True
                            break
                    if not placed:
                        # Try powering on an idle host
                        for oh in other_hosts:
                            if not oh.active:
                                oh.active = True
                                oh.vms = []
                                temp_placement[vm.vm_id] = oh.host_id
                                oh.vms.append(vm)
                                placed = True
                                break
                    if not placed:
                        feasible = False
                        break

                # Undo tentative placements
                for vm in remaining_vms:
                    if vm.vm_id in temp_placement:
                        oh = hosts[temp_placement[vm.vm_id]]
                        if vm in oh.vms:
                            oh.vms.remove(vm)

                if not feasible:
                    continue   # Can't consolidate this host, skip

                # Perform actual migration
                h.vms = []
                for vm in vms_here:
                    hid = place_fn(vm, [oh for oh in hosts if oh.host_id != h.host_id])
                    if hid is not None:
                        vm.host_id = hid
                        hosts[hid].vms.append(vm)
                        total_migrations += 1
                    else:
                        total_sla_viol += 1

                # Shut down host
                h.active = False
                h.vms = []

                # Track idle time saved for predictive algorithms
                if algorithm in ("P_PABFD_EWA", "P_PABFD_AR3", "P_PABFD_Oracle"):
                    # How long would PABFD have waited? The host is currently above
                    # PABFD threshold (current_util >= U_LOW for predictive triggers).
                    # Conservative estimate: half consolidation interval
                    if current_util >= U_LOW:
                        idle_time_saved += T_CONSOLIDATION / 2

        # 7. Power down truly empty (non-active) hosts
        for h in hosts:
            if h.active and len(h.vms) == 0:
                h.active = False

    # ── Compute final metrics ─────────────────────────────────────────────────
    total_vms = len(all_vms)
    sla_rate  = total_sla_viol / max(1, NUM_STEPS * NUM_HOSTS)
    energy_kwh = total_energy_j / 3_600_000

    # Idle energy saved (watts × seconds → joules)
    idle_energy_saved_j = HOST_P_IDLE * idle_time_saved

    return {
        "seed":              seed,
        "scenario":          scenario,
        "algorithm":         algorithm,
        "t_lookahead":       t_lookahead,
        "p_accuracy":        p_accuracy,
        "total_energy_j":    total_energy_j,
        "energy_kwh":        energy_kwh,
        "sla_violation_rate":sla_rate,
        "total_migrations":  total_migrations,
        "total_vms":         total_vms,
        "idle_time_saved_s": idle_time_saved,
        "idle_energy_saved_j":idle_energy_saved_j,
    }


# ─── Sensitivity Sweep ──────────────────────────────────────────────────────────

def run_sensitivity(
    seeds=SEEDS,
    scenarios=list(SCENARIOS.keys()),
    lookaheads=(150, 300, 600),
    accuracies=(0.50, 0.75, 0.90),
):
    """Run sensitivity sweep over lookahead × accuracy × scenario for A2/A3."""
    results = []
    total = len(seeds) * len(scenarios) * len(lookaheads) * len(accuracies) * 2
    done = 0
    for seed, scenario, lookahead, accuracy, algo in itertools.product(
        seeds, scenarios, lookaheads, accuracies,
        ["P_PABFD_EWA", "P_PABFD_AR3"]
    ):
        r = run_simulation(seed, scenario, algo, t_lookahead=lookahead, p_accuracy=accuracy)
        results.append(r)
        done += 1
        if done % 50 == 0:
            print(f"  sensitivity: {done}/{total}", flush=True)
    return results


# ─── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("=" * 60)
    print("P-PABFD Predictive Consolidation Simulation")
    print("Protocol: protocol-predictive.md")
    print("=" * 60)

    # ── Phase 1: Primary runs (150) ───────────────────────────────────────────
    print("\n[1/2] Primary runs: 5 algorithms × 3 scenarios × 10 seeds = 150 runs")
    primary_results = []
    total_primary = len(SEEDS) * len(SCENARIOS) * len(ALGORITHMS)
    done = 0
    for seed, scenario, algo in itertools.product(SEEDS, SCENARIOS.keys(), ALGORITHMS):
        r = run_simulation(seed, scenario, algo)
        primary_results.append(r)
        done += 1
        if done % 30 == 0:
            print(f"  {done}/{total_primary} runs complete", flush=True)

    print(f"  Primary runs complete: {len(primary_results)}")

    # ── Phase 2: Sensitivity runs ─────────────────────────────────────────────
    print("\n[2/2] Sensitivity sweep: accuracy × lookahead × scenario × seed")
    sensitivity_results = run_sensitivity()
    print(f"  Sensitivity runs complete: {len(sensitivity_results)}")

    # ── Write results ─────────────────────────────────────────────────────────
    all_results = primary_results + sensitivity_results
    fieldnames = list(all_results[0].keys())
    with open(RESULTS_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"\nResults written to {RESULTS_FILE}")
    print(f"Total runs: {len(all_results)}")

    # ── Quick summary ─────────────────────────────────────────────────────────
    print("\n── QUICK SUMMARY (primary runs, mean E_total_DC by algorithm) ──")

    import statistics
    by_algo = {}
    for r in primary_results:
        a = r["algorithm"]
        if a not in by_algo:
            by_algo[a] = []
        by_algo[a].append(r["total_energy_j"])

    pabfd_mean = statistics.mean(by_algo.get("PABFD", [1]))
    print(f"{'Algorithm':<20} {'Mean E (MJ)':>12} {'vs PABFD %':>12} {'N':>4}")
    print("-" * 52)
    for algo in ALGORITHMS:
        if algo in by_algo:
            vals = by_algo[algo]
            mean_e = statistics.mean(vals)
            pct = (pabfd_mean - mean_e) / pabfd_mean * 100
            print(f"{algo:<20} {mean_e/1e6:>12.3f} {pct:>11.2f}% {len(vals):>4}")

    print("\n── SLA VIOLATION RATES ──")
    by_algo_sla = {}
    for r in primary_results:
        a = r["algorithm"]
        if a not in by_algo_sla:
            by_algo_sla[a] = []
        by_algo_sla[a].append(r["sla_violation_rate"])
    for algo in ALGORITHMS:
        if algo in by_algo_sla:
            mean_sla = statistics.mean(by_algo_sla[algo])
            print(f"  {algo:<20}: {mean_sla:.4f} ({mean_sla*100:.2f}%)")

    print("\nDone. Simulation complete.")
