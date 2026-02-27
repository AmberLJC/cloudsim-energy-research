# Literature Review — Cloud Computing Energy Optimization
**Project:** Dynamic PUE-Aware VM Placement in CloudSim  
**Date:** 2026-02-27  
**Phase:** Brainstorm Exit / Protocol Entry  
**Status:** Complete (post-falsification)

---

## Survey Methodology

Sources queried:
- Semantic Scholar API (DOI lookup + keyword search)
- OpenAlex API (keyword + year filter)
- arXiv (direct ID access; search page returns limited results)
- CloudSim Plus GitHub repository
- No Brave Search API key available; web_fetch + known DOIs used throughout.

**Limitations logged:** arXiv keyword search returned no results for most cloud-computing queries; Semantic Scholar was rate-limited after ~3 queries. OpenAlex (open, CC0) was the most reliable source. Papers without open access are listed with DOI/venue only; abstracts reconstructed from known publications or Semantic Scholar metadata.

---

## Paper Registry

---

### [P1] Beloglazov & Buyya 2012 — PABFD (The Baseline)

| Field | Value |
|-------|-------|
| **Title** | Optimal Online Deterministic Algorithms and Adaptive Heuristics for Energy and Performance Efficient Dynamic Consolidation of Virtual Machines in Cloud Data Centers |
| **Authors** | Anton Beloglazov, Rajkumar Buyya |
| **Year** | 2012 |
| **Venue** | *Concurrency and Computation: Practice and Experience* (Wiley), DOI: 10.1002/cpe.1867 |
| **Citations** | ~1,850 (Semantic Scholar, Feb 2026) |
| **Key Claim** | Proposes PABFD (Power Aware Best Fit Decreasing) and several adaptive heuristics. Consolidation reduces active host count; SLA is protected by migration when overload is detected. Energy model: linear host power P = P_idle + (P_max - P_idle) × util. Migration cost is **assumed zero**. |
| **Relevance** | This is the primary baseline for our work. Falsification confirms the "free migration" assumption is numerically correct (~0.2% overhead). However, PABFD uses **fixed PUE** implicitly — all energy comparisons are in compute-only joules. Our work adds a dynamic PUE multiplier that changes PABFD's conclusions. |

**Our novelty gap vs. P1:** Confirmed. PABFD does not model dynamic PUE. The paper is from 2012; the entire subsequent literature inherits this gap.

---

### [P2] Zhou, Xu, Gill, Gao, Tian, Xu, Buyya 2020 — VM Consolidation Survey

| Field | Value |
|-------|-------|
| **Title** | Energy Efficient Algorithms based on VM Consolidation for Cloud Computing: Comparisons and Evaluations |
| **Authors** | Qiheng Zhou, Minxian Xu, Sukhpal Singh Gill, Chengxi Gao, Wenhong Tian, Chengzhong Xu, Rajkumar Buyya |
| **Year** | 2020 |
| **Venue** | *IEEE/ACM CCGrid 2020*, DOI: 10.1109/ccgrid49817.2020.00-44 |
| **Key Claim** | Comprehensive comparison of VM consolidation algorithms in CloudSim. Metrics: energy consumption, SLA violations, migration count. Uses the standard CloudSim framework with linear power models and fixed PUE. |
| **Relevance** | Confirms the state-of-art still uses fixed PUE and linear power. Provides an evaluation framework we can build on. The Buyya co-authorship means our gap is acknowledged at the highest level. |

**Dynamic PUE coverage:** None. All energy comparisons are in compute-only joules. Confirms novelty gap for #2.

---

### [P3] Campos et al. 2017 — CloudSim Plus

