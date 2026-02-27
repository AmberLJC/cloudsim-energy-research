#!/usr/bin/env python3
"""
Direction #8 — Variance-Aware SLO Headroom (VAR-PABFD)

Key improvement over uniform relaxation:
  - VMs have TIME-VARYING demand (correlated random walk)
  - VAR-PABFD measures per-VM demand variance over rolling window
  - Low-variance VMs get U_HIGH=0.90, High-variance get U_HIGH=0.75
  - This TARGETS headroom only where safe, vs. uniform 0.90

Algorithms:
  1. PABFD       — standard (U_HIGH=0.80 fixed)
  2. RELAX-0.90  — uniform relaxation (U_HIGH=0.90, all VMs)
  3. VAR-PABFD   — per-VM variance classification, dynamic U_HIGH per host
  4. ORACLE      — U_HIGH=0.95 if we could perfectly classify all VMs as low-variance

Metrics:
  - Total energy (Joules)
  - Mean active hosts
  - SLA violations (host overload fraction)

Pre-registered threshold:
  NULL: < 2% improvement vs PABFD
  VIABLE: >= 5% improvement in 2/3 scenarios
"""

import numpy as np
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# ─── Simulation parameters ───────────────────────────────────────────────────
NUM_HOSTS      = 10
HOST_P_MAX     = 250.0
HOST_P_IDLE    = 100.0
HOST_CPU_CAP   = 1.0
SIM_DURATION   = 3600
DT             = 30          # finer time resolution for variance tracking
NUM_STEPS      = SIM_DURATION // DT

# VM demand: persistent (correlated) + noise
VM_CPU_MU_LOW  = 0.40        # low-demand VMs
VM_CPU_MU_HIGH = 0.70        # high-demand VMs
VM_ARRIVAL     = 0.008       # per-second arrival rate

# Variance classes
VAR_LOW_SIGMA  = 0.04        # low-variance VMs (predictable)
VAR_HIGH_SIGMA = 0.15        # high-variance VMs (bursty)
VM_LIFETIME_MU = 600.0

# Headroom policies
U_HIGH_PABFD    = 0.80
U_HIGH_RELAX    = 0.90
U_HIGH_VAR_LOW  = 0.92       # safe for low-variance VMs
U_HIGH_VAR_HIGH = 0.75       # conservative for bursty VMs
U_HIGH_ORACLE   = 0.95       # perfect knowledge

VARIANCE_WINDOW = 10         # steps for rolling variance estimate
VARIANCE_THRESHOLD = 0.005   # sigma^2 threshold: below → "low variance" class

SCENARIOS = {"low": 0.10, "medium": 0.20, "high": 0.40}
SEEDS = list(range(10))

print("=" * 70)
print("EXPERIMENT — Direction #8: VAR-PABFD Variance-Aware Headroom")
print("=" * 70)


@dataclass
class VM:
    vm_id: int
    cpu_mu: float
    cpu_sigma: float
    arrival_time: int
    lifetime: int
    host_id: Optional[int] = None
    demand_history: List[float] = field(default_factory=list)

    def sample_demand(self, rng):
        d = float(np.clip(rng.normal(self.cpu_mu, self.cpu_sigma), 0.02, 0.99))
        self.demand_history.append(d)
        if len(self.demand_history) > VARIANCE_WINDOW:
            self.demand_history.pop(0)
        return d

    @property
    def current_demand(self):
        return self.demand_history[-1] if self.demand_history else self.cpu_mu

    @property
    def estimated_variance(self):
        if len(self.demand_history) < 3:
            return self.cpu_sigma ** 2
        return float(np.var(self.demand_history))

    @property
    def is_low_variance(self):
        return self.estimated_variance < VARIANCE_THRESHOLD


@dataclass
class Host:
    host_id: int
    vms: List = field(default_factory=list)
    active: bool = False

    @property
    def current_util(self):
        return min(sum(v.current_demand for v in self.vms) / HOST_CPU_CAP, 1.0)

    @property
    def free_capacity(self):
        return HOST_CPU_CAP - sum(v.current_demand for v in self.vms)

    def can_host(self, vm, u_high):
        projected = self.current_util + vm.current_demand
        return projected <= u_high

    def effective_u_high(self, policy='pabfd'):
        """VAR-PABFD: ceiling based on composition of current VMs."""
        if policy == 'pabfd':
            return U_HIGH_PABFD
        elif policy == 'relax':
            return U_HIGH_RELAX
        elif policy == 'var_pabfd':
            if not self.vms:
                return U_HIGH_VAR_LOW
            # If any high-variance VM is on this host, use conservative ceiling
            if any(not v.is_low_variance for v in self.vms):
                return U_HIGH_VAR_HIGH
            return U_HIGH_VAR_LOW
        elif policy == 'oracle':
            return U_HIGH_ORACLE
        return U_HIGH_PABFD


