#!/usr/bin/env python3
"""
Falsification Check — Direction #8: Probabilistic SLO Headroom Reduction

Research claim: Raising U_HIGH from 0.80 to 0.90 for low-variance VMs allows
more VMs per host → fewer active hosts → measurable idle energy savings.

This falsification check asks:
  1. What fraction of time do hosts actually operate near U_HIGH (80%)?
     If never → headroom is not binding → idea is moot.
  2. If we raise U_HIGH from 0.80 → 0.90, how many fewer hosts are needed?
     Theoretical estimate: 10% more capacity → ~11% fewer hosts.
  3. What is the expected energy saving from fewer hosts?
     ΔE ≈ P_idle × (N_hosts_saved) × T_active

Decision threshold:
  VIABLE:  expected saving > 5% of total energy
  MOOT:    expected saving < 2% of total energy
  BORDERLINE: 2–5%

Date: 2026-02-27
Protocol: Pre-falsification (before simulation code for #8 is written)
"""

import numpy as np
import statistics

# ─── Simulation parameters (same as primary runs) ─────────────────────────────
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

U_HIGH_BASE    = 0.80   # standard PABFD headroom
U_HIGH_RELAXED = 0.90   # proposed relaxed headroom

SCENARIOS = {"low": 0.10, "medium": 0.20, "high": 0.40}
SEEDS = list(range(10))

print("=" * 65)
print("FALSIFICATION CHECK — Direction #8: SLO Headroom Reduction")
print("=" * 65)

# ─── Part 1: How often do hosts actually approach U_HIGH? ─────────────────────

print("\n[1] BINDING CONSTRAINT ANALYSIS")
print("    How often do active hosts operate above 70% utilization?")
print("    (Near U_HIGH=80% → headroom IS binding)")
print()

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from collections import defaultdict

@dataclass
class VM:
    vm_id: int
    cpu_demand: float
    arrival_time: int
    lifetime: int
    host_id: Optional[int] = None

@dataclass
class Host:
    host_id: int
    vms: List = field(default_factory=list)
    active: bool = False

    @property
    def util(self):
        return min(sum(v.cpu_demand for v in self.vms) / HOST_CPU_CAP, 1.0)

    @property
    def free(self):
        return HOST_CPU_CAP - sum(v.cpu_demand for v in self.vms)

    def can_host(self, vm, u_high=U_HIGH_BASE):
        return self.free >= vm.cpu_demand and (self.util + vm.cpu_demand) <= u_high


def place_bfd(vm, hosts, u_high=U_HIGH_BASE):
    candidates = [(h.free, h.host_id) for h in hosts if h.active and h.can_host(vm, u_high)]
    if not candidates:
        for h in hosts:
            if not h.active:
                h.active = True
                h.vms = []
                return h.host_id
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def simulate_with_headroom(seed, scenario_churn, u_high):
    rng = np.random.default_rng(seed)
    hosts = [Host(i) for i in range(NUM_HOSTS)]
    
    all_vms = []
    vm_id = 0
    t = 0
    while t < SIM_DURATION:
        dt_next = rng.exponential(1.0 / VM_ARRIVAL)
        t += dt_next
        if t >= SIM_DURATION:
            break
        cpu = float(np.clip(rng.normal(VM_CPU_MU, VM_CPU_SIGMA), *VM_CPU_CLAMP))
        life = int(rng.exponential(VM_LIFETIME))
        all_vms.append(VM(vm_id, cpu, int(t), life))
        vm_id += 1
    
    n_churn = int(len(all_vms) * scenario_churn)
    churn_ids = rng.choice(len(all_vms), size=min(n_churn, len(all_vms)), replace=False)
    for idx in churn_ids:
        all_vms[idx].lifetime = int(all_vms[idx].lifetime * rng.uniform(0.1, 0.5))
    all_vms.sort(key=lambda v: v.arrival_time)
    arrival_queue = list(all_vms)
    
    active_vms = {}
    total_energy = 0.0
    host_util_samples = []
    active_host_counts = []
    near_ceiling_fraction = 0.0
    total_host_steps = 0
    near_ceiling_steps = 0
    last_consol = -300
    
    for step in range(NUM_STEPS):
        t_now = step * DT
        
        while arrival_queue and arrival_queue[0].arrival_time <= t_now:
            vm = arrival_queue.pop(0)
            hid = place_bfd(vm, hosts, u_high)
            if hid is not None:
                vm.host_id = hid
                hosts[hid].vms.append(vm)
                active_vms[vm.vm_id] = vm
        
        departed = [v for v in active_vms.values() if v.arrival_time + v.lifetime <= t_now]
        for vm in departed:
            if vm.host_id is not None:
                hosts[vm.host_id].vms = [v for v in hosts[vm.host_id].vms if v.vm_id != vm.vm_id]
            del active_vms[vm.vm_id]
        
        active_count = 0
        for h in hosts:
            if h.active or len(h.vms) > 0:
                h.active = True
                total_energy += (HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * h.util) * DT
                active_count += 1
                total_host_steps += 1
                if h.util > 0.70:  # near ceiling
                    near_ceiling_steps += 1
        active_host_counts.append(active_count)
        
        # Consolidation
        if t_now - last_consol >= 300:
            last_consol = t_now
            for h in hosts:
                if h.active and h.util < 0.30 and h.vms:
                    vms_here = list(h.vms)
                    h.vms = []
                    h.active = False
                    for vm in vms_here:
                        hid = place_bfd(vm, [oh for oh in hosts if oh.host_id != h.host_id], u_high)
                        if hid is not None:
                            vm.host_id = hid
                            hosts[hid].vms.append(vm)
        
        for h in hosts:
            if h.active and not h.vms:
                h.active = False
    
    near_pct = near_ceiling_steps / max(1, total_host_steps)
    return {
        'total_energy': total_energy,
        'mean_active_hosts': statistics.mean(active_host_counts),
        'near_ceiling_pct': near_pct,
        'total_vms': len(all_vms),
    }


