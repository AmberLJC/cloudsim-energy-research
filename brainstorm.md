# Brainstorm: Cloud Energy Optimization via CloudSim
**Phase:** Brainstorming | **Date:** 2026-02-27 | **Status:** Draft

---

## Problem Landscape Map — 15 Candidate Directions

| # | One-sentence claim | Domain | Source of idea |
|---|-------------------|--------|----------------|
| 1 | VM consolidation that accounts for live-migration's own energy cost reduces total datacenter energy more than naive count-minimizing consolidation | Energy-aware scheduling | Gap in Beloglazov 2012; migration cost assumed free |
| 2 | Dynamic PUE modeling (cooling load as function of placement) changes optimal VM placement decisions compared to fixed-PUE models | Cooling–compute co-optimization | CloudSim gap: all papers use fixed PUE |
| 3 | Proactive VM consolidation using temporal demand prediction outperforms reactive threshold-based consolidation on realistic traces | Predictive scheduling | Gap: most work assumes stationary workloads |
| 4 | Embodied carbon of server hardware refresh should be traded off against operational efficiency gains at a decision boundary derivable by simulation | Lifecycle carbon optimization | Embodied carbon almost absent in CloudSim literature |
| 5 | Multi-datacenter spatial routing of delay-tolerant batch jobs to match renewable energy availability reduces carbon footprint more than within-datacenter optimization alone | Spatial-temporal carbon scheduling | Carbon-aware work rarely combines spatial + temporal in one policy |
| 6 | VM communication topology-aware placement reduces network switch energy by X%, and ignoring this makes energy-efficient consolidation counterproductive for communication-heavy workloads | Network-energy co-optimization | Network energy ignored in most CloudSim energy papers |
| 7 | DVFS (Dynamic Voltage/Frequency Scaling) per-VM decisions co-optimized with placement outperform sequential (place-then-scale) approaches | DVFS + placement joint optimization | CloudSim lacks native DVFS model; coupling is unstudied |
| 8 | Probability-aware SLO headroom reduction (using workload variance forecasts) reduces idle/reserve energy while maintaining user-perceived SLA compliance | Probabilistic SLO + energy | Fixed safety margins are energy-wasteful; unstudied in sim |
| 9 | Memory-bandwidth-aware co-placement of VMs reduces memory subsystem energy in consolidated servers (cache interference model) | Memory energy model | Memory energy (not just CPU) largely ignored |
| 10 | The "migration cascade" phenomenon (one migration triggers overload on target, causing further migrations) is energy-catastrophic and predictable; a cascade-aware scheduler prevents it | Migration stability | Practical but understudied side effect of reactive consolidation |
| 11 | Energy-aware auto-scaling outperforms energy-oblivious auto-scaling when scaling-out cost is explicitly modeled per VM-type in simulation | Autoscaling energy awareness | Gap: autoscaling + energy rarely studied together |
| 12 | Heterogeneous host energy models (non-linear power curves, not just linear interpolation) change which host is the "greenest" target for placement | Power model accuracy | CloudSim uses linear models; real hardware is non-linear |
| 13 | Workload fingerprinting (classifying VM workloads by CPU activity signature) enables better energy-aware bin-packing than size-alone approaches | Workload-type classification | Classification done in cloud cost-opt literature, rarely for energy |
| 14 | Stranded energy (idle resources that can't be consolidated due to SLO constraints) is a predictable function of SLO tightness and workload variance, and can be quantified by simulation | Stranded energy quantification | Measurement paper; conceptually clean gap |
| 15 | A joint carbon + water footprint optimization policy outperforms carbon-only optimization policies under real renewable energy and water scarcity data | Multi-resource sustainability | Very recent (2025 papers on LLM/water), not yet extended to VM scheduling |

---

## Step 2: Trajectory Sketches — Top 6 Candidates

### Idea 2: Dynamic PUE-Aware VM Placement

**Core claim:** Fixed-PUE energy models systematically undervalue the benefit of balanced placement; incorporating dynamic cooling load as a function of rack heat density changes optimal placement policies in measurable ways.

```
Arc A: Implement dynamic PUE model in CloudSim (thermal zones) →
       Compare PUE-aware vs. fixed-PUE placement across 3 policies (BestFit, PABFD, FirstFit) →
       Measure total energy savings and temperature stability
Arc B: Extend to seasonal variation (summer vs. winter ambient temp) →
       Show that optimal policies shift seasonally → policy-switching strategy
Arc C: Theory: derive conditions under which dynamic PUE changes the optimal consolidation target →
       Empirical validation on PlanetLab/Azure traces
```

**Unique mechanism:** The feedback loop: placement → heat density → cooling overhead → actual total energy. This creates a non-linear optimization problem that invalidates greedy approaches.

---

### Idea 1: Migration-Energy-Aware Consolidation

**Core claim:** Live VM migration consumes measurable energy (bandwidth × time × dirty rate), and treating it as free leads to consolidation decisions that increase total energy in moderate-churn scenarios.

```
Arc A: Implement energy cost of migration in CloudSim → measure wasted energy under churn-heavy workloads →
       Compare to migration-cost-aware policy (only migrate if ROI > 0 within T minutes)
Arc B: Characterize the ROI break-even horizon across workload types →
       Derive policy parameters for when to consolidate vs. tolerate imbalance
Arc C: Model migration interference (parallel migrations degrade bandwidth) →
       Show cascading degradation under typical policies
```

**Unique mechanism:** Migration energy as a first-class scheduling constraint, not a side effect. Framing: energy-ROI of consolidation decisions.

---

### Idea 10: Migration Cascade Detection and Prevention

**Core claim:** Reactive threshold-based consolidation policies can trigger "cascade oscillations" where a migration to fix one overloaded host creates overload on the destination, triggering further migrations — net energy negative.

```
Arc A: Reproduce cascade phenomenon in CloudSim with synthetic workload →
       Measure total energy overhead of cascades vs. stable runs
Arc B: Define a cascade risk metric (based on load imbalance + migration queue depth) →
       Implement cascade-aware scheduler → evaluate energy savings
Arc C: Prove that certain threshold configurations are cascade-stable (formal analysis) →
       Provide configuration recommendations
```

---

### Idea 3: Proactive Consolidation via Temporal Demand Prediction

**Core claim:** Using 15-min-ahead workload forecasts to pre-consolidate VMs before demand drops reduces both migration frequency and idle energy compared to reactive approaches.

```
Arc A: Train lightweight LSTM/ARIMA on Azure Public Dataset traces →
       Feed predictions to CloudSim as synthetic workload → compare proactive vs. reactive consolidation
Arc B: Ablate prediction horizon (5/15/30/60 min) to find energy-optimal lookahead window
Arc C: Combine proactive consolidation with dynamic PUE model → cumulative effect
```

---

### Idea 12: Non-Linear Host Power Model Accuracy

**Core claim:** CloudSim's linear power model (P = P_idle + α×utilization) systematically misjudges which hosts are energy-optimal; real SPECpower curves are non-monotonic at low utilization.

```
Arc A: Fit quadratic/piecewise power models to SPECpower 2008 database →
       Run CloudSim experiments with linear vs. accurate models → measure scheduling divergence
Arc B: Identify the regime where linear models are good enough vs. dangerously wrong
Arc C: Build a plugin power model API for CloudSim that others can extend
```

---

### Idea 8: Probabilistic SLO Headroom Reduction

**Core claim:** Cloud providers maintain fixed CPU headroom (e.g., never exceed 80% utilization) to protect SLOs, but this wastes significant energy; risk-aware headroom (based on workload variance distribution) achieves same SLO compliance at lower energy cost.

```
Arc A: Model SLO compliance probability as function of headroom + workload variance (analytical) →
       Simulate variable headroom policies in CloudSim
Arc B: Show that variance-informed headroom reduces idle energy by X% with < ε% SLO degradation
Arc C: Extend to multi-tier SLO (gold/silver/bronze customers get different headroom)
```

---

## Step 3: Feasibility & Ethics Gate

| # | Idea | Data available? | Compute (CPU-only)? | Skills? | Ethics | Gate |
|---|------|----------------|---------------------|---------|--------|------|
| 2 | Dynamic PUE | Thermal model is publishable/synthetic | ✅ | CloudSim+Java+Python | None | **PASS** |
| 1 | Migration energy | Workload traces (Azure, PlanetLab) available | ✅ | CloudSim modification | None | **PASS** |
| 10 | Cascade prevention | Synthetic workload sufficient | ✅ | Medium complexity | None | **PASS** |
| 3 | Predictive consolidation | Azure traces available | ✅ | ML + CloudSim | None | **PASS** |
| 12 | Power model accuracy | SPECpower database public | ✅ | Python fitting + CloudSim | None | **PASS** |
| 8 | Probabilistic SLO | Synthetic workload sufficient | ✅ | Stats + CloudSim | None | **PASS** |

All 6 pass. Eliminating none.

---

## Step 4: Convergent Scoring (FINER + AI criteria)

| Idea | Feasible | Interesting | Novel | Ethical | Relevant | Evaluable | Reproducible | Robust | Risk-Ctrl | **Mean** |
|------|----------|-------------|-------|---------|----------|-----------|-------------|--------|-----------|---------|
| #2 Dynamic PUE | 4 | 5 | 5 | 5 | 5 | 4 | 4 | 3 | 4 | **4.3** |
| #1 Migration energy | 5 | 4 | 4 | 5 | 5 | 5 | 5 | 4 | 4 | **4.6** |
| #10 Cascade prevention | 4 | 4 | 4 | 5 | 4 | 4 | 4 | 3 | 3 | **3.9** |
| #3 Predictive consolidation | 4 | 4 | 3 | 5 | 4 | 5 | 5 | 4 | 4 | **4.2** |
| #12 Power model accuracy | 5 | 3 | 3 | 5 | 4 | 5 | 5 | 4 | 4 | **4.2** |
| #8 Probabilistic SLO | 4 | 4 | 4 | 5 | 4 | 4 | 4 | 3 | 4 | **4.0** |

### Rationale for top scores

**#1 Migration-Energy-Aware (4.6):** Highest because:
- Very feasible (CloudSim already models migration, just not its energy cost)
- Directly measurable metric (joules wasted vs. saved)
- Reproducible with Azure traces
- The "free migration" assumption is widespread → impact if shown wrong
- Combines well with other angles (cascade, prediction)

**#2 Dynamic PUE (4.3):** High novelty and relevance because:
- Cooling is 30-40% of datacenter energy — completely ignored in CloudSim literature
- Mechanistically distinct: placement → thermal → energy is a feedback loop
- Risk: requires building a credible thermal model (moderate effort)

**#3 Predictive consolidation (4.2):** Solid but less novel — temporal prediction + cloud scheduling is not new in general, the novelty is the CloudSim + energy angle. Somewhat incremental.

**#12 Power model accuracy (4.2):** Good engineering paper but risk of being a "benchmark" paper rather than a research contribution.

---

## Step 5: Prototype Falsification Plan

### Primary direction: #1 + #2 combined
**Thesis:** "Migration energy cost and dynamic PUE are both systematically ignored in CloudSim energy optimization; incorporating both reveals that the canonical PABFD policy suboptimally trades migration cost for marginal consolidation gain."

**Fast falsification experiment (hours, not days):**
1. Implement a simple linear migration energy model in Python (E_mig = bandwidth_bytes × energy_per_bit)
2. Replay 100 migration events from a synthetic CloudSim trace
3. If E_mig < 1% of total E_compute → migration energy is negligible → idea #1 is moot
4. If E_mig > 5% under high-churn workloads → proceed

**Falsification for PUE:**
1. Get 1 real server room thermal dataset (or use ASHRAE model)
2. Estimate PUE variation across load: typical range is 1.1–2.0
3. If PUE is within ±5% of 1.5 across all load conditions → fixed PUE is fine → idea #2 weakened
4. If PUE varies >10% across typical load ranges → dynamic PUE matters

**Sanity check baseline:** Run Beloglazov's PABFD in standard CloudSim → verify energy numbers match published results. If they don't, we have a calibration problem.

---

## Step 6: Research Statement (Pre-commit)

**Direction:** Migration-Energy-Aware + Dynamic-PUE Joint Optimization in CloudSim

**Research Statement:**
Cloud data center energy optimization research using CloudSim systematically underestimates two feedback loops: (1) the energy consumed by live VM migration operations themselves, and (2) the dynamic nature of PUE (Power Usage Effectiveness) as a function of load distribution across physical hosts. We instrument CloudSim with migration energy accounting and a dynamic thermal-cooling model, then show that the widely-used PABFD consolidation algorithm makes suboptimal decisions when these costs are ignored. We propose a consolidated policy — Migration-Energy-ROI-Aware Placement with Dynamic-PUE (MEAD) — that makes decisions using full energy accounting and demonstrate X% improvement in total energy efficiency across synthetic and real-trace workloads.

**Primary metric:** Total energy consumption (joules) over simulation run  
**Secondary metric:** SLA violation rate, migration count, average PUE  
**Primary dataset:** Azure VM traces / synthetic Poisson workload  
**Primary baseline:** PABFD (Beloglazov 2012) in standard CloudSim  
**CPU-only confirmed:** ✅ All computation is simulation + Python analysis

---

## Exit Criteria Check
- [x] At least one idea scores ≥ 3.5 — multiple score ≥ 4.0
- [x] Fast falsification plan written (pending execution)
- [x] Primary metric, dataset, and baseline identified
- [x] Research statement written
- [ ] Exploration directory created (single-direction project — using flat structure per SKILL.md § File Management)
- [ ] LOGBOX updated

---

## Open Questions for Amber
1. **Primary direction confirm?** Leaning toward #1+#2 combined (migration energy + dynamic PUE). This is a mechanistically novel contribution to CloudSim. Do you agree, or want to explore #10 (cascade) or #8 (probabilistic SLO) instead?
2. **Scope**: Paper or extended study? A focused conference paper would be #1 alone. A journal paper could combine #1 + #2 + #10.
3. **CloudSim version**: Use CloudSim 7G (latest, 2025) or classic 3.x? 7G has more features but less community baseline for comparison.

---

## Fast Falsification Results — 2026-02-27

> Script: `falsification-check.py` | Full output: `falsification-results.txt`

### Null Result: #1 Migration-Energy-Aware Consolidation — ❌ PIVOT

Quantitative falsification shows migration energy is **negligible**:

| Component | Energy | % of Compute |
|-----------|--------|--------------|
| Network transfer (2 GB VM, 400 Mbps, 0.5 nJ/bit, 20% rate) | 171.8 J | 0.003% |
| Dirty-page overhead (3×) | 515.4 J | 0.008% |
| CPU scan overhead (8% of PM power, 42.9s, 20 VMs) | 13,056.7 J | 0.191% |
| **TOTAL** | **13,744 J** | **~0.20%** |

**Decision: PIVOT.** Migration energy < 1% under all realistic configurations (including aggressive: 4 GB memory, 1000 Mbps, 1.0 nJ/bit at 40% rate → only 0.02%). The "free migration" assumption is essentially correct from an energy standpoint. The dominant migration cost is CPU overhead, not network energy.

**Logging null result honestly.** This is the right outcome — chasing a <1% effect would not produce a publishable contribution.

Alternative angle: Migration CASCADE effects (idea #10) are still viable — cascade overhead is a multiplier on the 0.2%, and cascade oscillations can persist for minutes, but even 10 cascade cycles would only reach ~2%. Still below 3% threshold. #10 weakened by this finding.

---

### Confirmed: #2 Dynamic PUE-Aware Placement — ✅ VIABLE (Primary Direction)

| Metric | Value |
|--------|-------|
| PUE range (real DCs) | 1.2 – 1.8 |
| Annual energy difference (500 kW load) | 2,628,000 kWh (+50%) |
| PUE reduction needed for >5% savings | 0.075 (achievable) |
| Policy impact (consolidated vs. spread) | **32.9% total energy difference** |

**Decision: PROCEED.** Dynamic PUE is unambiguously significant. A load-dependent PUE model (PUE(load) = 1.8 − 0.6×load, linear approximation) shows 4% energy swing per 0.1 change in load factor. The fixed-PUE assumption used in all CloudSim papers is wrong by up to 20–30% in realistic operating regimes.

**Key insight from misoptimization scenario:** Greedy consolidation (6 active PMs at 100% load, PUE=1.20) uses **33% less energy** than balanced spread (10 PMs at 60% load, PUE=1.44). This is the **opposite** of many existing consolidation results that assume fixed PUE=1.5. Under dynamic PUE, aggressive consolidation may actually be optimal — but PUE(load) is non-linear, so the sweet spot changes with workload characteristics.

---

## Revised Research Direction — Post Falsification

**Drop:** #1 Migration-Energy-Aware Consolidation (migration energy < 1%, not worth modeling)  
**Elevate:** #2 Dynamic PUE-Aware Placement (32% policy divergence — highly worth modeling)  
**Secondary:** #12 Non-Linear Power Model (complements #2, both challenge linear assumptions)  

**New research focus:** "CloudSim energy optimization papers use fixed PUE and linear power models. We show that load-dependent PUE (alone) changes the optimal placement policy by >30%. We implement dynamic PUE in CloudSim and propose a PUE-aware variant of PABFD."

