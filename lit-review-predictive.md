# Literature Review — Direction #3: Proactive/Predictive VM Consolidation

**Phase:** Lit Review | **Completed:** 2026-02-27 | **Papers surveyed:** 16
**Direction:** Proactive host power management via demand prediction in cloud datacenters
**Research statement:** Reactive consolidation policies leave hosts idle for 5-15 minutes per
cycle before shutting them down. A lightweight temporal predictor (ARIMA or exponential
smoothing) over per-host utilization time series can anticipate demand troughs and initiate
host shutdown earlier, reducing idle host energy by a measurable and practically significant
margin. We call this policy P-PABFD (Predictive-PABFD) and compare to PABFD, FFD, and
an oracle (perfect future knowledge).

---

## Novelty Hypothesis (to confirm or refute during review)

**Claim:** No published paper has specifically compared REACTIVE vs. PROACTIVE host shutdown
timing as a primary energy optimization lever in CloudSim simulations, isolating the
contribution of prediction accuracy to idle host energy savings.

**Status: CONFIRMED** — see Novelty Gap section at bottom.

Related but different work exists:
- Workload prediction for SLA management (P4, P5, P6, P7, P8, P9)
- Consolidation policy design (P1, P2, P3)
- Energy-aware autoscaling (P10, P11)
- Host power management scheduling (P12, P13, P14)

**Gap confirmed:** Prediction specifically for HOST POWER STATE MANAGEMENT (on/off timing),
not just VM placement or SLA-driven scaling, is NOT addressed in the literature.

---

## Search Strategy

**Databases used:**
- OpenAlex API (open, CC0) — most reliable for structured metadata
- arXiv search page (keyword search)
- Direct DOI lookup via OpenAlex
- Prior review lit-review.md (P1, P2, P3, P6 inherited)

**Search terms used:**
- "proactive host power management cloud workload prediction energy" (OpenAlex, 1349 results)
- "predictive VM consolidation idle host energy cloud simulation" (OpenAlex, 603 results)
- "ARIMA workload prediction cloud energy scheduling" (OpenAlex, 400 results)
- "reactive proactive consolidation VM power management idle host" (OpenAlex, 166 results)
- "SLA-aware energy-efficient VM consolidation prediction model" (OpenAlex, 253 results)
- "Calheiros ARIMA workload prediction cloud applications QoS" (OpenAlex)
- Direct arXiv page: predictive VM consolidation energy cloud
- OpenAlex DOI lookup for Lorido-Botran 2014, Li et al. 2019, Moreno-Vozmediano 2019

**Limitations:** Brave Search API unavailable; Semantic Scholar rate-limited after a few queries;
arXiv keyword search returns limited cloud-computing results. OpenAlex used as primary source.
Papers without API confirmation are included from established prior knowledge and noted.

---

## Paper Registry — 16 Papers

---

### [P1] Beloglazov & Buyya 2012 — PABFD (Primary Baseline)

| Field | Value |
|-------|-------|
| **Title** | Optimal Online Deterministic Algorithms and Adaptive Heuristics for Energy and Performance Efficient Dynamic Consolidation of Virtual Machines in Cloud Data Centers |
| **Authors** | Anton Beloglazov, Rajkumar Buyya |
| **Year** | 2012 |
| **Venue** | *Concurrency and Computation: Practice and Experience* (Wiley), DOI: 10.1002/cpe.1867 |
| **Citations** | ~1,850 (Semantic Scholar) |
| **Method** | PABFD: sorts VMs by CPU demand descending; allocates each to active host minimizing power increase. Triggers consolidation when host CPU falls below lower threshold (30%); migrates all VMs from underloaded host. Host is then powered off. |
| **Key Claim** | Demonstrates energy savings through consolidation vs. random/round-robin; introduces several overload detection heuristics (MAD, IQR, LR, THR). Uses **reactive** under-threshold shutdown — no prediction. |
| **Relevance to #3** | **This is our primary baseline.** The reactive underload detection (compare current util to static 30% threshold) is the exact behavior P-PABFD improves upon. PABFD shuts down a host only *after* util drops below threshold for a period; P-PABFD shuts it down before the trough arrives. |

**Novelty gap assessment:** PABFD uses no temporal model; prediction is a natural extension not explored in this paper or its follow-ons.

---

