# Research Protocol — Direction #3: P-PABFD Predictive Consolidation

**Status:** PRE-REGISTERED (locked — 2026-02-27)  
**Author:** Research Agent (cloudsim-research-advisor)  
**Phase:** Experiment Design → Implementation  
**Supersedes:** protocol.md (Direction #2, now archived)

> ⚠️ **Pre-registration principle:** This protocol is written before simulation code is run.
> Any deviation from the plan below must be documented as a protocol amendment in LOGBOX.md.
> No cherry-picking of metrics or conditions after seeing results.

---

## 1. Background & Motivation

Direction #2 (Dynamic PUE-Aware Placement) produced a **null result across all 4 model
variants** (linear/quadratic power × linear/ASHRAE PUE). The analytic mechanism was
identified: for all tested combinations, VM *placement within active hosts* changes total
energy by a negligible amount; the dominant lever is **host on/off state** (binary).

This observation directly motivates Direction #3: rather than optimizing *which active host*
receives a VM, we optimize *when idle hosts are shut down*. The mechanism:

- PABFD uses a reactive underload check: if `util_host(t) < U_low (30%)`, consolidate
- After falling below threshold, a host may remain idle for 0–300 s before the next
  consolidation check fires (consolidation interval = 5 min, mean wait ≈ 150 s)
- Each idle event wastes: `P_idle × T_wait = 100 W × 150 s = 15 kJ`
- Our falsification check confirmed: 3.4–13.6% of total compute energy is recoverable

**P-PABFD (Predictive-PABFD)** adds a lightweight temporal predictor to the underload
detection step. Instead of asking "is utilization below threshold NOW?", it asks
"will utilization drop below threshold within the next T_lookahead seconds?" and
initiates shutdown proactively.

---

## 2. Pre-Registered Hypotheses

### H1 (Primary)
> "P-PABFD with a 5-minute lookahead predictor (ARIMA-3 or exponential smoothing) reduces
> total datacenter energy by ≥ 5% compared to reactive PABFD, across at least 2 of 3
> churn scenarios (low/medium/high), without increasing SLA violation rate by more than
> 2 percentage points."

### H2 (Accuracy Tradeoff)
> "Prediction accuracy of ≥ 0.75 (correctly identifying ≥ 75% of upcoming underload
> events) is sufficient to achieve ≥ 80% of the Oracle upper bound energy savings.
> Below 0.50 accuracy, P-PABFD performs worse than reactive PABFD due to excessive
> false-positive shutdowns causing VM migrations."

### H3 (Predictor Complexity)
> "Exponential smoothing (EWA) achieves ≥ 90% of the energy savings of ARIMA-3, making
> the added complexity of ARIMA unnecessary in practice."

### H0 (Null)
> "P-PABFD does not improve total datacenter energy by more than 2% over reactive PABFD
> in any evaluated scenario."

**Falsification threshold (pre-registered):**
- < 2% improvement in all scenarios → null hypothesis NOT rejected → evaluate pivot
- > 5% improvement in ≥ 2/3 scenarios → proceed to full paper write-up
- 2–5% in ≥ 2/3 scenarios → borderline; extend dataset (Azure trace if available)

---

## 3. Algorithm Definitions

### Baseline: PABFD (Reactive)
Standard Beloglazov 2012 algorithm:
1. Every `T_consolidation` seconds (300 s), scan all hosts
2. If `util_host(t) < U_low (0.30)`, migrate all VMs off that host and shut it down
3. Placement: best-fit decreasing by CPU demand

### Proposed: P-PABFD (Proactive Predictive)

**Modification to step 2 only:**  
Replace: `if util_host(t) < U_low`  
With: `if predict(util_host, t + T_lookahead) < U_low`

Where `predict(...)` uses one of:
- **ARIMA-3**: AR(3) fitted to last N=20 observations of host utilization
  - Simple autoregression: `u(t+k) = φ₁u(t) + φ₂u(t-1) + φ₃u(t-2) + c`
  - Fitted via OLS at each prediction call
  - Falls back to current util if insufficient history (< 5 observations)
- **EWA**: Exponentially weighted average of recent utilization
  - `û(t+k) = α × u(t) + (1-α) × û(t-1)`, α = 0.3 (decay parameter)
  - Simple and fast; no fitting required
- **Oracle**: Perfect predictor — uses actual `util_host(t + T_lookahead)`
  - Upper bound; not deployable but establishes ceiling

**Prediction accuracy model (for realistic non-oracle runs):**  
The `predict()` function introduces controlled noise:
- With probability `p_accuracy`, it returns the true predicted value
- With probability `1 - p_accuracy`, it adds Gaussian noise: `σ = 0.15`
- This models realistic predictor imperfection without requiring a full time-series model

**False-positive handling:**  
When predictor incorrectly signals underload → host shutdown initiated → VMs migrated
to other hosts. If no host has capacity → migration fails → SLA violation counted.

---

## 4. Experimental Design

### 4.1 Algorithms Evaluated (5 total)

| ID | Name | Description |
|----|------|-------------|
| A0 | PABFD | Reactive baseline (Beloglazov 2012) |
| A1 | FFD | First-fit decreasing (simpler reactive baseline) |
| A2 | P-PABFD-EWA | Predictive with exponential smoothing |
| A3 | P-PABFD-ARIMA | Predictive with AR(3) |
| A4 | P-PABFD-Oracle | Perfect predictor (upper bound) |

### 4.2 Prediction Accuracy Levels (3, for A2/A3)

| Level | p_accuracy | Description |
|-------|-----------|-------------|
| Low   | 0.50      | Noisy predictor |
| Med   | 0.75      | Realistic cloud workload ARIMA (per Calheiros 2015) |
| High  | 0.90      | Near-accurate predictor |