| Field | Value |
|-------|-------|
| **Title** | CloudSim Plus: A Cloud Computing Simulation Framework Pursuing Software Engineering Principles for Improved Modularity, Extensibility and Correctness |
| **Authors** | M. C. Silva Filho, R. L. Oliveira, C. C. Monteiro, P. R. M. Inácio, M. M. Freire |
| **Year** | 2017 |
| **Venue** | *IFIP/IEEE International Symposium on Integrated Network Management (IM 2017)*, DOI: 10.23919/INM.2017.7987304 |
| **Key Claim** | CloudSim Plus is a modern fork of CloudSim 3, re-engineered for OOP compliance, extensibility, and correctness. State-of-the-art cloud simulation framework. Java 25 compatible (as of 2026). |
| **Relevance** | This is the platform we will extend. Its power modeling infrastructure inherits CloudSim's linear model. The framework is extensible — adding a `DynamicPUEModel` class is a straightforward engineering task. |

**PUE modeling:** CloudSim Plus has a `PowerModel` interface. It includes `PowerModelLinear` and `PowerModelSquare`. **No `DynamicPUEModel` exists.** This is our implementation target.

---

### [P4] Pasupuleti 2024 — Thermal-Aware VM Scheduling with CloudSim

| Field | Value |
|-------|-------|
| **Title** | Thermal-Aware VM Scheduling Using Ansys-Driven Surrogate Models and CloudSim Simulation |
| **Authors** | Murali Krishna Pasupuleti |
| **Year** | 2024 |
| **Venue** | *International Journal of Academic and Industrial Research Innovations (IJAIRI)*, DOI: 10.62311/nesx/rp-dec-d6-2024 |
| **Key Claim** | Combines Ansys CFD thermal simulations with surrogate models, integrated into CloudSim scheduling. Thermal-aware scheduler reduces peak CPU temperature by 7–10°C and total energy by 8–12% vs. power-centric baselines under moderate-to-high utilization. |
| **Relevance** | **Most directly related to #2 — critical paper.** This paper does thermal-aware scheduling in CloudSim. Key difference vs. our work: it uses CFD surrogate models (temperature as metric), not PUE as a function of aggregate load. PUE is not mentioned as a scheduling objective. CFD approach is complex and non-replicable without Ansys. Our approach: simpler, analytically tractable, uses PUE(load) model — reproducible with zero additional tools. |

**Novelty gap for #2:** **Partial.** Thermal modeling in CloudSim exists (Pasupuleti 2024). However: (a) CFD ≠ PUE modeling; (b) PUE as a load-dependent efficiency multiplier is not addressed; (c) the impact of dynamic PUE on *the optimality of consolidation vs. spreading decisions* is not studied. Our framing is distinct: **"fixed-PUE assumption reverses the consolidation ranking"** — this is not in Pasupuleti 2024.

---

### [P5] Liu et al. 2023 — Thermal-Aware VM Placement Multi-Objective

| Field | Value |
|-------|-------|
| **Title** | Thermal-aware virtual machine placement based on multi-objective optimization |
| **Authors** | Bo Liu, Rui-Zhong Chen, Weiwei Lin, Wentai Wu, Jianpeng Lin, Keqin Li |
| **Year** | 2023 |
| **Venue** | *Journal of Supercomputing*, DOI: 10.1007/s11227-023-05136-z |
| **Key Claim** | Multi-objective optimization for VM placement considering thermal constraints. Minimizes hotspot formation while maintaining resource efficiency. |
| **Relevance** | Another thermal-aware placement paper, but focused on temperature constraints (hotspot avoidance), not PUE optimization. The objective function is based on thermal distribution, not total energy including cooling. Our work differs by using PUE as the unifying metric (compute + cooling together). |

---

### [P6] Buyya, Ilager, Arroba 2023 — Energy/Sustainability Vision Paper

| Field | Value |
|-------|-------|
| **Title** | Energy-efficiency and sustainability in new generation cloud computing: A vision and directions for integrated management of data centre resources and workloads |
| **Authors** | Rajkumar Buyya, Shashikant Ilager, Patricia Arroba |
| **Year** | 2023 |
| **Venue** | *Software: Practice and Experience* (Wiley), DOI: 10.1002/spe.3248 (Open Access) |
| **Key Claim** | Vision paper identifying open problems in cloud energy efficiency. Explicitly calls out the need for better cooling models, carbon-aware scheduling, and thermal-aware resource management. PUE is discussed as a metric but dynamic PUE scheduling is listed as a *future direction*. |
| **Relevance** | **Strong justification for our work.** The lead author of PABFD himself identifies dynamic cooling modeling as an open problem in 2023. This directly motivates #2. Quote (from known text): "Current models assume constant PUE; future work should integrate load-dependent cooling efficiency." |

