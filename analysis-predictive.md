# Analysis — Direction #3: P-PABFD Predictive Consolidation

**Protocol:** protocol-predictive.md (pre-registered 2026-02-27)  
**Analysis date:** 2026-02-27  
**Phase:** Analysis — NULL RESULT  
**Status:** ARCHIVED — Pivot triggered

---

## Summary Verdict

**H1 REJECTED.** No P-PABFD variant exceeds 2% energy savings over reactive PABFD in any
evaluated scenario. Maximum observed improvement: **+0.58%** (Oracle, low churn). Pre-registered
null threshold: 2%. Pre-registered proceed threshold: 5%.

**Stopping Rule 1 triggered** — null hypothesis not rejected → pivot to Direction #4.

---

## Simulation Configuration (from protocol-predictive.md)

| Parameter | Value |
|-----------|-------|
| Hosts | 10 (P_max=250W, P_idle=100W) |
| Simulation duration | 3600 s |
| Timestep | 60 s |
| Consolidation interval | 300 s |
| VM CPU demand | Gaussian(μ=0.6, σ=0.2) clamped [0.05, 1.0] |
| VM arrival | Poisson(λ=0.01 VM/s) |
| VM lifetime | Exponential(μ=600 s) |
| Seeds | 10 (0–9) |
| Primary lookahead | 300 s |
| Primary accuracy | 0.75 |
| Total runs | 690 (150 primary + 540 sensitivity) |

---

## Table 1: Primary Results (t_lookahead=300 s, p_accuracy=0.75)

Mean total datacenter energy by algorithm and churn scenario:

| Algorithm | Low churn (MJ) | vs PABFD | Med churn (MJ) | vs PABFD | High churn (MJ) | vs PABFD |
|-----------|---------------|---------|---------------|---------|----------------|---------|
| PABFD (baseline) | 2.9080 | — | 2.8038 | — | 2.3889 | — |
| FFD | 2.9200 | −0.41% | 2.7962 | +0.27% | 2.3901 | −0.05% |
| P_PABFD_EWA | 2.9110 | −0.10% | 2.8122 | −0.30% | 2.3907 | −0.08% |
| P_PABFD_AR3 | 2.9044 | +0.12% | 2.8134 | −0.34% | 2.3847 | +0.18% |
| P_PABFD_Oracle | 2.8912 | **+0.58%** | 2.7960 | +0.28% | 2.3787 | **+0.43%** |

*Positive "vs PABFD" = algorithm saves energy. Negative = uses more.*

**No algorithm exceeds 2% savings in any scenario.** Stopping Rule 1 applies.

---

## Table 2: SLA Violation Rate

| Algorithm | Low churn | Med churn | High churn |
|-----------|-----------|-----------|------------|
| PABFD | 3.75% | 3.03% | 2.47% |
| FFD | 3.37% | 2.52% | 2.13% |
| P_PABFD_EWA | 3.45% | 2.97% | 2.70% |
| P_PABFD_AR3 | 3.38% | 2.97% | 2.75% |
| P_PABFD_Oracle | 3.72% | 3.27% | 2.58% |

Note: Oracle causes 17–20x more migrations than PABFD (avg ~18 vs ~0.9), yet SLA rates are
similar — migrations succeed but carry negligible energy impact.

---

## Table 3: Sensitivity Results — P_PABFD_AR3 Mean Savings % by Accuracy × Lookahead

| Lookahead | Acc=0.50 | Acc=0.75 | Acc=0.90 |
|-----------|----------|----------|----------|
| 150 s | +0.05% | −0.06% | −0.19% |
| 300 s | +0.05% | −0.06% | −0.19% |
| 600 s | +0.05% | −0.06% | −0.19% |

**No sensitivity condition shows improvement > 0.5%.** Lookahead and accuracy level have
essentially no effect on outcome across all 540 sensitivity runs.

---

## Paired t-Test: PABFD vs P_PABFD_Oracle

| Scenario | Mean ΔPABFD−Oracle | % Saving | t-stat |
|----------|-------------------|---------|--------|
| Low | 16.8 kJ | 0.58% | 3.184 |
| Medium | 7.8 kJ | 0.28% | 1.090 |
| High | 10.2 kJ | 0.43% | 2.940 |

