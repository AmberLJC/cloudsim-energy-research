# Research Protocol — Dynamic PUE-Aware VM Placement in CloudSim

**Status:** PRE-REGISTERED (locked after brainstorm exit)  
**Date locked:** 2026-02-27  
**Author:** Research Agent (cloudsim-research-worker)  
**Phase:** Brainstorm → Protocol (Task 3 complete)  
**Supersedes:** Research Statement in brainstorm.md §6  

> ⚠️ **Pre-registration principle:** This protocol is written before implementation begins. Any deviation from the analysis plan below must be documented as a protocol amendment with a reason. No cherry-picking of metrics or conditions after seeing results.

---

## 1. Locked Hypothesis

**Primary hypothesis (H1):**  
> "The fixed-PUE assumption used in CloudSim-based VM placement algorithms causes measurable misjudgment of optimal placement policy. A load-dependent dynamic PUE model, when incorporated into the placement decision function, yields lower total datacenter energy (compute + cooling) than the standard PABFD policy over the same workload trace."

**Secondary hypothesis (H2):**  
> "The direction of the PABFD misjudgment (consolidation vs. spreading) depends on the operating load regime: under moderate-to-high load, consolidation is more energy-efficient when PUE(load) is accounted for; under very-low load, PUE may penalize consolidation due to hotspot cooling costs."

**Null hypothesis (H0):**  
> "Dynamic PUE modeling does not change optimal placement decisions by more than 2% total energy vs. fixed-PUE PABFD over the evaluation scenarios."

**Falsification threshold:** If our proposed policy improves total energy by < 2% over PABFD in all scenarios, the null hypothesis holds. We will report this as a null result.

---

## 2. PUE Model Definition (Locked)

**Primary model (linear approximation, ASHRAE-inspired):**

```
PUE(u) = PUE_max - (PUE_max - PUE_min) × u
```

where:
- `u` = average CPU utilization across all active hosts (0–1)
- `PUE_max` = 1.8 (PUE at zero load — typical poor-cooling scenario)
- `PUE_min` = 1.2 (PUE at 100% load — efficient high-density cooling)
- Default parameters: PUE_max=1.8, PUE_min=1.2

**Sensitivity test (pre-registered):**
- We will additionally test `PUE_max` ∈ {1.4, 1.6, 1.8} and `PUE_min` ∈ {1.1, 1.2, 1.3}
- If H1 only holds for extreme PUE ranges (e.g., PUE_max=1.8, PUE_min=1.1), we will report the boundary conditions.

**Energy model:**
```
E_total = Σ_t [ P(u_t) × PUE(u_t) × Δt ]
```
where `P(u_t) = P_idle + (P_max - P_idle) × u_t` (standard CloudSim linear model).

---

## 3. Proposed Algorithm (D-PABFD)

**Dynamic PUE-Aware Best Fit Decreasing (D-PABFD):**

Standard PABFD selects the host that maximizes utilization after VM placement (Best Fit Decreasing on CPU). Our modification: replace the selection criterion with **total energy cost per unit of accepted VM work**, accounting for PUE.

```
Standard PABFD: select host h = argmax_h (util_after_placement(h))
D-PABFD: select host h = argmin_h [ ΔE_compute(h) × PUE(û_datacenter_after) ]
```

where `û_datacenter_after` is the predicted average datacenter utilization after placing the VM on host `h`, and `ΔE_compute(h)` is the incremental compute energy.

**Key insight:** D-PABFD prefers the host that minimizes the *marginal total energy* including the PUE change, not just the compute energy. When the PUE model is linear, consolidating increases `û`, which lowers PUE, which *reduces the PUE multiplier* — creating a virtuous cycle. D-PABFD explicitly rewards this.

---

## 4. Primary Metric

**Total datacenter energy (J) over simulation window:**

```
E_total_DC = Σ_{t=0}^{T} [ Σ_{h ∈ active_hosts} P(u_h(t)) × PUE(u_DC(t)) × Δt ]
```

- `u_h(t)` = utilization of host h at time t
- `u_DC(t)` = average utilization across all hosts at time t
- `PUE(u_DC(t))` = dynamic PUE at time t (function of average load)
- Active hosts = hosts with at least one running VM