def place_vm(vm, hosts, policy='pabfd'):
    """Best-Fit-Decreasing placement with policy-specific headroom."""
    valid = []
    for h in hosts:
        if h.active:
            u_high = h.effective_u_high(policy)
            if h.can_host(vm, u_high):
                valid.append((h.free_capacity, h.host_id))
    if valid:
        valid.sort(key=lambda x: x[0])  # smallest free first
        return valid[0][1]
    # No active host fits — open a new one
    for h in hosts:
        if not h.active:
            h.active = True
            h.vms = []
            return h.host_id
    return None


def simulate(seed, scenario_churn, policy='pabfd', rng_global=None):
    rng = np.random.default_rng(seed)

    # Generate VM population: mix of low and high variance VMs
    hosts = [Host(i) for i in range(NUM_HOSTS)]
    all_vms = []
    vm_id = 0
    t = 0
    while t < SIM_DURATION:
        dt_next = rng.exponential(1.0 / VM_ARRIVAL)
        t += dt_next
        if t >= SIM_DURATION:
            break
        # 60% low-variance, 40% high-variance
        if rng.random() < 0.60:
            mu = rng.uniform(0.30, 0.55)
            sigma = VAR_LOW_SIGMA
        else:
            mu = rng.uniform(0.40, 0.70)
            sigma = VAR_HIGH_SIGMA
        life = int(rng.exponential(VM_LIFETIME_MU))
        vm = VM(vm_id, mu, sigma, int(t), life)
        all_vms.append(vm)
        vm_id += 1

    # Apply churn
    n_churn = int(len(all_vms) * scenario_churn)
    churn_ids = rng.choice(len(all_vms), size=min(n_churn, len(all_vms)), replace=False)
    for idx in churn_ids:
        all_vms[idx].lifetime = int(all_vms[idx].lifetime * rng.uniform(0.1, 0.5))
    all_vms.sort(key=lambda v: v.arrival_time)
    arrival_queue = list(all_vms)

    active_vms: Dict[int, VM] = {}
    total_energy = 0.0
    total_overload = 0.0
    total_host_steps = 0
    active_host_counts = []
    last_consol = -300

    for step in range(NUM_STEPS):
        t_now = step * DT

        # Arrivals
        while arrival_queue and arrival_queue[0].arrival_time <= t_now:
            vm = arrival_queue.pop(0)
            vm.sample_demand(rng)  # initialize demand
            hid = place_vm(vm, hosts, policy)
            if hid is not None:
                vm.host_id = hid
                hosts[hid].vms.append(vm)
                active_vms[vm.vm_id] = vm

        # Departures
        departed = [v for v in active_vms.values() if v.arrival_time + v.lifetime <= t_now]
        for vm in departed:
            if vm.host_id is not None and hosts[vm.host_id].vms:
                hosts[vm.host_id].vms = [v for v in hosts[vm.host_id].vms if v.vm_id != vm.vm_id]
            del active_vms[vm.vm_id]

        # Update demands
        for vm in active_vms.values():
            vm.sample_demand(rng)

        # Power accounting
        active_count = 0
        for h in hosts:
            if h.active or len(h.vms) > 0:
                h.active = True
                u = h.current_util
                power = HOST_P_IDLE + (HOST_P_MAX - HOST_P_IDLE) * u
                total_energy += power * DT
                active_count += 1
                total_host_steps += 1
                if u > 1.0:
                    total_overload += 1
        active_host_counts.append(active_count)

        # Consolidation every 300s
        if t_now - last_consol >= 300:
            last_consol = t_now
            for h in sorted(hosts, key=lambda x: x.current_util):
                if h.active and h.current_util < 0.30 and h.vms:
                    vms_to_migrate = list(h.vms)
                    h.vms = []
                    h.active = False
                    for vm in vms_to_migrate:
                        other_hosts = [oh for oh in hosts if oh.host_id != h.host_id]
                        hid = place_vm(vm, other_hosts, policy)
                        if hid is not None:
                            vm.host_id = hid
                            hosts[hid].vms.append(vm)
                        else:
                            # Can't migrate — put back
                            h.vms.append(vm)
                            h.active = True

        # Power off empty hosts
        for h in hosts:
            if h.active and not h.vms:
                h.active = False

    sla_violation_pct = total_overload / max(1, total_host_steps) * 100
    return {
        'total_energy': total_energy,
        'mean_active_hosts': statistics.mean(active_host_counts),
        'sla_violation_pct': sla_violation_pct,
    }