Note: Oracle (A4) is always accuracy=1.0.

### 4.3 Lookahead Horizons (3)

| Horizon | T_lookahead | Description |
|---------|-------------|-------------|
| Short   | 150 s       | 2.5 min lookahead |
| Medium  | 300 s       | 5 min lookahead (primary) |
| Long    | 600 s       | 10 min lookahead |

**Primary evaluation:** T_lookahead = 300 s, p_accuracy = 0.75

### 4.4 Churn Scenarios (3, same as Direction #2)

| Scenario | Churn rate | Expected avg utilization |
|----------|-----------|--------------------------|
| Low      | 10%/hr    | ~40-50% |
| Medium   | 20%/hr    | ~50-65% |
| High     | 40%/hr    | ~60-75% |

### 4.5 Run Matrix

**Primary runs (main result):** 5 algorithms × 3 scenarios × 10 seeds = **150 runs**

**Sensitivity runs (accuracy × horizon):** 
- A2/A3 × 3 accuracy levels × 3 horizons × 3 scenarios × 10 seeds = **540 runs**
- (Subset: 3 accuracy × 3 horizon × 3 scenario × 10 seed = 270 per algorithm)

**Total: 150 + 540 = 690 runs** (at ~0.1 s/run = ~69 s compute time, feasible)

If compute time is infeasible: reduce to primary runs (150) + accuracy sweep at primary
horizon (2 × 3 × 3 × 10 = 180) = **330 runs** as fallback.

---

## 5. Primary Metric

```
E_idle_saved = Σ_{events} P_idle × ΔT_early_shutdown   [J]
E_idle_saved_pct = E_idle_saved / E_total_PABFD × 100  [%]
```

Where `ΔT_early_shutdown` = time between proactive shutdown trigger and the time
PABFD would have fired the reactive trigger.

**Total energy comparison (primary table):**
```
E_total_DC = Σ_t Σ_{h ∈ active_hosts} P(u_h(t)) × Δt    [J]
```

Note: No PUE multiplier (that was Direction #2, now archived). Pure compute energy.

---

## 6. Secondary Metrics

| Metric | Formula | Why |
|--------|---------|-----|
| SLA violation rate | #overloaded_slots / #total_slots | Safety constraint |
| Avg early shutdown lead time (s) | mean(ΔT_early) per event | Mechanism check |
| False positive rate | #premature_shutdowns_with_SLA_cost / #shutdowns | Predictor quality |
| Migration count | total VM migrations | SLA overhead proxy |
| Energy savings vs. Oracle | (E_Oracle - E_policy) / (E_Oracle - E_PABFD) | Efficiency gap |

---

## 7. Dataset

Same synthetic Poisson workload from Direction #2:
- 10 hosts, HPE ProLiant DL360, P_max=250W, P_idle=100W
- Simulation: 3600 s, DT=60 s
- VM CPU demand: Gaussian(μ=0.6, σ=0.2), clamped [0.05, 1.0]
- VM arrival: Poisson(λ=0.01 VMs/s)
- VM lifetime: Exponential(mean=600 s)
- Seeds: 0–9 (fixed for reproducibility)

History buffer for predictor: last 20 timesteps (20 × 60 s = 20 min history)

---

## 8. Stopping Rule (Pre-Registered)

**Rule 1 — Null result:**  
If P-PABFD (any variant, primary accuracy=0.75, lookahead=300 s) does not improve
`E_total_DC` by > 2% over PABFD in any of 3 scenarios → null result confirmed.
- Log in LOGBOX.md → pivot to next brainstorm candidate

**Rule 2 — Proceed:**  
If ≥ 1 P-PABFD variant shows > 5% improvement in ≥ 2/3 scenarios (p < 0.05) →
proceed to full paper write-up + Azure trace validation.

**Rule 3 — Borderline (2–5%):**  
Run Azure trace (if available) or increase seeds to 20. Report conservative CI.

**Rule 4 — SLA disqualification:**  
If SLA violation rate of any P-PABFD variant exceeds PABFD by > 5 percentage points
(absolute), that variant is disqualified regardless of energy savings.

---

## 9. Pre-Registered Statistical Tests

- **Primary:** Paired t-test (paired by seed), PABFD vs. best P-PABFD, on `E_total_DC`
- **Alpha:** 0.05, two-tailed
- **Effect size:** Cohen's d
- **Sensitivity:** Report savings (%) vs. accuracy level and lookahead horizon as a 3×3 grid
- No post-hoc subgroup analysis beyond the pre-registered accuracy × horizon grid

---

## 10. Expected Contribution

**If H1 confirmed:**
1. First study to show that lightweight temporal prediction of host utilization, applied
   to the *underload detection* step of PABFD consolidation, reduces idle host energy
   by a meaningful margin
2. P-PABFD as a simple, drop-in modification requiring only utilization history (no
   additional sensors beyond what PABFD already uses)
3. Characterization of prediction accuracy vs. energy savings tradeoff
4. Null result from Direction #2 repurposed: "VM *placement* within active hosts is energy-
   neutral; *when* hosts are shut down is the real lever"

**Target venues (same as Direction #2):**
- IEEE Transactions on Cloud Computing
- Future Generation Computer Systems (Elsevier/Buyya)
- ACM/IEEE CCGrid 2026

---

## 11. Phase Exit Criteria

- [x] Protocol written and committed
- [x] Lit review complete (16 papers, novelty gap confirmed)
- [x] Falsification passed (3.4–13.6% recoverable)
- [ ] Baseline (PABFD) reproduces Direction #2 energy values ± 5%
- [ ] Metrics and stopping rule defined (above)
- [ ] Simulation run and primary results recorded

---

*Pre-registered by autonomous research agent on 2026-02-27.*