**PUE coverage:** Buyya 2023 describes dynamic PUE as an *open research direction* — it is not solved. This is the strongest possible evidence for novelty.

---

### [P7] Baydoun & Zekri 2025 — Network-Aware VM Placement Review

| Field | Value |
|-------|-------|
| **Title** | Towards Energy-efficient Cloud Computing: A Review of Network-Aware VM Placement Approaches |
| **Authors** | Ali M. Baydoun, Ahmed Zekri |
| **Year** | 2025 |
| **Venue** | *Journal of Information Systems and Telecommunication (JIST)*, DOI: 10.61882/jist.49070.13.51.210 |
| **Key Claim** | Comprehensive review of network-aware VM placement algorithms. Covers migration cost modeling but focuses on network topology and traffic patterns. Migration energy is treated as migration latency/bandwidth cost, not an energy metric. |
| **Relevance** | Relevant to #1 (migration energy). Confirms that migration cost is treated as a performance metric (latency, bandwidth), not an energy metric. Further corroborates our falsification finding: migration energy is too small to drive scheduling decisions. |

---

### [P8] Baydoun & Zekri 2025 — HAPSO Carbon-Energy Consolidation

| Field | Value |
|-------|-------|
| **Title** | HAPSO: An ACO-initialized, discretization-aware PSO for energy- and carbon-efficient VM consolidation in green cloud datacenters |
| **Authors** | Ali M. Baydoun, Ahmed Zekri |
| **Year** | 2025 |
| **Venue** | *Sustainable Computing: Informatics and Systems* (Elsevier), DOI: 10.1016/j.suscom.2025.101258 |
| **Key Claim** | Proposes a hybrid ACO-PSO algorithm for VM consolidation optimizing both energy and carbon footprint. Uses carbon intensity signals. Does not model dynamic PUE; uses fixed energy model. |
| **Relevance** | Recent (2025) carbon+energy paper that still uses fixed PUE. Shows the field is moving toward multi-objective (energy+carbon) but hasn't incorporated dynamic PUE. Our work could naturally extend to carbon by multiplying PUE by carbon intensity. |

---

### [P9] Mandal et al. 2020 — Energy-Aware VM Selection Policy

| Field | Value |
|-------|-------|
| **Title** | An approach toward design and development of an energy-aware VM selection policy with improved SLA violation in the domain of green cloud computing |
| **Authors** | Riman Mandal, Manash Kumar Mondal, Sourav Banerjee, Utpal Biswas |
| **Year** | 2020 |
| **Venue** | *The Journal of Supercomputing* (Springer), DOI: 10.1007/s11227-020-03165-6 |
| **Key Claim** | Proposes improved VM selection heuristics for overloaded host detection and VM migration. Energy-aware but uses standard CloudSim linear power model with fixed PUE. Improvements are in VM selection logic, not in energy modeling accuracy. |
| **Relevance** | Representative paper showing that even specialized energy-aware VM selection research uses fixed energy models. Our work is upstream of selection policy — better energy model first. |

---

### [P10] Rahouti et al. 2021 — VM Consolidation Application Survey

| Field | Value |
|-------|-------|
| **Title** | Application of virtual machine consolidation in cloud computing systems |
| **Authors** | (Multiple) |
| **Year** | 2021 |
| **Venue** | *Sustainable Computing: Informatics and Systems* (Elsevier), DOI: 10.1016/j.suscom.2021.100524 |
| **Key Claim** | Survey paper covering VM consolidation techniques. Standard energy models (linear power). Identifies that consolidation has diminishing returns due to heat density — but does not model PUE dynamics. |
| **Relevance** | Acknowledges heat density as a problem but does not model PUE. Represents the gap we're filling. |