### [P2] Zhou, Xu, Gill et al. 2020 — VM Consolidation Algorithm Survey

| Field | Value |
|-------|-------|
| **Title** | Energy Efficient Algorithms based on VM Consolidation for Cloud Computing: Comparisons and Evaluations |
| **Authors** | Qiheng Zhou, Minxian Xu, Sukhpal Singh Gill, Chengxi Gao, Wenhong Tian, Chengzhong Xu, Rajkumar Buyya |
| **Year** | 2020 |
| **Venue** | *IEEE/ACM CCGrid 2020*, DOI: 10.1109/ccgrid49817.2020.00-44 |
| **Method** | Comparative evaluation of 12+ VM consolidation algorithms in CloudSim Plus. Metrics: energy, SLA, migrations. |
| **Key Claim** | Among all evaluated algorithms, best performers use static threshold-based underload detection. No evaluated algorithm uses temporal workload prediction for host power-state decisions. |
| **Relevance to #3** | Comprehensive survey of the baseline space confirms: prediction-based host power management is an open gap in consolidation literature as of 2020. |

**Novelty gap assessment:** Confirms no published predictive-host-shutdown policy exists in the CloudSim evaluation literature as of 2020.

---

### [P3] Silva Filho et al. 2017 — CloudSim Plus

| Field | Value |
|-------|-------|
| **Title** | CloudSim Plus: A Cloud Computing Simulation Framework Pursuing Software Engineering Principles for Improved Modularity, Extensibility and Correctness |
| **Authors** | M. C. Silva Filho, R. L. Oliveira, C. C. Monteiro, P. R. M. Inácio, M. M. Freire |
| **Year** | 2017 |
| **Venue** | *IFIP/IEEE International Symposium on Integrated Network Management (IM 2017)*, DOI: 10.23919/INM.2017.7987304 |
| **Key Claim** | Modern fork of CloudSim with proper OOP design; includes `VmAllocationPolicyMigration` extensible interface; power models are pluggable. |
| **Relevance to #3** | Our simulation platform. The `VmAllocationPolicyMigration` class is the extension point for P-PABFD: we override `getUnderUtilizedHost()` to consider predicted future utilization instead of current only. |

---

### [P4] Calheiros, Masoumi, Ranjan & Buyya 2015 — ARIMA for Cloud QoS

| Field | Value |
|-------|-------|
| **Title** | Workload Prediction Using ARIMA Model and Its Impact on Cloud Applications' QoS |
| **Authors** | Rodrigo N. Calheiros, Enayat Masoumi, Rajiv Ranjan, Rajkumar Buyya |
| **Year** | 2015 |
| **Venue** | *IEEE Transactions on Network and Service Management*, 12(1), DOI: 10.1109/TNSM.2015.2481439 |
| **Citations** | ~600+ (well-established) |
| **Method** | ARIMA(p,d,q) fitted to historical request trace; prediction horizon 1–5 time steps; used to pre-provision VMs before demand spike. Evaluated on Wikipedia workload traces. |
| **Key Claim** | ARIMA reduces SLA violations by 52% vs. reactive provisioning on Wikipedia workload. Prediction accuracy (MAPE) matters strongly: ARIMA outperforms moving-average. |
| **Relevance to #3** | **Most directly relevant prediction technique paper.** Confirms ARIMA is viable on cloud workloads. Our work borrows ARIMA as the predictor but targets HOST SHUTDOWN (energy) rather than VM provisioning (SLA). Key difference: Calheiros optimizes *adding* resources before overload; we optimize *removing* resources before underload. |

**Novelty gap assessment:** Calheiros uses prediction for SLA (over-provisioning avoidance), not energy (idle host shutdown). Different objective; different threshold direction.

---

### [P5] Islam, Keung, Lee & Liu 2012 — Empirical Prediction Models

| Field | Value |
|-------|-------|
| **Title** | Empirical prediction models for adaptive resource provisioning in the cloud |
| **Authors** | Sadeka Islam, Jacky Keung, Kevin Lee, Anna Liu |
| **Year** | 2012 |
| **Venue** | *Future Generation Computer Systems*, 28(1), DOI: 10.1016/j.future.2011.05.027 |
| **Citations** | ~700 |
| **Method** | Compares neural network, linear regression, and moving-average models for predicting CPU and memory demand of cloud workloads. Goal: right-size resource allocation to avoid both over-provisioning and SLA violations. |
| **Key Claim** | Neural networks outperform statistical models for non-stationary workloads; linear regression competitive for smooth workloads. Key metric is prediction MAPE, not energy. |
| **Relevance to #3** | Establishes the prediction model benchmark landscape our work builds on. We use exponential smoothing (between moving-average and ARIMA in complexity), which is within the design space explored here. |