# Run baseline (U_HIGH=0.80) across scenarios
print(f"{'Scenario':<12} {'Mean active hosts':>18} {'% time near U_HIGH=0.80':>25} {'Energy (MJ)':>12}")
print("-" * 70)

baseline_results = {}
relaxed_results = {}

for sc_name, churn in SCENARIOS.items():
    base_runs = [simulate_with_headroom(s, churn, U_HIGH_BASE) for s in SEEDS]
    relax_runs = [simulate_with_headroom(s, churn, U_HIGH_RELAXED) for s in SEEDS]
    
    base_energy = statistics.mean([r['total_energy'] for r in base_runs])
    base_hosts = statistics.mean([r['mean_active_hosts'] for r in base_runs])
    base_near = statistics.mean([r['near_ceiling_pct'] for r in base_runs])
    
    relax_energy = statistics.mean([r['total_energy'] for r in relax_runs])
    relax_hosts = statistics.mean([r['mean_active_hosts'] for r in relax_runs])
    
    savings_pct = (base_energy - relax_energy) / base_energy * 100
    hosts_saved = base_hosts - relax_hosts
    
    baseline_results[sc_name] = {'energy': base_energy, 'hosts': base_hosts, 'near': base_near}
    relaxed_results[sc_name] = {'energy': relax_energy, 'hosts': relax_hosts, 'savings': savings_pct}
    
    print(f"{sc_name:<12} {base_hosts:>18.2f} {base_near*100:>24.1f}% {base_energy/1e6:>12.4f}")

print()
print("[2] ENERGY SAVINGS FROM RELAXED HEADROOM (U_HIGH: 0.80 → 0.90)")
print()
print(f"{'Scenario':<12} {'Base hosts':>12} {'Relax hosts':>13} {'Hosts saved':>13} {'Energy saving':>15}")
print("-" * 70)

all_savings = []
for sc_name in SCENARIOS:
    b = baseline_results[sc_name]
    r = relaxed_results[sc_name]
    hosts_saved = b['hosts'] - r['hosts']
    savings = r['savings']
    all_savings.append(savings)
    print(f"{sc_name:<12} {b['hosts']:>12.2f} {r['hosts']:>13.2f} {hosts_saved:>13.2f} {savings:>14.2f}%")

print()
print("[3] THEORETICAL ESTIMATE VS SIMULATED")
print()
print("  Theoretical (simple): +10% capacity per host → ~9.1% fewer hosts")
print("  Each host saved → P_idle × T_active = 100W × ~3000s = 300 kJ/run")
print()
for sc_name in SCENARIOS:
    b = baseline_results[sc_name]
    r = relaxed_results[sc_name]
    hosts_saved = b['hosts'] - r['hosts']
    est_saving = hosts_saved * HOST_P_IDLE * 3000 / b['energy'] * 100
    print(f"  {sc_name}: {hosts_saved:.2f} hosts saved, est saving = {est_saving:.1f}%, actual = {r['savings']:.2f}%")

print()
print("[4] BINDING CONSTRAINT DIAGNOSIS")
print()
for sc_name in SCENARIOS:
    b = baseline_results[sc_name]
    near = b['near']
    if near > 0.20:
        diagnosis = "BINDING — headroom is frequently hit, relaxation will help"
    elif near > 0.05:
        diagnosis = "PARTIALLY BINDING — some benefit expected"
    else:
        diagnosis = "NOT BINDING — hosts rarely near ceiling, idea may be moot"
    print(f"  {sc_name}: {near*100:.1f}% of active host-steps at util > 0.70 → {diagnosis}")

print()
print("=" * 65)
print("FALSIFICATION VERDICT")
print("=" * 65)
mean_saving = statistics.mean(all_savings)
print(f"  Mean energy saving (0.80 → 0.90 headroom): {mean_saving:.2f}%")
print()
if mean_saving >= 5.0:
    print("  ✅ VIABLE — savings ≥ 5%. Direction #8 confirmed as primary direction.")
    print("     Proceed to Lit Review for #8.")
elif mean_saving >= 2.0:
    print("  ⚠️  BORDERLINE — savings 2–5%. May be publishable with variance modeling.")
    print("     Proceed with caution; note that full variance-aware algorithm may do better.")
else:
    print("  ❌ MOOT — savings < 2%. Headroom not the binding constraint.")
    print("     Pivot to next brainstorm candidate.")
    print()
    if mean_saving >= 0.5:
        print("  NOTE: Small positive effect exists but below publishable threshold.")
    else:
        print("  NOTE: Zero or negative effect — fundamental mechanism is absent.")

print()
print("  Key question: Is U_HIGH=80% the bottleneck, or is low utilization the norm?")
print("  See 'near_ceiling_pct' above for the answer.")
