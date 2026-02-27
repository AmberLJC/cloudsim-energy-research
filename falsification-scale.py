#!/usr/bin/env python3
"""
Falsification Check — Direction #16: Diurnal-Scale Consolidation

Research hypothesis: The null/borderline results of directions #2, #3, #8
are caused by simulation scale (3600s, 10 hosts) rather than algorithm weakness.
At realistic scale (24h, 50 hosts, diurnal workload), the same mechanisms
should produce measurably larger savings (>5%).

This script tests the SCALE HYPOTHESIS by running PABFD vs VAR-PABFD
at three scales and measuring whether savings % grows with scale:
  - Scale A: 3600s, 10 hosts (baseline from #8)
  - Scale B: 14400s (4h), 20 hosts
  - Scale C: 86400s (24h), 50 hosts

Diurnal workload: VM arrival rate follows sinusoidal pattern:
  λ(t) = λ_mean × (1 + 0.6 × sin(2π × t / 86400 + φ))
where φ offsets peak to midday.

Pre-registered: 2026-02-27
Decision threshold:
  VIABLE: savings at Scale C > 5%, AND savings grow with scale
  MOOT:   savings < 2% at Scale C (scale doesn't help)
"""

import numpy as np
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from collections import deque

# ─── Shared params ─────────────────────────────────────────────────────────────
HOST_P_MAX   = 250.0
HOST_P_IDLE  = 100.0
HOST_CPU_CAP = 1.0
VM_CPU_MU    = 0.6
VM_CPU_SIGMA = 0.2
VM_CPU_CLAMP = (0.05, 1.0)
VM_LIFETIME_MEAN = 600.0
U_HIGH_BASE  = 0.80
U_LOW        = 0.30
CONSOL_INT   = 300
DT           = 60

SCALES = {
    "A_3600s_10h":   (3600,  10, 0.01,  60),   # (duration, n_hosts, λ_mean, VM_count_hint)
    "B_14400s_20h":  (14400, 20, 0.015, 150),
    "C_86400s_50h":  (86400, 50, 0.02,  500),
}

SEEDS = list(range(5))  # 5 seeds for speed

@dataclass
class VM:
    vm_id: int
    base_cpu: float
    arrival_time: int
    lifetime: int
    host_id: Optional[int] = None
    demand_history: object = field(default_factory=lambda: deque(maxlen=10))

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

    def effective_u_high(self, k: float) -> float:
        if k == 0.0:
            return U_HIGH_BASE
        if not self.vms:
            return U_HIGH_BASE
        sigma = statistics.mean(v.demand_variance for v in self.vms)
        return min(0.95, U_HIGH_BASE + k * sigma)

    def can_host(self, vm, k: float) -> bool:
        u_high = self.effective_u_high(k)
        projected = sum(v.current_demand for v in self.vms) / HOST_CPU_CAP + vm.base_cpu
        return projected <= u_high


def place_bfd(vm, hosts, k):
    candidates = [(h.free, h.host_id) for h in hosts if h.active and h.can_host(vm, k)]
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    for h in hosts:
        if not h.active:
            h.active = True
            h.vms = []
            return h.host_id
    return None

# property for Host.free
Host.free = property(lambda self: HOST_CPU_CAP - sum(v.current_demand for v in self.vms))


def simulate(seed, duration, n_hosts, lambda_mean, k, diurnal=True):
    rng = np.random.default_rng(seed)
    hosts = [Host(i) for i in range(n_hosts)]
    n_steps = duration // DT

    # Generate VM arrivals with optional diurnal pattern
    all_vms = []
    vm_id = 0
    t = 0.0
    while t < duration:
        # Diurnal arrival rate: peaks at noon (t=43200s for 24h)
        if diurnal and duration >= 14400:
            lam = lambda_mean * (1.0 + 0.6 * np.sin(2 * np.pi * t / 86400 - np.pi/2))
            lam = max(lam, lambda_mean * 0.2)  # floor at 20% of mean
        else:
            lam = lambda_mean
        dt_next = rng.exponential(1.0 / lam)
        t += dt_next
        if t >= duration:
            break
        base_cpu = float(np.clip(rng.normal(VM_CPU_MU, VM_CPU_SIGMA), *VM_CPU_CLAMP))
        life = int(rng.exponential(VM_LIFETIME_MEAN))
        vm = VM(vm_id, base_cpu, int(t), life, demand_history=deque(maxlen=10))
        all_vms.append(vm)
        vm_id += 1

    all_vms.sort(key=lambda v: v.arrival_time)
    arrival_queue = list(all_vms)
    active_vms = {}
    total_energy = 0.0
    last_consol = -CONSOL_INT
    active_host_counts = []

    for step in range(n_steps):
        t_now = step * DT

        # Arrivals
        while arrival_queue and arrival_queue[0].arrival_time <= t_now:
            vm = arrival_queue.pop(0)
            hid = place_bfd(vm, hosts, k)
            if hid is not None:
                vm.host_id = hid
                hosts[hid].vms.append(vm)
                active_vms[vm.vm_id] = vm

        # Update demand
        for vm in active_vms.values():
            noisy = float(np.clip(rng.normal(vm.base_cpu, vm.base_cpu * 0.15), *VM_CPU_CLAMP))
            vm.demand_history.append(noisy)

        # Departures
        departed = [v for v in active_vms.values() if v.arrival_time + v.lifetime <= t_now]
        for vm in departed:
            if vm.host_id is not None and 0 <= vm.host_id < n_hosts:
                hosts[vm.host_id].vms = [v for v in hosts[vm.host_id].vms if v.vm_id != vm.vm_id]
            del active_vms[vm.vm_id]

        # Energy
        active_count = 0
        for h in hosts:
            if h.vms:
                h.active = True
            if h.active:
                power = HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * h.util
                total_energy += power * DT
                active_count += 1
        active_host_counts.append(active_count)

        # Consolidation
        if t_now - last_consol >= CONSOL_INT:
            last_consol = t_now
            for h in hosts:
                if h.active and h.util < U_LOW and h.vms:
                    vms_to_move = list(h.vms)
                    h.vms = []
                    h.active = False
                    for vm in vms_to_move:
                        other = [oh for oh in hosts if oh.host_id != h.host_id]
                        hid = place_bfd(vm, other, k)
                        if hid is not None:
                            vm.host_id = hid
                            hosts[hid].vms.append(vm)
                        else:
                            h.active = True
                            h.vms.append(vm)
                            vm.host_id = h.host_id

        for h in hosts:
            if h.active and not h.vms:
                h.active = False

    mean_active = statistics.mean(active_host_counts) if active_host_counts else 0
    return {
        'total_energy_J': total_energy,
        'mean_active_hosts': mean_active,
        'total_vms': len(all_vms),
        'n_hosts': n_hosts,
    }