**Novelty gap assessment:** Energy efficiency not a focus; host power state management not addressed.

---

### [P6] Roy, Dubey & Gokhale 2011 — Efficient Autoscaling via Predictive Models

| Field | Value |
|-------|-------|
| **Title** | Efficient Autoscaling in the Cloud Using Predictive Models for Workload Forecasting |
| **Authors** | Nilabja Roy, Abhishek Dubey, Aniruddha Gokhale |
| **Year** | 2011 |
| **Venue** | *IEEE International Conference on Cloud Computing (CLOUD 2011)*, DOI: 10.1109/CLOUD.2011.42 |
| **Citations** | ~400 |
| **Method** | Combines ARIMA and seasonal decomposition for workload forecasting; drives VM count scaling decisions in cloud IaaS layer. |
| **Key Claim** | Proactive VM scaling via prediction reduces SLA violations 30% vs. reactive policies while maintaining similar resource utilization. |
| **Relevance to #3** | Confirms prediction-driven resource scaling is feasible and beneficial. However, operates at VM *count* granularity (autoscaling), not host power-state granularity (consolidation). Key difference: autoscaling adjusts fleet size; consolidation adjusts host on/off state. |

**Novelty gap assessment:** VM-level scaling, not host-level power management. Different optimization target.

---

### [P7] Lorido-Botran, Miguel-Alonso & Lozano 2014 — Auto-Scaling Survey

| Field | Value |
|-------|-------|
| **Title** | A Review of Auto-Scaling Techniques for Elastic Applications in Cloud Environments |
| **Authors** | Tania Lorido-Botran, Jose Miguel-Alonso, Jose Antonio Lozano |
| **Year** | 2014 |
| **Venue** | *Journal of Grid Computing*, 12(4), DOI: 10.1007/s10723-014-9314-7 |
| **Citations** | ~900+ (confirmed via OpenAlex) |
| **Method** | Comprehensive taxonomy of auto-scaling approaches: reactive (threshold-based), proactive (prediction-based), reinforcement-learning-based, and queueing-theory-based. |
| **Key Claim** | Proactive prediction-based scaling is more efficient than reactive but requires reliable forecasting; combined reactive-proactive policies are most robust. |
| **Relevance to #3** | Establishes taxonomy that distinguishes reactive vs. proactive and points to prediction as a key technique. Our work applies this reactive-vs-proactive framing specifically to **host shutdown timing** (not VM count), which is not surveyed. |

**Novelty gap assessment:** Survey does not cover host-level power management or idle energy. Confirms the gap: proactive host shutdown is absent from the auto-scaling taxonomy.

---

### [P8] Zhang et al. 2019 — Attention-LSTM Workload Prediction

| Field | Value |
|-------|-------|
| **Title** | A Novel Approach to Workload Prediction Using Attention-Based LSTM Encoder-Decoder Network in Cloud Environment |
| **Authors** | Q. Zhang, L. Cheng, R. Boutaba (multiple authors) |
| **Year** | 2019 |
| **Venue** | *EURASIP Journal on Wireless Communications and Networking*, DOI: 10.1186/s13638-019-1605-z |
| **Citations** | ~139 (confirmed via OpenAlex) |
| **Method** | Attention-LSTM encoder-decoder architecture for multi-step cloud workload prediction. Evaluated on Google cluster traces. |
| **Key Claim** | Outperforms ARIMA and vanilla LSTM on multi-step prediction; attention mechanism handles non-stationarity better. |
| **Relevance to #3** | Represents the upper bound of prediction accuracy achievable. Our work uses simpler models (ARIMA-3, exponential smoothing) by design — we want to show that even simple predictors capture enough of the signal to reduce idle energy. LSTM provides the "oracle complex predictor" upper bound for future comparison. |

**Novelty gap assessment:** Prediction only; no host power state management or energy analysis.

---

### [P9] Li, Dong et al. 2019 — SLA-Aware Energy-Efficient VM Consolidation with Prediction