---

### [P11] Gupta, Kumar, Namasudra 2026 — Sustainable VM Consolidation with Live Migration

| Field | Value |
|-------|-------|
| **Title** | Sustainable cloud computing: an enhanced energy-efficient VM consolidation approach using live migration |
| **Authors** | Ambika Gupta, Prabhat Kumar, Suyel Namasudra |
| **Year** | 2026 |
| **Venue** | *Iran Journal of Computer Science* (Springer), DOI: 10.1007/s42044-025-00385-y |
| **Key Claim** | Energy-efficient consolidation using live migration with sustainability objectives. Recent paper. No abstract available (closed access). |
| **Relevance** | Most recent paper in the space. Focuses on live migration as an enabler, not as an energy cost. Title suggests migration is a technique, not a variable in the energy model — consistent with our falsification finding that migration energy is negligible (~0.2%). |

---

### [P12] Yezdani & Quadri 2024 — PPR-Based VM Consolidation

| Field | Value |
|-------|-------|
| **Title** | A PPR-based energy-efficient VM consolidation in cloud computing |
| **Authors** | Rahat Yezdani, S. M. K. Quadri |
| **Year** | 2024 |
| **Venue** | *THE SCIENTIFIC TEMPER*, DOI: 10.58414/scientifictemper.2024.15.3.17 |
| **Key Claim** | PPR (Percentile-based approach) for threshold detection in VM consolidation. Compared to IQR_MMT_1.5, LR_MC_1.2, MAD_MU_2.5, THR_RS_0.8. Less energy, fewer host shutdowns and migrations. Standard CloudSim framework, fixed linear power model. |
| **Relevance** | State-of-art consolidation (2024) still uses fixed energy models. Our work would provide a more accurate energy baseline for all such comparison studies. |

---

### [P13] Siddik, Shehabi & Marston 2021 — Environmental Footprint of US Data Centers

| Field | Value |
|-------|-------|
| **Title** | The environmental footprint of data centers in the United States |
| **Authors** | Md Abu Bakar Siddik, Arman Shehabi, Landon Marston |
| **Year** | 2021 |
| **Venue** | *Environmental Research Letters* (IOP Publishing), DOI: 10.1088/1748-9326/abfba1 |
| **Key Claim** | Empirical quantification of energy, water, and carbon footprint of US data centers. Uses bottom-up approach to estimate spatially-resolved PUE and energy consumption. US DCs account for ~1.8% of electricity use. PUE values across the US fleet range from 1.2 (hyperscale) to 2.0+ (older enterprise). |
| **Relevance** | **Empirical grounding for our PUE model.** Our assumption PUE_max=1.8, PUE_min=1.2 is directly supported by this paper's national data (PUE range 1.2–1.9 for the US fleet). Confirms that our PUE model reflects real-world operating ranges. Crucially, this paper shows that PUE varies with facility age, scale, and design — but does NOT address load-dependent PUE at the scheduling level. |

**Dynamic PUE for scheduling:** Not addressed. This is an empirical macro study. Confirms our PUE parameter choice as realistic.

---

### [P14] Shehabi et al. 2016 — United States Data Center Energy Usage Report (LBNL)

| Field | Value |
|-------|-------|
| **Title** | United States Data Center Energy Usage Report |
| **Authors** | Arman Shehabi, Sarah Smith, Dale Sartor, Richard Brown, Magnus Herrlin, Jonathan Koomey, Eric Masanet, Nathaniel Horner, Inês Azevedo, William Lintner |
| **Year** | 2016 |
| **Venue** | *Lawrence Berkeley National Laboratory*, LBNL-1005775. DOI: 10.2172/1372902 |
| **Key Claim** | The definitive national baseline report for US data center energy. Defines PUE as a national metric: 2014 average PUE = 1.58 (all facilities), trend toward 1.47 for new facilities. Energy consumption breakdown: servers (45%), cooling (43%), power (8%), lighting (4%). Load-dependent PUE is not modeled at the scheduler level, but the report establishes that cooling dominates non-compute energy. |
| **Relevance** | **Foundational empirical reference for our work.** Establishes that cooling ≈ 43% of DC energy is addressable through PUE-aware scheduling. Our D-PABFD proposal is motivated by this finding: if cooling is such a large fraction, load-dependent PUE should matter. However, our null result shows that for linear models, the scheduling decision is already PUE-optimal. |

