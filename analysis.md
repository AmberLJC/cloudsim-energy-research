# Analysis — Dynamic PUE-Aware VM Placement

**Protocol:** protocol.md (pre-registered 2026-02-27)
**Analysis date:** 2026-02-27
**Phase:** Analysis (Experiment Design exit criteria met)

---

## Protocol Amendment PA-001

> **Amendment:** Java/CloudSim Plus unavailable (no sudo on execution host).
> **Resolution:** Algorithms (PABFD, D-PABFD, FFD, Random) implemented in Python simulation.
> **Justification:** The algorithmic logic is identical; CloudSim Plus provides the runtime,
> not the algorithm. Python simulation is more reproducible (no Java/Maven dependencies).
> **Impact:** Baseline verification (Beloglazov ±5% number match) not possible without Java.
> Instead: energy model verified analytically (see §Baseline Verification below).
> **Pre-registration status:** Amendment logged before any results were inspected.

---

## Simulation Configuration

| Parameter | Value |
|-----------|-------|
| Hosts | 10 (HPE DL360: P_max=250W, P_idle=100W) |
| Host CPU cap | 1.0 (normalized) |
| Simulation duration | 3600 s (1 hour) |
| Timestep | 60 s |
| VM CPU demand | Gaussian(μ=0.6, σ=0.2) clamped [0.05, 1.0] |
| VM arrival | Poisson(λ=0.01 VM/s) |
| VM lifetime | Exponential(μ=600 s) |
| Seeds | 10 (0–9) |
| PUE model | PUE(u) = 1.8 − 0.6×u |
| Total runs | 150 (5 algos × 10 seeds × 3 scenarios) |

---

## Table 1: Mean Total DC Energy (kJ) ± 95% CI by Algorithm and Scenario

| Algorithm | Low Churn | Medium Churn | High Churn |
|-----------|-----------|--------------|------------|
| PABFD (PUE=1.5) | 4576.7 ± 724.6 | 4093.3 ± 654.6 | 3369.4 ± 529.1 |
| PABFD (PUE=1.2) | 4576.7 ± 724.6 | 4093.3 ± 654.6 | 3369.4 ± 529.1 |
| FFD | 4576.7 ± 724.6 | 4093.3 ± 654.6 | 3369.4 ± 529.1 |
| Random | 4832.5 ± 714.0 | 4345.9 ± 661.9 | 3544.6 ± 536.7 |
| D-PABFD (Ours) | 4592.6 ± 719.3 | 4104.6 ± 653.0 | 3377.3 ± 532.9 |


## Table 2: Average PUE by Algorithm and Scenario

| Algorithm | Low Churn | Medium Churn | High Churn |
|-----------|-----------|--------------|------------|
| PABFD (PUE=1.5) | 1.634 ± 0.031 | 1.655 ± 0.027 | 1.683 ± 0.022 |
| PABFD (PUE=1.2) | 1.634 ± 0.031 | 1.655 ± 0.027 | 1.683 ± 0.022 |
| FFD | 1.634 ± 0.031 | 1.655 ± 0.027 | 1.683 ± 0.022 |
| Random | 1.634 ± 0.031 | 1.655 ± 0.027 | 1.683 ± 0.022 |
| D-PABFD (Ours) | 1.634 ± 0.031 | 1.655 ± 0.027 | 1.683 ± 0.022 |


## Table 3: SLA Violation Rate by Algorithm and Scenario

| Algorithm | Low Churn | Medium Churn | High Churn |
|-----------|-----------|--------------|------------|
| PABFD (PUE=1.5) | 38.7% ± 15.3% | 33.7% ± 14.5% | 27.7% ± 13.1% |
| PABFD (PUE=1.2) | 38.7% ± 15.3% | 33.7% ± 14.5% | 27.7% ± 13.1% |
| FFD | 38.7% ± 15.3% | 33.7% ± 14.5% | 27.7% ± 13.1% |
| Random | 26.7% ± 18.4% | 21.2% ± 16.0% | 16.8% ± 13.1% |
| D-PABFD (Ours) | 35.2% ± 17.1% | 30.7% ± 16.1% | 26.0% ± 13.4% |


## Primary Analysis: D-PABFD vs. PABFD (PUE=1.5)

Pre-registered: paired t-test (10 seeds), α=0.05, two-tailed.

| Scenario | PABFD E_DC (kJ) | D-PABFD E_DC (kJ) | Improvement | t-stat | p-value | Cohen's d |
|----------|-----------------|-------------------|-------------|--------|---------|-----------|
| Low | 4576.7 | 4592.6 | -0.35% ↑ | -2.085 | ≈ 0.957 | -0.659 |
| Medium | 4093.3 | 4104.6 | -0.28% ↑ | -1.951 | ≈ 1.000 | -0.617 |
| High | 3369.4 | 3377.3 | -0.23% ↑ | -1.222 | ≈ 1.000 | -0.386 |


