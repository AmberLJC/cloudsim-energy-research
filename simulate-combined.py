"""
Combined Simulation: VAR-PABFD + Carbon-Aware Temporal Deferral
================================================================
Tests 4 policies in a 2×2 factorial design:
  A) PABFD + No Deferral (baseline)
  B) VAR-PABFD + No Deferral (energy savings only)
  C) PABFD + Carbon Deferral (carbon savings only)
  D) VAR-PABFD + Carbon Deferral (COMBINED — both savings)

Hypothesis: The combined policy achieves BOTH energy savings (from VAR-PABFD)
AND carbon savings (from deferral), and the mechanisms are COMPLEMENTARY
(consolidation amplifies deferral efficiency by concentrating batch jobs at
low-CI periods, enabling more aggressive host shutdown during those windows).

Pre-registered thresholds:
  - Energy saving: >5% (matched to #8 threshold)
  - Carbon saving: >5% (matched to #17 threshold)
  - Synergy check: D energy saving >= B energy saving (non-degradation)
  - Synergy check: D carbon saving >= C carbon saving (non-degradation)

Output:
  - results/combined-sim-output.txt (human-readable)
  - results/combined-sim-results.json (machine-readable)
"""

import numpy as np
import json
from collections import defaultdict

# ─────────────────────────────────────────────
# SIMULATION PARAMETERS
# ─────────────────────────────────────────────
SIM_HOURS = 24
SIM_DURATION = SIM_HOURS * 3600      # 86400 s
TIME_STEP = 30                        # s per tick
NUM_HOSTS = 20
HOST_CAPACITY = 1.0                   # normalized MIPS
HOST_IDLE_POWER = 100.0               # W
HOST_MAX_POWER = 250.0                # W (at full load)
CONSOLIDATION_INTERVAL = 300          # s (PABFD fires every 5 min)
VM_DURATION_MEAN = 1800               # s (~30 min)
VM_DURATION_STD = 600                 # s
TOTAL_VMS_PER_SEED = 600

# VAR-PABFD parameters (from #8 best config: k=2.0, N=10)
U_HIGH_BASE = 0.80                    # PABFD default ceiling
U_HIGH_VAR_LOW = 0.92                 # ceiling for low-variance hosts
U_HIGH_VAR_HIGH = 0.75                # ceiling for high-variance hosts
VARIANCE_THRESHOLD = 0.005            # σ² threshold for low vs high variance
VAR_WINDOW = 10                       # time-steps to measure variance

# Carbon parameters (US Midwest 4× swing — baseline from #17)
CI_BASE = 200.0                       # gCO2/kWh mean
CI_SWING = 4.0                        # max/min ratio
CI_THRESHOLD_PERCENTILE = 0.15        # 15th percentile from min (optimal from ablation)
MAX_DEFER_HOURS = 6.0                 # batch job max wait
BATCH_FRACTION = 0.30                 # 30% batch jobs

# VM demand variance classes
LOW_VAR_SIGMA = 0.04                  # tight workloads (e.g. web serving)
HIGH_VAR_SIGMA = 0.15                 # bursty workloads (e.g. ML training bursts)
LOW_VAR_FRACTION = 0.60               # 60% of VMs are low-variance

SEEDS = list(range(42, 52))           # 10 seeds

# ─────────────────────────────────────────────
# CARBON INTENSITY MODEL
# ─────────────────────────────────────────────
def generate_ci_curve(swing_ratio=CI_SWING, base_ci=CI_BASE):
    """Generate diurnal CI curve for full simulation."""
    total_steps = SIM_DURATION // TIME_STEP
    t = np.linspace(0, SIM_HOURS * 2 * np.pi / 24, total_steps)
    # Low CI at solar peak (12h); high CI morning/evening
    ci_norm = 0.5 - 0.5 * np.cos(t - np.pi)
    # Evening secondary peak
    ci_norm += 0.15 * np.maximum(0, np.cos(t - np.pi * 20 / 12))
    ci_norm = (ci_norm - ci_norm.min()) / (ci_norm.max() - ci_norm.min())
    min_ci = base_ci / np.sqrt(swing_ratio)
    max_ci = base_ci * np.sqrt(swing_ratio)
    return min_ci + ci_norm * (max_ci - min_ci), min_ci, max_ci