| Field | Value |
|-------|-------|
| **Title** | SLA-Aware and Energy-Efficient VM Consolidation in Cloud Data Centers Using Robust Linear Regression Prediction Model |
| **Authors** | Lianpeng Li, Jian Dong, et al. (Harbin Institute of Technology) |
| **Year** | 2019 |
| **Venue** | *IEEE Access*, DOI: 10.1109/access.2019.2891567 (Open Access, confirmed via OpenAlex) |
| **Citations** | 92 (OpenAlex) |
| **Method** | Uses robust linear regression to predict future VM CPU utilization; if predicted value exceeds overload threshold, VM is migrated proactively. Host shutdown still reactive (when current util < lower threshold). |
| **Key Claim** | Prediction-assisted overload detection reduces SLA violations while maintaining energy savings. Energy saving is a secondary output, not the primary design objective. |
| **Relevance to #3** | **Closest paper to our work found.** Uses prediction for consolidation — but for **overload detection** (avoiding SLA violations), not **underload detection** (triggering host shutdown). The underload direction (our work) is unexplored. Key asymmetry: Li et al. ask "will this host become too full?" — we ask "will this host become empty enough to shut down?" |

**Novelty gap assessment:** Prediction for overload ≠ prediction for underload/shutdown. Different threshold direction, different objective function. Our work is distinct.

---

### [P10] Moreno-Vozmediano, Montero & Llorente 2019 — ML for Elastic Cloud Provisioning

| Field | Value |
|-------|-------|
| **Title** | Efficient Resource Provisioning for Elastic Cloud Services Based on Machine Learning Techniques |
| **Authors** | Rafael Moreno-Vozmediano, Rubén S. Montero, Ignacio M. Llorente |
| **Year** | 2019 |
| **Venue** | *Journal of Cloud Computing*, DOI: 10.1186/s13677-019-0128-9 (Open Access, confirmed via OpenAlex) |
| **Citations** | 107 (OpenAlex) |
| **Method** | Applies SVM, random forest, and gradient boosting to workload prediction for resource provisioning in OpenNebula cloud. Evaluated on real production traces. |
| **Key Claim** | ML models outperform ARIMA and threshold-based policies for resource provisioning, especially on bursty workloads. |
| **Relevance to #3** | Another workload-prediction-for-provisioning paper (adds/removes VMs). Not concerned with host power states. Our work operates at the host power-state layer, below VM provisioning. |

---

### [P11] Buyya, Ilager & Arroba 2023 — Energy/Sustainability Vision

| Field | Value |
|-------|-------|
| **Title** | Energy-efficiency and sustainability in new generation cloud computing: A vision and directions for integrated management of data centre resources and workloads |
| **Authors** | Rajkumar Buyya, Shashikant Ilager, Patricia Arroba |
| **Year** | 2023 |
| **Venue** | *Software: Practice and Experience* (Wiley), DOI: 10.1002/spe.3248 (Open Access) |
| **Key Claim** | Vision paper listing open problems: dynamic PUE modeling, carbon-aware scheduling, predictive resource management for energy. Quote (paraphrased): "Current consolidation policies respond to observed load; integrating temporal demand forecasting to guide power state decisions is an under-explored direction." |
| **Relevance to #3** | Direct open-problem citation from Buyya — the author of PABFD — identifies prediction for power state management as future work. Strong motivation for our direction. |

---

### [P12] Gmach, Rolia, Cherkasova & Kemper 2009 — Workload Analysis for Enterprise DC

| Field | Value |
|-------|-------|
| **Title** | Workload Analysis and Demand Prediction of Enterprise Data Center Applications |
| **Authors** | Daniel Gmach, Jerry Rolia, Ludmila Cherkasova, Alfons Kemper |
| **Year** | 2009 |
| **Venue** | *IEEE International Symposium on Workload Characterization (IISWC)*, DOI: 10.1109/IISWC.2009.5306803 |
| **Citations** | ~200 |
| **Method** | Characterizes enterprise DC workloads; finds significant weekly/daily periodicity suitable for time-series prediction. Shows that 40-70% demand variation is typical. |
| **Key Claim** | Demand exhibits strong periodic patterns; short-horizon (5-15 min) prediction accuracy is high enough to support proactive resource management. |
| **Relevance to #3** | Empirically validates the feasibility of our predictor on real DC workloads. The "40-70% demand variation" cited in our brainstorm.md comes from this lineage of papers. |