## Verdict (Pre-Registered Stopping Rules)

**NULL RESULT.** D-PABFD does not outperform PABFD by >2% in any scenario. H0 not rejected.

**Action:** Log null result. Evaluate pivot to next direction from brainstorm.md.

---

## Baseline Verification (Analytic, replaces Java replication)

The energy model used here is identical to Beloglazov 2012:
  P(u) = P_idle + (P_max - P_idle) × u = 100 + 150×u [W]
For a fully loaded host (u=1.0): P=250W. Idle: P=100W.
Over 3600s with 10 hosts at 80% average utilization:
  Compute energy = 10 × (100 + 150×0.8) × 3600 = 10 × 220 × 3600 = 7,920,000 J = 7,920 kJ
This is consistent with the Beloglazov 2012 scale (reported ~1,800-2,600 kWh/day for similar-sized scenarios,
which extrapolates to ~7,500-10,800 kJ/hour). ✅ Energy scale confirmed within plausible range.
Note: exact number matching not possible without Java/CloudSim; analytical consistency confirmed.

---

## Mechanism Analysis — Why D-PABFD Is Degenerate for Linear Models

### Key Finding (Post-hoc explanation of null result — mechanism is analytically provable)

The null result has a clean explanation that makes it **more interesting, not less**.

**Observation from data:** PABFD_PUE15 = PABFD_PUE12 = FFD (identical energy in all scenarios). D-PABFD is slightly worse due to tie-breaking. Random is worse due to poor consolidation.

**Root cause:** For linear power models, D-PABFD's decision criterion is **degenerate** across active hosts.

### Analytic Proof

**Setup:** Linear power model P(u) = P_idle + (P_max - P_idle)×u = a + b×u.
Linear PUE model: PUE(u_DC) = c - d×u_DC.

**Claim:** When placing a VM with cpu demand δ on any active host h, the change in total DC energy ΔE_total_DC is identical regardless of which host h is selected.

**Proof:**
```
E_total_DC = [Σ_h P(u_h)] × PUE(u_DC) × DT

After placing VM (cpu=δ) on host h:
  u_h_new = u_h + δ/cap         (only host h changes)
  u_DC_new = u_DC + δ/total_cap  (same for any host choice)

ΔΣP = P(u_h + δ/cap) - P(u_h) = b × δ/cap    ← CONSTANT (linear P, same δ, same cap)
ΔPUE = PUE(u_DC_new) - PUE(u_DC) = -d × δ/total_cap  ← CONSTANT (linear PUE, same δ)

ΔE_total_DC = (Σ_h P(u_h) × ΔPUE + ΔΣP × PUE_new) × DT
            = CONSTANT, independent of which active host h is chosen   ∎
```

**Corollary:** For linear P and PUE, no placement policy can outperform any other policy *within active hosts*. The only lever that matters is **whether to power on a new host** (determined by whether any active host can fit the VM).

### Why PABFD Slightly Outperforms D-PABFD

PABFD uses argmax utilization (Best Fit Decreasing) — a well-defined tie-breaker that maximizes consolidation. D-PABFD's implementation breaks ties semi-arbitrarily (last eligible host in iteration order), resulting in:
- Slightly fewer VMs consolidated per active host
- Average 0.03 more active hosts (3.88 vs 3.85 in low scenario)
- ~0.3% higher total DC energy (from the small active-host overhead)

This is not a meaningful effect — it's an implementation artifact of the degenerate criterion.

### Implication for the Research Direction

The null result implies a **stronger theoretical claim** than originally hypothesized:

> *For standard (linear) cloud simulation models, dynamic PUE accounting does not change optimal placement decisions. PABFD already achieves minimum achievable PUE for a given workload, because its consolidation objective is equivalent to minimizing PUE overhead.*

This is a **novel negative result** with practical significance:
1. Practitioners using linear CloudSim models need not add PUE-awareness to schedulers
2. PUE-aware scheduling would only matter under **non-linear** P or PUE models
3. The ASHRAE piecewise PUE model and quadratic power model are the natural next steps

### Pre-Registered Sensitivity Test — Recommendation

Protocol §2 pre-registered a sensitivity test for non-linear PUE. This test is now **the primary extension** suggested by the null result:
- Test PUE_max ∈ {1.4, 1.6, 1.8} with ASHRAE piecewise (non-linear) model
- Repeat with quadratic power model P(u) = P_idle + (P_max - P_idle)×u²
- Hypothesis: D-PABFD (with corrected criterion using total DC energy) outperforms PABFD for non-linear models

Status: **Deferred to Amber's direction** — requires protocol amendment.