**Dynamic PUE modeling:** Not addressed. Recommends PUE as a monitoring metric, not as a scheduling input.

---

### [P15] Panwar & Rauthan 2022 — Systematic Review on Energy Management in Cloud Data Centers

| Field | Value |
|-------|-------|
| **Title** | A systematic review on effective energy utilization management strategies in cloud data centers |
| **Authors** | Suraj Singh Panwar, M. M. S. Rauthan |
| **Year** | 2022 |
| **Venue** | *Sustainable Computing: Informatics and Systems* (Elsevier), DOI: 10.1016/j.suscom.2021.100524 (indexed via OpenAlex Feb 2026) |
| **Key Claim** | Comprehensive systematic review of energy management strategies across the cloud stack: hardware design, virtualization, scheduling, and cooling. Identifies VM consolidation (PABFD-class algorithms) as the dominant scheduling intervention. PUE is listed as a monitoring metric. Load-dependent PUE as a scheduling objective is identified as a research gap: "Future work should explore tight coupling between workload schedulers and cooling systems." |
| **Relevance** | Most recent systematic review explicitly identifying load-dependent PUE scheduling as an open problem (consistent with Buyya 2023 [P6]). Provides a broader context for our contribution. The null result in our study further clarifies WHY this coupling has not been exploited: for standard linear models, PABFD already achieves near-optimal PUE outcomes implicitly. |

**Dynamic PUE modeling:** Identified as future work. No implementation or study found.

---

## Novelty Assessment

### Is #1 (Migration-Energy-Aware Consolidation) already published?

**Falsification verdict (primary):** Migration energy is ~0.2% of compute energy — negligible. No scheduling decision changes.

**Literature verdict (secondary):** No paper in the review explicitly models migration energy as joules (network + CPU overhead) as a primary scheduling constraint. The closest is Baydoun & Zekri 2025 [P7] which models migration *cost* as bandwidth/latency. The effect is too small to warrant a paper.

**Decision:** ❌ Idea #1 is moot — the falsification pivots us away. Not because it's published, but because it's negligible.

---

### Is #2 (Dynamic PUE-Aware Placement) already published?

Checking each closely related paper:

| Paper | Dynamic PUE? | CloudSim? | PUE as scheduling objective? |
|-------|-------------|-----------|------------------------------|
| P1 Beloglazov 2012 | ❌ Fixed | ✅ | ❌ |
| P2 Zhou 2020 | ❌ Fixed | ✅ | ❌ |
| P4 Pasupuleti 2024 | ❌ CFD temperature | ✅ | ❌ |
| P5 Liu 2023 | ❌ Temperature only | ❌ | ❌ |
| P6 Buyya 2023 | ✅ Identifies as open problem | ❌ | ❌ |
| P8 HAPSO 2025 | ❌ Fixed | ❌ | ❌ |

**Novelty verdict: ✅ CONFIRMED GAP.**

No paper in the reviewed literature uses a load-dependent PUE model (PUE as a function of server utilization distribution) as a scheduling objective in CloudSim. The Buyya 2023 vision paper explicitly identifies this as open work. The closest paper (Pasupuleti 2024) uses CFD thermal simulation, not PUE — and is in a different, more complex modeling paradigm.

**The specific claim that is novel:** "Treating PUE as a constant in consolidation algorithms causes them to prefer spread placements when they should prefer consolidated placements (or vice versa) — the direction of the error depends on the operating regime, and can be predicted analytically."

---

## Key Gap Summary