print("=" * 70)
print("FALSIFICATION — Direction #16: Scale Hypothesis")
print("=" * 70)
print()
print("Hypothesis: VAR-PABFD savings grow with simulation scale.")
print("k=2.0 (best from #8), diurnal arrival pattern at scale B & C.")
print()

results_table = {}
for scale_name, (duration, n_hosts, lam, _) in SCALES.items():
    print(f"Running scale {scale_name} ({duration}s, {n_hosts} hosts)...")
    base_runs = []
    var_runs = []
    for seed in SEEDS:
        b = simulate(seed, duration, n_hosts, lam, k=0.0, diurnal=True)
        v = simulate(seed, duration, n_hosts, lam, k=2.0, diurnal=True)
        base_runs.append(b)
        var_runs.append(v)

    base_e = statistics.mean(r['total_energy_J'] for r in base_runs)
    var_e = statistics.mean(r['total_energy_J'] for r in var_runs)
    savings_pct = (base_e - var_e) / base_e * 100
    base_h = statistics.mean(r['mean_active_hosts'] for r in base_runs)
    var_h = statistics.mean(r['mean_active_hosts'] for r in var_runs)
    base_vms = statistics.mean(r['total_vms'] for r in base_runs)

    results_table[scale_name] = {
        'savings_pct': savings_pct,
        'base_e_MJ': base_e / 1e6,
        'var_e_MJ': var_e / 1e6,
        'base_hosts': base_h,
        'var_hosts': var_h,
        'total_vms': base_vms,
    }
    print(f"  Base: {base_e/1e6:.4f} MJ, VAR: {var_e/1e6:.4f} MJ, saving: {savings_pct:.2f}%")
    print(f"  Hosts: base={base_h:.2f}, var={var_h:.2f}, VMs: {base_vms:.0f}")
    print()

print()
print("=" * 70)
print("SCALE HYPOTHESIS EVALUATION")
print("=" * 70)
print()
print(f"{'Scale':<22} {'Savings %':>10} {'Base E (MJ)':>12} {'VAR E (MJ)':>12} {'Hosts saved':>12}")
print("-" * 72)
savings_series = []
for scale_name, r in results_table.items():
    hosts_saved = r['base_hosts'] - r['var_hosts']
    print(f"{scale_name:<22} {r['savings_pct']:>9.2f}% {r['base_e_MJ']:>12.4f} {r['var_e_MJ']:>12.4f} {hosts_saved:>12.2f}")
    savings_series.append(r['savings_pct'])

print()

# Check if savings grow monotonically with scale
grows = all(savings_series[i] <= savings_series[i+1] for i in range(len(savings_series)-1))
scale_c_savings = list(results_table.values())[-1]['savings_pct']

print(f"  Savings grow with scale: {'YES' if grows else 'NO (non-monotonic)'}")
print(f"  Scale C savings: {scale_c_savings:.2f}%")
print()

if scale_c_savings >= 5.0 and grows:
    verdict = "✅ VIABLE — Scale is the bottleneck. Run full 24h simulation."
    detail = "The effect size grows with scale. Proceed to full 24h/50-host simulation."
elif scale_c_savings >= 5.0:
    verdict = "⚠️  PARTIALLY VIABLE — Large scale savings but non-monotonic growth."
    detail = "Effect exists at scale C. Run full simulation but diagnose non-monotonicity."
elif scale_c_savings >= 2.0:
    verdict = "⚠️  BORDERLINE — Scale helps but not enough. Pivot to #17 (carbon-aware)."
    detail = "Scale extends the effect but not beyond publishable threshold."
else:
    verdict = "❌ MOOT — Scale doesn't help. Pivot to carbon-aware scheduling (#17)."
    detail = "The effect does NOT grow with scale. Root cause is elsewhere."

print(f"  VERDICT: {verdict}")
print(f"  DETAIL: {detail}")
print()
print("  Pre-registration for #16:")
print("  If VIABLE: full sim = 10 seeds × 2 configs × 3 scenarios × Scale C = 60 runs")
print("  Metric: energy saving %, mean active hosts, diurnal variance of savings")