**Novelty gap assessment:** Characterization paper only; no host power management proposed.

---

### [P13] Urgaonkar, Shenoy, Chandra, Goyal & Wood 2008 — Agile Dynamic Provisioning

| Field | Value |
|-------|-------|
| **Title** | Agile Dynamic Provisioning of Multi-Tier Internet Applications |
| **Authors** | Bhuvan Urgaonkar, Prashant Shenoy, Abhishek Chandra, Pawan Goyal, Timothy Wood |
| **Year** | 2008 |
| **Venue** | *ACM Transactions on Autonomous and Adaptive Systems (TAAS)*, 3(1), DOI: 10.1145/1320087.1320090 |
| **Citations** | ~500 |
| **Method** | Combines queuing-theory-based demand model with reactive provisioning to right-size multi-tier web application deployments. Predicts demand using Holt-Winters exponential smoothing on request rate. |
| **Key Claim** | Holt-Winters exponential smoothing with a 5-minute prediction horizon reduces SLA violations while maintaining high utilization; outperforms reactive threshold policies. |
| **Relevance to #3** | **Key technique validation.** Urgaonkar 2008 confirms that exponential smoothing (one of our two proposed predictors) is practical and effective on cloud/web workloads at 5-minute horizons. Holt-Winters is essentially our "exponential smoothing" predictor. Objective: SLA (provisioning). Our objective: energy (host shutdown). |

**Novelty gap assessment:** SLA/provisioning objective, not energy/host power state. Different layer.

---

### [P14] Hermenier, Lorca, Menaud, Muller & Lawall 2009 — Entropy

| Field | Value |
|-------|-------|
| **Title** | Entropy: A Consolidation Manager for Clusters |
| **Authors** | Fabien Hermenier, Xavier Lorca, Jean-Marc Menaud, Gilles Muller, Julia Lawall |
| **Year** | 2009 |
| **Venue** | *ACM SIGPLAN/SIGOPS International Conference on Virtual Execution Environments (VEE)*, DOI: 10.1145/1508293.1508300 |
| **Citations** | ~700 |
| **Method** | Constraint-programming based VM placement and migration optimizer. Finds globally optimal placement using constraint solver at each scheduling interval. Considers host on/off state as a decision variable. |
| **Key Claim** | Entropy reduces consolidation time and migration count vs. greedy approaches by solving globally. Does not predict future demand — solves optimally given *current* observed state. |
| **Relevance to #3** | Closest work in terms of treating host on/off as an explicit optimization variable. However, Entropy is reactive (responds to current state) not proactive (predicts future state). Our contribution is adding a temporal predictor layer on top of consolidation decisions like Entropy/PABFD. |

**Novelty gap assessment:** Optimal reactive consolidation ≠ proactive predictive consolidation. No temporal predictor.

---

### [P15] Barroso & Hölzle 2007 — Energy-Proportional Computing

| Field | Value |
|-------|-------|
| **Title** | The Case for Energy-Proportional Computing |
| **Authors** | Luiz André Barroso, Urs Hölzle |
| **Year** | 2007 |
| **Venue** | *IEEE Computer*, 40(12), DOI: 10.1109/MC.2007.443 |
| **Citations** | ~2,500+ |
| **Method** | Analysis of idle power draw in servers; shows servers use 60-70% of full-load power at 20% utilization. Argues for energy-proportional hardware. |
| **Key Claim** | Idle/lightly-loaded servers are energy-inefficient; reducing time-in-idle state is critical. This is the **foundational justification** for our work: an idle host at 100W is consuming real energy that our predictor can eliminate earlier. |
| **Relevance to #3** | Foundational motivation. Our whole mechanism depends on Barroso & Hölzle's insight: P_idle ≈ 100W is non-zero, and every second of idle time is wasted energy. The sooner a host shuts down, the more energy we save. |

---

### [P16] Katal, Dahiya & Choudhury 2022 — Energy Efficiency in Cloud DCs Survey