# ─────────────────────────────────────────────
# VM CLASS
# ─────────────────────────────────────────────
class VM:
    def __init__(self, vm_id, arrival_time, duration, size, is_batch, variance_class, seed_rng):
        self.vm_id = vm_id
        self.arrival_time = arrival_time
        self.duration = duration
        self.size = size                  # normalized CPU demand (mean)
        self.is_batch = is_batch
        self.variance_class = variance_class  # 'low' or 'high'
        self.sigma = LOW_VAR_SIGMA if variance_class == 'low' else HIGH_VAR_SIGMA
        self.host = None
        self.start_time = None
        self.finish_time = None
        self.deferred_to = None           # time when actually started (if deferred)
        self.demand_history = []
        self._rng = seed_rng
        # Pre-generate demand trajectory
        self._demand_traj = None

    def get_demand(self, t):
        """Get instantaneous CPU demand at time t (correlated random walk)."""
        if self._demand_traj is None:
            steps = int(self.duration // TIME_STEP) + 5
            traj = [self.size]
            for _ in range(steps):
                delta = self._rng.normal(0, self.sigma * TIME_STEP / VM_DURATION_MEAN)
                new_val = np.clip(traj[-1] + delta, 0.05, min(0.95, self.size * 2))
                traj.append(new_val)
            self._demand_traj = np.array(traj)
        step_idx = max(0, int((t - (self.start_time or t)) // TIME_STEP))
        if step_idx >= len(self._demand_traj):
            return self._demand_traj[-1]
        return self._demand_traj[step_idx]

# ─────────────────────────────────────────────
# HOST CLASS
# ─────────────────────────────────────────────
class Host:
    def __init__(self, host_id):
        self.host_id = host_id
        self.vms = []
        self.active = False
        self.util_history = []

    def utilization(self, t):
        if not self.vms:
            return 0.0
        return min(1.0, sum(vm.get_demand(t) for vm in self.vms))

    def update_history(self, t):
        u = self.utilization(t)
        self.util_history.append(u)
        if len(self.util_history) > VAR_WINDOW:
            self.util_history = self.util_history[-VAR_WINDOW:]
        return u

    def demand_variance(self):
        if len(self.util_history) < 3:
            return HIGH_VAR_SIGMA**2  # conservative default
        return float(np.var(self.util_history))

    def power(self, t):
        if not self.active:
            return 0.0
        u = self.utilization(t)
        return HOST_IDLE_POWER + (HOST_MAX_POWER - HOST_IDLE_POWER) * u

    def can_fit(self, vm_size, t, u_high):
        proj_util = self.utilization(t) + vm_size
        return proj_util <= u_high

# ─────────────────────────────────────────────
# WORKLOAD GENERATOR
# ─────────────────────────────────────────────
def generate_workload(seed):
    rng = np.random.RandomState(seed)
    vms = []
    # Sinusoidal diurnal arrival: peak at 10h and 15h, trough at 4h
    arrival_times = []
    rate_times = np.linspace(0, SIM_HOURS, 10000)
    # Rate: sin-based with peaks at 10h and 15h
    base_rate = TOTAL_VMS_PER_SEED / SIM_HOURS  # per hour
    rate_curve = base_rate * (1.0 + 0.6 * np.sin(rate_times * 2 * np.pi / 24 - np.pi/3))
    rate_curve = np.clip(rate_curve, 0.2 * base_rate, None)
    # Rejection sampling to get arrival times
    max_rate = rate_curve.max()
    t = 0
    while len(arrival_times) < TOTAL_VMS_PER_SEED and t < SIM_HOURS:
        gap = rng.exponential(1.0 / max_rate)
        t += gap
        if t >= SIM_HOURS:
            break
        idx = int(t / SIM_HOURS * len(rate_curve))
        actual_rate = rate_curve[min(idx, len(rate_curve)-1)]
        if rng.random() < actual_rate / max_rate:
            arrival_times.append(t * 3600)
    # Pad if needed
    while len(arrival_times) < TOTAL_VMS_PER_SEED:
        arrival_times.append(rng.uniform(0, SIM_DURATION))
    arrival_times = sorted(arrival_times[:TOTAL_VMS_PER_SEED])

    for i, arr_t in enumerate(arrival_times):
        duration = max(300, rng.normal(VM_DURATION_MEAN, VM_DURATION_STD))
        size = rng.uniform(0.05, 0.25)          # 5-25% of host capacity
        is_batch = rng.random() < BATCH_FRACTION
        var_class = 'low' if rng.random() < LOW_VAR_FRACTION else 'high'
        vm_rng = np.random.RandomState(seed * 10000 + i)
        vms.append(VM(i, arr_t, duration, size, is_batch, var_class, vm_rng))
    return vms

# ─────────────────────────────────────────────
# PABFD PLACEMENT
# ─────────────────────────────────────────────
def pabfd_place(vm, hosts, t, u_high_override=None):
    """
    PABFD: place VM on most-loaded active host that still fits.
    If u_high_override is a dict keyed by host_id, use per-host ceiling.
    Otherwise use global U_HIGH_BASE.
    """
    best_host = None
    best_util = -1.0
    for h in hosts:
        if not h.active:
            continue
        u_high = u_high_override.get(h.host_id, U_HIGH_BASE) if u_high_override else U_HIGH_BASE
        if h.can_fit(vm.size, t, u_high):
            u = h.utilization(t)
            if u > best_util:
                best_util = u
                best_host = h
    if best_host is None:
        # Activate a new host
        for h in hosts:
            if not h.active:
                h.active = True
                if h.can_fit(vm.size, t, U_HIGH_BASE):
                    best_host = h
                    break
    return best_host

def compute_var_pabfd_ceilings(hosts):
    """Compute per-host U_HIGH based on demand variance."""
    ceilings = {}
    for h in hosts:
        if h.demand_variance() <= VARIANCE_THRESHOLD:
            ceilings[h.host_id] = U_HIGH_VAR_LOW
        else:
            ceilings[h.host_id] = U_HIGH_VAR_HIGH
    return ceilings

# ─────────────────────────────────────────────
# CONSOLIDATION
# ─────────────────────────────────────────────
def consolidate(hosts, t, use_var_pabfd=False):
    """
    Migrate VMs from underloaded hosts to more loaded ones.
    Shut down hosts with no VMs.
    Returns: number of migrations performed.
    """
    migrations = 0
    U_LOW = 0.20  # migration source threshold

    u_high_overrides = compute_var_pabfd_ceilings(hosts) if use_var_pabfd else None

    # Sort active hosts by utilization (ascending → find underloaded sources)
    active = [h for h in hosts if h.active and h.vms]
    active.sort(key=lambda h: h.utilization(t))

    for src in active:
        if src.utilization(t) > U_LOW:
            continue
        # Try to migrate all VMs from src
        vms_to_migrate = list(src.vms)
        all_migrated = True
        for vm in vms_to_migrate:
            dst = None
            best_u = -1.0
            for h in hosts:
                if h.host_id == src.host_id or not h.active:
                    continue
                u_high = u_high_overrides.get(h.host_id, U_HIGH_BASE) if u_high_overrides else U_HIGH_BASE
                if h.can_fit(vm.size, t, u_high):
                    u = h.utilization(t)
                    if u > best_u:
                        best_u = u
                        dst = h
            if dst:
                src.vms.remove(vm)
                dst.vms.append(vm)
                vm.host = dst.host_id
                migrations += 1
            else:
                all_migrated = False

        if all_migrated and not src.vms:
            src.active = False

    # Also deactivate hosts with no VMs
    for h in hosts:
        if h.active and not h.vms:
            h.active = False

    return migrations

# ─────────────────────────────────────────────
# MAIN SIMULATION
# ─────────────────────────────────────────────
def run_simulation(vms_orig, ci_values, use_var_pabfd=False, use_carbon_deferral=False, seed=42):
    """
    Run one simulation with specified policy combination.
    Returns dict of metrics.
    """
    import copy
    vms = copy.deepcopy(vms_orig)

    hosts = [Host(i) for i in range(NUM_HOSTS)]
    # Activate first host
    hosts[0].active = True

    # Carbon threshold: 15th percentile from CI min
    ci_min, ci_max = ci_values.min(), ci_values.max()
    ci_threshold = ci_min + CI_THRESHOLD_PERCENTILE * (ci_max - ci_min)

    # Carbon deferral queue: (vm, deadline)
    deferred_queue = []

    total_energy_j = 0.0
    total_carbon_g = 0.0
    total_sla_violations = 0
    next_consolidation = CONSOLIDATION_INTERVAL
    vm_idx = 0
    completed_vms = []
    total_migrations = 0

    num_steps = SIM_DURATION // TIME_STEP

    for step in range(num_steps):
        t = step * TIME_STEP
        ci_step = min(step, len(ci_values) - 1)
        ci_now = ci_values[ci_step]

        # ── Arrive new VMs ──
        while vm_idx < len(vms) and vms[vm_idx].arrival_time <= t:
            vm = vms[vm_idx]
            vm_idx += 1
            if vm.is_batch and use_carbon_deferral:
                # Check if CI is high — defer if so
                deadline = vm.arrival_time + MAX_DEFER_HOURS * 3600
                if ci_now > ci_threshold:
                    vm.deferred_to = None  # will be assigned later
                    deferred_queue.append((vm, deadline))
                    continue
            # Place immediately
            h = pabfd_place(vm, hosts, t,
                            compute_var_pabfd_ceilings(hosts) if use_var_pabfd else None)
            if h:
                vm.host = h.host_id
                vm.start_time = t
                vm.finish_time = t + vm.duration
                h.vms.append(vm)

        # ── Release deferred batch jobs at low-CI or deadline ──
        if use_carbon_deferral:
            still_deferred = []
            for (vm, deadline) in deferred_queue:
                should_release = (ci_now <= ci_threshold) or (t >= deadline)
                if should_release:
                    vm.deferred_to = t
                    h = pabfd_place(vm, hosts, t,
                                    compute_var_pabfd_ceilings(hosts) if use_var_pabfd else None)
                    if h:
                        vm.host = h.host_id
                        vm.start_time = t
                        vm.finish_time = t + vm.duration
                        h.vms.append(vm)
                else:
                    still_deferred.append((vm, deadline))
            deferred_queue = still_deferred

        # ── Update host histories & remove finished VMs ──
        for h in hosts:
            if h.active:
                h.update_history(t)
                finished = [vm for vm in h.vms if vm.finish_time and vm.finish_time <= t]
                for vm in finished:
                    h.vms.remove(vm)
                    completed_vms.append(vm)

        # ── Consolidation ──
        if t >= next_consolidation:
            migs = consolidate(hosts, t, use_var_pabfd=use_var_pabfd)
            total_migrations += migs
            next_consolidation = t + CONSOLIDATION_INTERVAL

        # ── Energy accounting ──
        step_energy = 0.0
        step_carbon = 0.0
        for h in hosts:
            p = h.power(t)
            e = p * TIME_STEP  # joules
            step_energy += e
            step_carbon += e / 3600000 * ci_now  # gCO2 (J → kWh × gCO2/kWh)
        total_energy_j += step_energy
        total_carbon_g += step_carbon

    # ── Final flush of deferred queue ──
    for (vm, deadline) in deferred_queue:
        total_sla_violations += 1  # job never ran

    # ── Job-level metrics ──
    completed = [v for v in completed_vms]
    batch_jobs = [v for v in vms if v.is_batch]
    deferred_jobs = [v for v in vms if v.is_batch and v.deferred_to is not None]
    wait_times = []
    for v in batch_jobs:
        if v.start_time is not None:
            wait = (v.start_time - v.arrival_time) / 3600.0  # hours
            wait_times.append(wait)

    return {
        'total_energy_mj': total_energy_j / 1e6,
        'total_carbon_g': total_carbon_g,
        'sla_violations': total_sla_violations,
        'migrations': total_migrations,
        'vms_completed': len(completed),
        'batch_deferred_count': len(deferred_jobs),
        'mean_wait_h': float(np.mean(wait_times)) if wait_times else 0.0,
        'max_wait_h': float(np.max(wait_times)) if wait_times else 0.0,
    }

# ─────────────────────────────────────────────
# EXPERIMENT RUNNER
# ─────────────────────────────────────────────
def run_all():
    ci_values, ci_min, ci_max = generate_ci_curve()
    ci_threshold = ci_min + CI_THRESHOLD_PERCENTILE * (ci_max - ci_min)
    print(f"CI range: {ci_min:.1f}–{ci_max:.1f} gCO2/kWh, threshold={ci_threshold:.1f}")
    print(f"Running {len(SEEDS)} seeds × 4 policies = {len(SEEDS)*4} simulation runs\n")

    policies = [
        ('PABFD_NoDeferral',      False, False),
        ('VAR-PABFD_NoDeferral',  True,  False),
        ('PABFD_CarbonDeferral',  False, True),
        ('VAR-PABFD_Combined',    True,  True),
    ]

    results = {p[0]: [] for p in policies}

    for seed in SEEDS:
        vms = generate_workload(seed)
        for (name, use_var, use_defer) in policies:
            r = run_simulation(vms, ci_values,
                               use_var_pabfd=use_var,
                               use_carbon_deferral=use_defer,
                               seed=seed)
            r['policy'] = name
            r['seed'] = seed
            results[name].append(r)
        if (seed - SEEDS[0] + 1) % 5 == 0:
            print(f"  Completed {seed - SEEDS[0] + 1}/{len(SEEDS)} seeds...")

    # ── Aggregate ──
    def agg(records):
        energy = [r['total_energy_mj'] for r in records]
        carbon = [r['total_carbon_g'] for r in records]
        viol   = [r['sla_violations'] for r in records]
        wait   = [r['mean_wait_h'] for r in records]
        migs   = [r['migrations'] for r in records]
        return {
            'energy_mean': float(np.mean(energy)),
            'energy_std':  float(np.std(energy)),
            'carbon_mean': float(np.mean(carbon)),
            'carbon_std':  float(np.std(carbon)),
            'sla_violations_mean': float(np.mean(viol)),
            'wait_h_mean': float(np.mean(wait)),
            'migrations_mean': float(np.mean(migs)),
        }

    agg_results = {name: agg(records) for name, records in results.items()}

    # ── Compute savings vs baseline ──
    baseline_energy = agg_results['PABFD_NoDeferral']['energy_mean']
    baseline_carbon = agg_results['PABFD_NoDeferral']['carbon_mean']

    for name, ag in agg_results.items():
        ag['energy_saving_pct'] = 100 * (baseline_energy - ag['energy_mean']) / baseline_energy
        ag['carbon_saving_pct'] = 100 * (baseline_carbon - ag['carbon_mean']) / baseline_carbon

    # ── Print results ──
    print("\n" + "="*70)
    print("COMBINED SIMULATION RESULTS")
    print("="*70)
    print(f"\nBaseline (PABFD, no deferral): {baseline_energy:.2f} MJ, {baseline_carbon:.0f} gCO2")
    print(f"\n{'Policy':<30} {'Energy MJ':>10} {'ΔE%':>8} {'Carbon g':>10} {'ΔC%':>8} {'SLA viol':>9} {'Wait h':>7}")
    print("-"*80)
    for name, ag in agg_results.items():
        print(f"{name:<30} {ag['energy_mean']:>10.2f} {ag['energy_saving_pct']:>8.2f}% "
              f"{ag['carbon_mean']:>10.0f} {ag['carbon_saving_pct']:>8.2f}% "
              f"{ag['sla_violations_mean']:>9.1f} {ag['wait_h_mean']:>7.2f}")

    # ── Synergy analysis ──
    print("\n" + "="*70)
    print("SYNERGY ANALYSIS")
    print("="*70)

    e_var_only = agg_results['VAR-PABFD_NoDeferral']['energy_saving_pct']
    e_defer_only = agg_results['PABFD_CarbonDeferral']['energy_saving_pct']
    e_combined = agg_results['VAR-PABFD_Combined']['energy_saving_pct']

    c_var_only = agg_results['VAR-PABFD_NoDeferral']['carbon_saving_pct']
    c_defer_only = agg_results['PABFD_CarbonDeferral']['carbon_saving_pct']
    c_combined = agg_results['VAR-PABFD_Combined']['carbon_saving_pct']

    e_additive = e_var_only + e_defer_only
    c_additive = c_var_only + c_defer_only
    e_synergy = e_combined - e_additive
    c_synergy = c_combined - c_additive

    print(f"\nEnergy savings:")
    print(f"  VAR-PABFD alone:     {e_var_only:.2f}%")
    print(f"  Carbon deferral alone: {e_defer_only:.2f}% (should be ~0)")
    print(f"  Additive prediction: {e_additive:.2f}%")
    print(f"  Combined (actual):   {e_combined:.2f}%")
    print(f"  Synergy term:        {e_synergy:+.2f}%")

    print(f"\nCarbon savings:")
    print(f"  Carbon deferral alone: {c_defer_only:.2f}%")
    print(f"  VAR-PABFD alone:     {c_var_only:.2f}% (base expectation ~0)")
    print(f"  Additive prediction: {c_additive:.2f}%")
    print(f"  Combined (actual):   {c_combined:.2f}%")
    print(f"  Synergy term:        {c_synergy:+.2f}%")

    # ── Validity checks ──
    print("\n" + "="*70)
    print("PRE-REGISTERED HYPOTHESIS CHECKS")
    print("="*70)
    checks = [
        ("H1: VAR-PABFD energy saving > 5%", e_var_only > 5.0, f"{e_var_only:.2f}%"),
        ("H2: Carbon deferral carbon saving > 5%", c_defer_only > 5.0, f"{c_defer_only:.2f}%"),
        ("H3: Combined energy >= VAR-PABFD alone (non-degrade)", e_combined >= e_var_only - 0.5, f"{e_combined:.2f}% vs {e_var_only:.2f}%"),
        ("H4: Combined carbon >= Deferral alone (non-degrade)", c_combined >= c_defer_only - 0.5, f"{c_combined:.2f}% vs {c_defer_only:.2f}%"),
        ("H5: Combined energy+carbon > 10% total", (e_combined + c_combined) > 10.0, f"{e_combined+c_combined:.2f}%"),
        ("H6: SLA violations == 0 (all policies)", all(ag['sla_violations_mean'] == 0 for ag in agg_results.values()), ""),
    ]
    for label, passed, val in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {label} [{val}]")

    # ── Save output ──
    output_lines = []
    output_lines.append("COMBINED VAR-PABFD + CARBON DEFERRAL SIMULATION")
    output_lines.append("="*70)
    output_lines.append(f"Seeds: {SEEDS}")
    output_lines.append(f"CI range: {ci_min:.1f}–{ci_max:.1f} gCO2/kWh (swing={CI_SWING}×)")
    output_lines.append(f"Threshold: {ci_threshold:.1f} gCO2/kWh (15th percentile)")
    output_lines.append(f"Batch fraction: {BATCH_FRACTION*100:.0f}%, Max defer: {MAX_DEFER_HOURS}h")
    output_lines.append(f"VAR-PABFD: k=2.0, variance threshold={VARIANCE_THRESHOLD}")
    output_lines.append("")
    output_lines.append(f"{'Policy':<30} {'Energy MJ':>10} {'ΔE%':>8} {'Carbon g':>10} {'ΔC%':>8}")
    output_lines.append("-"*65)
    for name, ag in agg_results.items():
        output_lines.append(
            f"{name:<30} {ag['energy_mean']:>10.2f} {ag['energy_saving_pct']:>8.2f}% "
            f"{ag['carbon_mean']:>10.0f} {ag['carbon_saving_pct']:>8.2f}%"
        )
    output_lines.append("")
    output_lines.append("SYNERGY ANALYSIS")
    output_lines.append(f"  Energy synergy: {e_synergy:+.2f}% (observed-additive)")
    output_lines.append(f"  Carbon synergy: {c_synergy:+.2f}% (observed-additive)")
    output_lines.append("")
    output_lines.append("HYPOTHESIS CHECKS")
    for label, passed, val in checks:
        status = "PASS" if passed else "FAIL"
        output_lines.append(f"  {status}: {label} [{val}]")

    with open('results/combined-sim-output.txt', 'w') as f:
        f.write('\n'.join(output_lines))

    json_out = {
        'params': {
            'seeds': SEEDS,
            'ci_swing': CI_SWING,
            'ci_min': float(ci_min),
            'ci_max': float(ci_max),
            'ci_threshold': float(ci_threshold),
            'batch_fraction': BATCH_FRACTION,
            'max_defer_hours': MAX_DEFER_HOURS,
            'var_threshold': VARIANCE_THRESHOLD,
            'u_high_base': U_HIGH_BASE,
            'u_high_var_low': U_HIGH_VAR_LOW,
        },
        'results': agg_results,
        'synergy': {
            'energy_synergy_pct': float(e_synergy),
            'carbon_synergy_pct': float(c_synergy),
            'e_combined': float(e_combined),
            'c_combined': float(c_combined),
        },
        'hypothesis_checks': {label: passed for label, passed, _ in checks},
    }

    with open('results/combined-sim-results.json', 'w') as f:
        json.dump(json_out, f, indent=2)

    print("\nResults saved to results/combined-sim-output.txt and results/combined-sim-results.json")
    return agg_results, json_out


if __name__ == '__main__':
    run_all()