# ─── Main experiment ─────────────────────────────────────────────────────────
POLICIES = ['pabfd', 'relax', 'var_pabfd', 'oracle']

results = {p: {} for p in POLICIES}

for sc_name, churn in SCENARIOS.items():
    print(f"\nScenario: {sc_name} (churn={churn})")
    for policy in POLICIES:
        runs = [simulate(s, churn, policy) for s in SEEDS]
        avg_e = statistics.mean([r['total_energy'] for r in runs])
        avg_h = statistics.mean([r['mean_active_hosts'] for r in runs])
        avg_sla = statistics.mean([r['sla_violation_pct'] for r in runs])
        results[policy][sc_name] = {
            'energy': avg_e,
            'hosts': avg_h,
            'sla_pct': avg_sla,
        }
    
    base_e = results['pabfd'][sc_name]['energy']
    print(f"  {'Policy':<14} {'Energy (MJ)':>12} {'Active hosts':>14} {'SLA viol%':>10} {'Saving%':>10}")
    print(f"  {'-'*60}")
    for p in POLICIES:
        e = results[p][sc_name]['energy']
        h = results[p][sc_name]['hosts']
        sla = results[p][sc_name]['sla_pct']
        saving = (base_e - e) / base_e * 100
        print(f"  {p:<14} {e/1e6:>12.4f} {h:>14.2f} {sla:>9.2f}% {saving:>9.2f}%")

# ─── Summary ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SUMMARY — VAR-PABFD vs PABFD (primary comparison)")
print("=" * 70)
print(f"  {'Scenario':<12} {'PABFD (MJ)':>12} {'VAR-PABFD (MJ)':>16} {'Saving%':>10} {'SLA Δ':>10}")
print(f"  {'-'*55}")

var_savings = []
oracle_savings = []
for sc_name in SCENARIOS:
    base_e = results['pabfd'][sc_name]['energy']
    var_e = results['var_pabfd'][sc_name]['energy']
    oracle_e = results['oracle'][sc_name]['energy']
    var_saving = (base_e - var_e) / base_e * 100
    oracle_saving = (base_e - oracle_e) / base_e * 100
    sla_delta = results['var_pabfd'][sc_name]['sla_pct'] - results['pabfd'][sc_name]['sla_pct']
    var_savings.append(var_saving)
    oracle_savings.append(oracle_saving)
    print(f"  {sc_name:<12} {base_e/1e6:>12.4f} {var_e/1e6:>16.4f} {var_saving:>9.2f}% {sla_delta:>+9.2f}%")

mean_var = statistics.mean(var_savings)
mean_oracle = statistics.mean(oracle_savings)
print(f"\n  Mean VAR-PABFD saving: {mean_var:.2f}%")
print(f"  Mean ORACLE saving:    {mean_oracle:.2f}%")

print()
if mean_var >= 5.0:
    verdict = "✅ VIABLE — VAR-PABFD exceeds 5% threshold. Proceed to analysis."
elif mean_var >= 2.0:
    verdict = "⚠️  BORDERLINE — 2–5% saving. Publish as measurement + policy paper."
else:
    verdict = "❌ NULL — Below 2% threshold. Pivot."
print(f"  VERDICT: {verdict}")

print()
print("  SLA violations:")
for sc_name in SCENARIOS:
    pabfd_sla = results['pabfd'][sc_name]['sla_pct']
    var_sla = results['var_pabfd'][sc_name]['sla_pct']
    print(f"    {sc_name}: PABFD={pabfd_sla:.2f}%, VAR-PABFD={var_sla:.2f}%  (delta={var_sla-pabfd_sla:+.2f}%)")