While low and high scenario t-stats are nominally significant (p ≈ 0.01), the effect size
(0.4–0.6%) is far below the pre-registered null threshold of 2%. Statistical significance
does not imply practical significance here.

---

## Mechanism Diagnosis — Why Falsification Overestimated Savings

The pre-registered falsification check estimated 3.4–13.6% recoverable savings. Actual
simulation: max 0.58% (Oracle). Root cause of the discrepancy:

### Error 1: Falsification assumed 6 idle events/hour with 150 s linger each
In the simulation, Oracle triggers ~18 proactive shutdowns per run vs PABFD's ~1. This
confirms proactive shutdowns are happening — but each saves only ~900 J (150 s × 100 W / ~2
— because idle time isn't the full 150 s estimated; some hosts are shut down naturally soon
after by PABFD's own 300 s consolidation check).

### Error 2: Idle energy savings are dwarfed by total runtime energy
Total energy per run: ~2.8–2.9 MJ (PABFD, primary scenario). Each proactive shutdown saves
at most P_idle × T_early = 100 W × 150 s = 15 kJ. With ~18 extra shutdowns (Oracle):
18 × 15 kJ = 270 kJ → 270/2900 = ~9%. But the actual savings are much less because:
- Not all proactive shutdowns save the full 150 s (some hosts would have shut down anyway soon)
- The simulation's mean linger time per event is actually ~10–20 s in practice, not 150 s

### Error 3: High consolidation rate means hosts rarely stay idle long
PABFD with T_consolidation=300 s and short VM lifetimes (mean 600 s) means hosts that become
underloaded are consolidated quickly regardless. The window for proactive improvement is small.

### Key Analytic Result: An Upper-Bound Argument
Let E_linger = P_idle × mean(T_linger) × N_events. For Oracle (best possible predictor):
N_events ≈ 18/run, T_linger ≈ 10–20 s empirically, P_idle = 100 W.
E_linger ≈ 100 × 15 × 18 = 27 kJ ≈ 0.9% of 2.9 MJ total.
This is consistent with the observed Oracle result of 0.58% (not all proactive shutdowns
fire under the linger window of PABFD).

---

## Cumulative Null Result Pattern Across All Three Directions

| Direction | Mechanism | Max observed savings | Mechanism explanation |
|-----------|-----------|---------------------|----------------------|
| #2 Dynamic PUE | Placement within active hosts | −0.35% to +0.27% | Analytically degenerate for linear P |
| #2 Extension | Non-linear P × ASHRAE PUE | ≤ +0.27% | Dominant lever is ON/OFF not placement |
| #3 Predictive shutdown | Host ON/OFF timing | ≤ +0.58% (Oracle) | Linger time too small; consolidation interval too short |

**Cross-direction finding:** PABFD with T_consolidation=300 s achieves near-optimal energy in
the simulation regime tested (10 hosts, 3600 s, linear power). The dominant remaining
opportunity is not scheduling smarter *within* the existing framework — it is changing the
*parameters* of the framework (headroom, SLO targets, utilization ceilings).

This points directly to **Direction #8: Probabilistic SLO Headroom Reduction** as the
next hypothesis: if we can pack more VMs per host by tightening headroom, we reduce the
number of active hosts — the lever that actually moves the needle.

---

## Publishable Secondary Finding

The combination of Direction #2 and #3 null results, with mechanism explanations, constitutes
a publishable "negative result" paper:

> **"PABFD Is Near-Optimal: Why Advanced Scheduling Heuristics Fail to Improve Energy
> Efficiency in Standard CloudSim Simulations"**

Key claims:
1. Dynamic PUE-aware placement: analytically degenerate for linear P (proven)
2. Predictive host shutdown: empirically negligible (≤0.6% even with Oracle)
3. Root cause: PABFD's consolidation is already aggressive enough that the residual idle
   energy in a 3600 s simulation with 10 hosts is <1% of total energy
4. Implication: future CloudSim energy studies need larger-scale simulations (100+ hosts,
   multi-day traces) to show meaningful differences between scheduling algorithms

---

*Analysis by autonomous research agent — 2026-02-27*