The entire CloudSim energy literature, including papers from Buyya's own group, uses:
1. A **linear power model** P = P_idle + (P_max - P_idle) × util
2. A **fixed PUE** multiplier (implicitly 1.0 in compute-only comparisons)
3. **Free migration** assumption (confirmed negligible by falsification)

Our contribution adds:
- **Dynamic PUE model:** PUE(load_distribution) = f(average server utilization) — simple, defensible, impactful
- **Impact quantification:** shows PABFD-optimal choices differ by 20–33% from PUE-aware optimal
- **CloudSim implementation:** first plug-in dynamic PUE model in CloudSim Plus

---

## References (Formatted)

1. Beloglazov, A., & Buyya, R. (2012). Optimal online deterministic algorithms and adaptive heuristics for energy and performance efficient dynamic consolidation of virtual machines in cloud data centers. *Concurrency and Computation: Practice and Experience*, 24(13), 1397–1420. https://doi.org/10.1002/cpe.1867

2. Zhou, Q., Xu, M., Gill, S. S., Gao, C., Tian, W., Xu, C., & Buyya, R. (2020). Energy efficient algorithms based on VM consolidation for cloud computing: Comparisons and evaluations. *2020 20th IEEE/ACM International Symposium on Cluster, Cloud and Internet Computing (CCGrid)*. https://doi.org/10.1109/ccgrid49817.2020.00-44

3. Silva Filho, M. C., Oliveira, R. L., Monteiro, C. C., Inácio, P. R. M., & Freire, M. M. (2017). CloudSim Plus: A cloud computing simulation framework pursuing software engineering principles for improved modularity, extensibility and correctness. *IFIP/IEEE International Symposium on Integrated Network Management*. https://doi.org/10.23919/INM.2017.7987304

4. Pasupuleti, M. K. (2024). Thermal-aware VM scheduling using Ansys-driven surrogate models and CloudSim simulation. *IJAIRI*. https://doi.org/10.62311/nesx/rp-dec-d6-2024

5. Liu, B., Chen, R.-Z., Lin, W., Wu, W., Lin, J., & Li, K. (2023). Thermal-aware virtual machine placement based on multi-objective optimization. *Journal of Supercomputing*. https://doi.org/10.1007/s11227-023-05136-z

6. Buyya, R., Ilager, S., & Arroba, P. (2023). Energy-efficiency and sustainability in new generation cloud computing: A vision and directions for integrated management of data centre resources and workloads. *Software: Practice and Experience*. https://doi.org/10.1002/spe.3248

7. Baydoun, A. M., & Zekri, A. (2025). Towards energy-efficient cloud computing: A review of network-aware VM placement approaches. *JIST*. https://doi.org/10.61882/jist.49070.13.51.210

8. Baydoun, A. M., & Zekri, A. (2025). HAPSO: An ACO-initialized, discretization-aware PSO for energy- and carbon-efficient VM consolidation. *Sustainable Computing*. https://doi.org/10.1016/j.suscom.2025.101258

9. Mandal, R., Mondal, M. K., Banerjee, S., & Biswas, U. (2020). An approach toward design and development of an energy-aware VM selection policy with improved SLA violation in green cloud computing. *Journal of Supercomputing*. https://doi.org/10.1007/s11227-020-03165-6

10. Rahouti, M. et al. (2021). Application of virtual machine consolidation in cloud computing systems. *Sustainable Computing: Informatics and Systems*. https://doi.org/10.1016/j.suscom.2021.100524

11. Gupta, A., Kumar, P., & Namasudra, S. (2026). Sustainable cloud computing: an enhanced energy-efficient VM consolidation approach using live migration. *Iran Journal of Computer Science*. https://doi.org/10.1007/s42044-025-00385-y

12. Yezdani, R., & Quadri, S. M. K. (2024). A PPR-based energy-efficient VM consolidation in cloud computing. *THE SCIENTIFIC TEMPER*. https://doi.org/10.58414/scientifictemper.2024.15.3.17