**Why this metric:** Total DC energy is the operationally meaningful metric (power bill, carbon footprint). All existing papers report compute-only energy; we report true DC energy. This also makes the comparison meaningful: PABFD's "savings" may shrink or reverse when cooling overhead is correctly counted.

---

## 5. Secondary Metrics

| Metric | Purpose |
|--------|---------|
| SLA violation rate | Confirm we don't sacrifice SLA for energy |
| Average PUE over simulation | Show the mechanism works |
| Number of VM migrations | Confirm migration cost is indeed negligible |
| Energy per unit of VM-time delivered | Efficiency metric (energy × SLA_compliance) |
| Active host count over time | Understand consolidation behavior |

---

## 6. Baselines

| Baseline | Description | Why included |
|----------|-------------|--------------|
| **PABFD (fixed PUE=1.5)** | Beloglazov 2012. Standard, fixed PUE=1.5 assumed. | Primary baseline; most-cited |
| **PABFD (fixed PUE=1.2)** | Same algorithm, optimistic PUE assumption. | Tests sensitivity to PUE constant choice |
| **FirstFit Decreasing (FFD)** | Simple baseline. Greedy first-fit by CPU. | Lower bound on sophistication |
| **Random placement** | VMs placed randomly (no energy objective). | Upper bound on waste |
| **D-PABFD (our proposal)** | Dynamic PUE-aware modification. | Proposed algorithm |

All baselines use **identical workload traces, same CloudSim Plus configuration, same host hardware parameters.** Randomness seeds are fixed and reported.

---

## 7. Dataset

### Primary: Synthetic Poisson Workload

**Purpose:** Maximum reproducibility; allows controlled sweep of load levels.

Parameters:
- Number of VMs: 100
- Number of physical hosts: 10
- Simulation duration: 3600 s (1 hour), 10 repetitions
- VM CPU demand: Gaussian, μ=0.6, σ=0.2, clamped to [0.05, 1.0]
- VM arrival: Poisson(λ=0.01 VM/s) — 36 arrivals/hour on average
- VM lifetime: Exponential(μ=600 s) — mean 10 minutes
- Host config: HPE ProLiant DL360 model, P_max=250W, P_idle=100W, 4 CPU, 8 GB RAM
- Churn scenarios: {Low: 10%, Medium: 20%, High: 40%} VM replacement rate per hour

**Outputs:** 10 seeds × 5 algorithms × 3 load scenarios = 150 simulation runs

### Secondary: Azure VM Trace (if available)

Azure VM traces from the Reliability Lab (2017/2019 public dataset) or PlanetLab traces from the original Beloglazov experiments.

**If unavailable:** Replace with synthetic trace with higher workload variance (coefficient of variation = 0.4) to simulate realistic burstiness.

### Pre-registration note on data:
If the Azure trace is used, we will use only the first 24 hours of trace data. No cherry-picking of trace windows. If the synthetic trace produces null results but the Azure trace does not (or vice versa), both will be reported separately.

---

## 8. Implementation Plan

### Phase 1: CloudSim Plus Extension (Week 1)

1. Add `DynamicPUEModel` class to CloudSim Plus:
   - Interface: `getPUE(double avgDatacenterUtil) → double`
   - Implementation: `LinearDynamicPUEModel(double pueMin, double pueMax)`
   - Alternative: `ASHRAE2021PUEModel` (piecewise, from published ASHRAE data)

2. Modify energy accounting in `DatacenterBroker` / `CloudletScheduler`:
   - Replace `E = P(u) × Δt` with `E = P(u) × PUE(u_DC) × Δt`

3. Implement D-PABFD:
   - Extend `VmAllocationPolicyBestFitDecreased`
   - Override `findHostForVm()` to use marginal total energy criterion

4. Verification: Run PABFD on Beloglazov's original 800-VM scenario. Check that compute-only energy matches published results within ±5%.

### Phase 2: Experiments (Week 2)

5. Run all 150 simulation conditions (150 × ~2 min each = ~5 CPU-hours)
6. Record all metrics to CSV