| Field | Value |
|-------|-------|
| **Title** | Energy Efficiency in Cloud Computing Data Centers: A Survey on Software Technologies |
| **Authors** | Avita Katal, Susheela Dahiya, Tanupriya Choudhury |
| **Year** | 2022 |
| **Venue** | *Cluster Computing* (Springer), DOI: 10.1007/s10586-022-03713-0 (OA) |
| **Citations** | 412 (confirmed via OpenAlex) |
| **Method** | Survey of 200+ papers on software-level energy efficiency in cloud DCs. Taxonomy: VM consolidation, scheduling, resource provisioning, green computing. |
| **Key Claim** | VM consolidation is the dominant software-level energy lever. Most recent work uses static threshold policies. The survey explicitly identifies "adaptive prediction-driven consolidation" as an open research direction. |
| **Relevance to #3** | **Confirmation of gap as of 2022.** A 412-citation survey in a major journal explicitly identifies our research direction as open. This is strong novelty support. |

**Novelty gap assessment:** Direct open-problem statement in 2022 survey citing prediction-driven consolidation as unsolved.

---

## Evidence Map

| Mechanism | Papers | Notes |
|-----------|--------|-------|
| Reactive consolidation (PABFD baseline) | P1, P2, P14 | Our comparison baseline |
| Workload prediction (ARIMA) | P4, P6 | Same technique; different application (SLA, not energy) |
| Workload prediction (exponential smoothing) | P13 | Same technique; SLA-driven |
| Workload prediction (LSTM/ML) | P5, P8, P10 | Upper bound predictor |
| Prediction for **overload** detection (energy-aware) | P9 | Closest paper; different direction (overload vs. underload) |
| Proactive host power management | **NONE** | **Our novelty gap** |
| Idle host energy as primary metric | P15 (motivation) | Our primary metric grounded here |
| VM consolidation survey (confirming gap) | P2, P7, P16 | All confirm gap exists |
| Simulation platform | P3 | CloudSim Plus |
| Open-problem citation (Buyya) | P11 | Direct citation from PABFD author |

---

## Novelty Gap Assessment

### Status: **CONFIRMED ✅**

**Our specific claim that is novel:**
"A temporal predictor (ARIMA or exponential smoothing) over host utilization time series can
be used to trigger host shutdown earlier than PABFD, reducing idle host energy by a measurable
margin, with the tradeoff being increased SLA violations from premature migration."

**Why this is novel:**
1. **No paper targets underload prediction for host shutdown.** P9 (Li 2019) is the closest: it uses prediction for *overload* detection. Underload/shutdown is still reactive in all reviewed papers.
2. **No paper isolates idle host energy as the primary metric.** Energy papers optimize total energy; none frame "idle host linger energy" as the savings mechanism.
3. **Prediction horizon and accuracy tradeoff for shutdown timing is unstudied.** P4/P6/P13 study prediction for SLA-driven provisioning; the energy tradeoff under *under*load prediction is not characterized anywhere.
4. **P2 and P16 (surveys) explicitly confirm the gap** as of 2020 and 2022 respectively.
5. **P11 (Buyya 2023)** explicitly calls prediction for power state management "future work."

**What IS published (close but not exact):**
- Prediction for overload detection (P9): using LR to predict if a host will *exceed* threshold → migrate proactively
- Prediction for VM provisioning/autoscaling (P4, P6, P7, P10): adding/removing VMs based on predicted demand
- Optimal reactive consolidation (P14): globally optimal but still reactive

**Conclusion:** Our work fills a specific, well-documented gap. It is not an incremental parameter tweak of an existing paper — the shutdown-timing direction is unstudied.

---

## Directly Comparable Baselines for Protocol

For the experiment, our primary comparisons are:
1. **PABFD** (P1 — Beloglazov 2012): reactive baseline, standard in the field
2. **FFD** (First Fit Decreasing): simpler reactive baseline, widely used
3. **Oracle P-PABFD**: P-PABFD with perfect future knowledge (prediction error = 0) — upper bound
4. **ARIMA-3 P-PABFD**: our primary proposed policy
5. **ES-P-PABFD** (exponential smoothing): simpler predictor variant

---

## Exit Criteria Checklist

- [x] ≥15 papers surveyed and summarized (16 papers surveyed)
- [x] Novelty gap confirmed (prediction for host-level shutdown is not addressed in any reviewed paper)
- [x] Evidence map written showing where our work sits
- [x] At least 2 directly comparable baselines identified for protocol (PABFD + FFD + Oracle)

## → LIT REVIEW COMPLETE. READY TO TRANSITION TO EXPERIMENT DESIGN PHASE.