### Phase 3: Analysis (Week 3)

7. Primary analysis: Compare E_total_DC across algorithms. Report mean ± 95% CI.
8. Stopping rule (see §9 below).
9. Sensitivity analysis: PUE parameter sweep.
10. Visualization: PUE over time, energy breakdown (compute vs. cooling).

---

## 9. Stopping Rule (Pre-registered)

**Rule 1 — Null result pivot:** If D-PABFD does not outperform PABFD by more than 2% on E_total_DC in any of the 3 synthetic load scenarios (Low/Medium/High churn), we declare the null hypothesis not rejected. We will write up the null result as: "Dynamic PUE Modeling Fails to Change Optimal VM Placement Decisions in CloudSim Simulations."

**Rule 2 — Confirmation stop:** If D-PABFD shows >5% improvement in E_total_DC in at least 2 of 3 scenarios (with p < 0.05, paired t-test across seeds), we proceed to write the full paper.

**Rule 3 — Protocol amendment required if:** We change the PUE model parameters, the VM workload distribution, the number of hosts/VMs, or the algorithm definition after seeing any result. All amendments must be documented in LOGBOX.md with a pre-registration timestamp.

---

## 10. Pre-Registered Analysis Plan

**Statistical tests:**
- Primary: Paired t-test (10 seeds, paired by seed), PABFD vs. D-PABFD, on E_total_DC
- Alpha = 0.05, two-tailed. No multiple-comparison correction (primary analysis is a single comparison).
- For secondary metrics: Bonferroni correction for 5 secondary metrics → α = 0.01

**Effect size reporting:** Cohen's d for all reported comparisons.

**Tables:** 
- Table 1: Mean ± SD of E_total_DC for each algorithm × scenario
- Table 2: SLA violation rate for each algorithm × scenario
- Table 3: Sensitivity to PUE parameters (PUE_max × PUE_min grid)

**Figures:**
- Figure 1: Time-series of PUE and total energy under each algorithm
- Figure 2: Boxplot of E_total_DC across seeds per algorithm
- Figure 3: Active host count + average utilization over time

**No post-hoc subgroup analysis unless pre-registered here.** Exception: if workload traces reveal temporal structure (e.g., diurnal patterns in Azure trace), we will report a time-stratified analysis as an appendix.

---

## 11. Threat Mitigation

| Threat | Mitigation |
|--------|-----------|
| Linear PUE model too simplistic | Also test ASHRAE piecewise model in sensitivity section |
| CloudSim doesn't model real datacenter cooling physics | Explicitly frame as a *simulation study* with cited PUE empirical range |
| Results don't generalize to real workloads | Use Azure traces as secondary dataset |
| D-PABFD has higher SLA violations | Report SLA as co-primary metric; algorithm is disqualified if SLA > PABFD |
| Implementation errors in D-PABFD | Verification step: match Beloglazov published numbers |

---

## 12. Expected Contribution

If H1 is confirmed:

1. **First CloudSim study** to show that fixed-PUE assumption changes the ranking of VM placement policies
2. **D-PABFD** as a simple, drop-in modification to PABFD requiring no additional sensors or data
3. **Open-source implementation** in CloudSim Plus (PR to main repository)
4. **Quantified boundary conditions** under which dynamic PUE matters vs. can be ignored

Target venues:
- **Primary:** IEEE Transactions on Cloud Computing (TCC) — high-impact, relevant audience
- **Alternative:** Future Generation Computer Systems (FGCS) — Buyya's home venue, broader reach
- **Conference (faster):** ACM/IEEE CCGrid or ICDCS

---

## 13. Phase Exit Criteria (to enter IMPLEMENTATION phase)

- [x] Protocol written and committed
- [x] Literature review complete
- [x] Falsification passed for #2 (dynamic PUE)
- [x] Novelty gap confirmed (no prior CloudSim + dynamic PUE paper)
- [ ] Beloglazov replication test passed (±5% energy match) — deferred to Phase 1
- [ ] Git tag `protocol-locked` applied

---

*This protocol was written by the autonomous research agent on 2026-02-27 and is considered pre-registered as of the first git commit containing this file.*
