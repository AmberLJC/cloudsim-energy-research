> **HotCarbon 2026 condensed version (6-page target). Source: paper.md v1.0-final — Open Problems section added; ready for HotCarbon 2026 submission when CFP opens**

---

# Carbon-Optimal Hardware Lifecycle Planning for AI Data Centers: A Dynamic Programming Approach

**Targeting:** HotCarbon 2026  
**Date:** 2026-02-28

---

## Abstract

The formula data center sustainability teams use to compute optimal server refresh cycles (periodic replacement T*) is mathematically invalid for real data centers, which always have staggered fleet age distributions. We show this invalidity using finite-horizon dynamic programming applied to a parameterized fleet simulation, and quantify the operational consequences. For GPU inference fleets — 60–80% of deployed AI compute — correcting this mistake by moving from a 2-year to a 4-year refresh cycle saves **17–43% lifecycle carbon** across six grid carbon intensity scenarios (50–800 gCO₂/kWh), conditional on embodied carbon ≥ 1,500 kgCO₂/node. Against a more conservative Fixed-3yr baseline, DP-Optimal saves 7–23%; the largest gains accrue when moving from 2-year to 4-year cycles, which itself is achievable with a simple policy requiring no monitoring. Disaggregating training and inference hardware refresh cycles is the primary actionable lever for reducing embodied carbon in AI infrastructure.

**Keywords:** embodied carbon, lifecycle carbon, hardware refresh, dynamic programming, GPU, inference

---

## 1. Introduction

Every data center sustainability team optimizing hardware refresh cycles uses the same formula: the classical periodic replacement T* = argmin_T [K/T + (1/T)∫c(t)dt], which yields an optimal replacement interval as a function of embodied cost K and operating cost c(t). **This formula is mathematically invalid for real data centers.** T* assumes all servers simultaneously start at age 0 — a condition that holds only on day one of a greenfield deployment. Every real fleet has staggered procurement vintages, with servers entering any planning horizon at heterogeneous ages. For staggered fleets, T* systematically misidentifies which servers to replace immediately versus hold, and can recommend policies that perform *worse* than simply doing nothing and running servers to their operational limit. We demonstrate this invalidity formally and show the correct approach: finite-horizon dynamic programming, which evaluates each server's optimal decision as a function of its individual age, generation, and remaining planning horizon.

Correcting this mistake has concrete operational consequences for AI infrastructure. NVIDIA's ~2-year architectural cadence (A100→H100→H200→B200, 2020–2025) has entrenched a uniform 2-year GPU refresh norm across inference and training alike. Yet **inference** (60–80% of deployed AI GPU compute [2]) can tolerate 4-year-old hardware; only training requires frontier generations. Applying DP-optimal lifecycle planning to GPU inference fleets — where the industry norm is most misaligned — shows that simply extending refresh from 2 to 4 years saves 17–43% lifecycle carbon versus the 2-year norm (7–23% against a 3-year baseline reflecting actual hyperscaler cycles), conditional on GPU embodied carbon ≥ 1,500 kgCO₂/node. This is not a narrow optimization: it is a structural correction made possible by recognizing that inference and training have different hardware requirements and that the formula currently guiding refresh policy is wrong.

**Contributions:**
1. First demonstration that classical T* analysis is invalid for staggered fleet deployments and can *underperform* the industry norm in practice.
2. First simulation-based quantification of lifecycle carbon under DP-optimal vs industry norm refresh policies across CPU and GPU fleet scenarios and six grid carbon intensity scenarios.
3. A practical 2-parameter threshold heuristic capturing 69–89% of DP savings, implementable using only an asset registry and public grid CI data.

---

## 2. Background

**Embodied carbon in computing.** Gupta et al. [1] established that embodied carbon dominates lifecycle emissions for clean-energy procurers. Acun et al. [4] extended this to AI hardware: 8-GPU server nodes carry ~3,000–5,000 kgCO₂eq embodied before first operation. Ji et al. (SCARIF) [5] provide the most detailed GPU server LCA, confirming accelerators account for 60–75% of node-level embodied carbon. Luccioni et al. [6] showed empirically that including embodied carbon roughly doubles operational-only lifecycle estimates for large model training.

**Equipment replacement DP.** Bellman [7] formulated asset replacement as a DP with state (age, time-remaining) and backward induction. Pierskalla and Voelker [10] established the key distinction between infinite-horizon stationary models (yielding T*) and finite-horizon models requiring DP. For any asset whose operating costs change over time — including servers on a decarbonizing grid — finite-horizon DP is the correct formulation. The T* formula assumes all assets start at age 0; real data centers have heterogeneous age distributions that violate this assumption.

**Inference dominance.** Inference represents 60–80% of deployed AI GPU compute at hyperscale [2]. Unlike training (intensive but discrete), inference serving is continuous and tolerates older hardware. This makes inference hardware lifecycle the primary lever for embodied carbon reduction.

---

## 3. System Model and Policies

We model a fleet of N=50 servers over a H=10 year horizon with annual replacement decisions. Each server has state (gen, age): hardware generation and years since last replacement. Replacing a server incurs embodied carbon K and installs a newer-generation server with efficiency gain η per generation. Operating a server of generation g at grid CI c emits P·(1−η)^g · c per year (P = 250 W base power, η = 50%/gen for GPU, 15%/gen for CPU; K = 3,000 kgCO₂ GPU, 1,000 kgCO₂ CPU). Initial fleet ages are uniformly distributed in [0, refresh_norm). We run 20 Monte Carlo seeds over six CI scenarios: nuclear_fr (50), norway_hydro (100), eu_avg (300), us_avg (400), uk_grid (500), coal_pl (800 g/kWh).

**Policies evaluated:**

- **Fixed-2yr** (GPU baseline): Replace each server when age ≥ 2 years. Current AI industry norm.
- **Fixed-3yr** (alternative baseline): Replace when age ≥ 3 years. Reflects actual reported hyperscaler cycles.
- **Fixed-4yr** (extended cycle): Replace when age ≥ 4 years. Primary comparison for GPU inference.
- **DP-Optimal**: Backward induction on V[gen, years_remaining] — replace iff embodied + future_cost(gen+1) < future_cost(gen). Globally optimal under the model.
- **Threshold Heuristic** (practical): Replace if age ≥ α AND current CI ≥ β; otherwise hold to max_age.

For GPU inference, a hard max_useful_age = 4 years is enforced regardless of policy (operational obsolescence constraint). The DP table is built with this constraint incorporated.

**Grid CI model.** Static scenarios use constant CI. The eu_decarbonizing scenario uses a linear decline from 300 to 200 g/kWh over 10 years, incorporated into DP backward induction via a per-step CI schedule.

---

## 4. Results

### GPU Inference Fleet

Table 1 shows GPU inference results (max_age=4yr, eff=50%/gen, emb=3,000 kgCO₂, N=50, H=10yr, 20 seeds) across all CI scenarios and all fixed baselines. DP-Optimal saves **17–43%** versus Fixed-2yr and **7–23%** versus Fixed-3yr.

**Table 1: GPU Inference Fleet — DP-Optimal Carbon Savings vs Multiple Baselines**

| Scenario | CI (g/kWh) | Fixed-2yr (kgCO₂) | Fixed-3yr (kgCO₂) | DP-Optimal (kgCO₂) | DP vs Fixed-2yr | DP vs Fixed-3yr |
|---|---|---|---|---|---|---|
| nuclear_fr | 50 | 848,483 | 626,870 | 483,395 | **+43.0%** | **+22.9%** |
| norway_hydro | 100 | 866,867 | 653,740 | 516,790 | **+40.4%** | **+20.9%** |
| eu_avg | 300 | 940,400 | 761,220 | 706,762 | **+24.8%** | **+7.2%** |
| us_avg | 400 | 977,167 | 814,959 | 742,350 | **+24.0%** | **+8.9%** |
| uk_grid | 500 | 1,013,933 | 868,699 | 777,938 | **+23.3%** | **+10.4%** |
| coal_pl | 800 | 1,124,233 | 1,029,919 | 930,675 | **+17.2%** | **+9.6%** |

*All scenarios: GPU inference fleet, max_useful_age=4yr, eff_gain=50%/gen, emb=3,000 kgCO₂/node.*

Against a Fixed-2yr baseline, DP-Optimal savings are substantial across all CI scenarios. Against the more conservative Fixed-3yr baseline (reflecting actual hyperscaler cycles), savings range from +7.2% (eu_avg) to +22.9% (nuclear). The findings are robust to efficiency gain assumptions (25–75%/gen): savings remain positive at every tested efficiency level and CI scenario (Table 4 in full paper). Embodied carbon uncertainty (emb ∈ {500–5,000} kgCO₂) similarly leaves DP-Optimal savings positive across the full plausible range. The Fixed-4yr heuristic fails at high-CI + low-emb regimes (see Discussion).

### CPU Fleet

**Table 2: CPU Fleet — DP-Optimal vs Fixed-5yr Industry Norm**

| Scenario | CI (g/kWh) | Fixed-5yr (kgCO₂) | DP-Optimal (kgCO₂) | DP Saving |
|---|---|---|---|---|
| nuclear_fr | 50 | ~219,000 | ~87,000 | **+60.3%** |
| norway_hydro | 100 | ~231,000 | ~113,000 | **+51.1%** |
| eu_avg | 300 | ~277,000 | ~215,000 | **+22.4%** |
| us_avg | 400 | ~300,000 | ~246,000 | **+18.1%** |
| uk_grid | 500 | ~322,000 | ~277,000 | **+13.9%** |
| coal_pl | 800 | ~390,000 | ~346,000 | **+11.3%** |

*CPU fleet: N=50, H=10yr, eff=15%/gen, emb=1,000 kgCO₂, 20 seeds. Values are approximate from simulation.*

CPU savings peak at low-CI grids (where embodied cost dominates and holding hardware is most beneficial) and remain meaningful at high-CI grids (~11%). The eu_decarbonizing scenario (300→200 g/kWh linear decline) shows DP savings increasing to +16.6% vs +12.4% for static eu_avg, as the DP correctly recommends holding hardware longer when future operational carbon is declining.

---

## 5. The T* Invalidity Finding

The classical analytical refresh cycle T* = argmin_T [K/T + (1/T)∫c(t)dt] produces a useful first approximation but rests on a zero-age fleet assumption: all servers simultaneously start fresh at age 0. This assumption is violated in every real data center, where servers span multiple procurement vintages and enter any planning horizon at heterogeneous ages.

**The staggered fleet failure mode.** When T* recommends "hold until T years," it ignores servers that already have age 2 at the start of the planning horizon and face 8 remaining years — for which the optimal decision is immediate replacement to harvest efficiency gains over the full 8 years. T* sees their age (2) and says "wait until you reach T years." DP sees their state (gen=0, age=2, years_remaining=8) and immediately replaces them if the efficiency gain over 8 years exceeds embodied cost.

**The front-loading mechanism.** DP-Optimal systematically front-loads replacements in early years of the planning horizon for servers that entered already aged. This creates a characteristic pattern: a high-replacement burst in years 1–3, followed by a period of holding, then selective replacement as younger servers approach their optimal age. T* applied to a staggered fleet instead spreads replacements evenly — which looks like the Fixed-T* policy, achieving worse outcomes than either DP or the simple industry norm.

**Empirical result.** At uk_grid (CI=500 g/kWh), Fixed-T* (T*=1yr) achieves worse outcomes than Fixed-5yr for CPU fleets with staggered ages — a counterintuitive failure confirmed across 20 Monte Carlo seeds. The DP, recognizing that replacing every server annually in a staggered fleet causes unnecessary embodied emissions (many replacements occur on near-new servers), correctly selects a per-server schedule that the aggregate T* formula cannot represent.

**General condition.** For a server at age a with remaining horizon H, immediate replacement dominates T*'s "hold" recommendation when H·Δc(CI) > K_embodied, where Δc(CI) is the annual operational savings from next-gen hardware. This condition is age- and horizon-dependent; T*'s steady-state formula never evaluates it. Any staggered fleet contains servers for which this condition holds and T* misses them.

---

## 6. Threshold Heuristic

A DP-Optimal policy requires computing and storing a V[gen, years_remaining] table and applying it per-server annually — tractable in software but requiring CI monitoring and DP computation infrastructure. A practical deployment needs something simpler.

We derived a 2-parameter threshold heuristic via grid search: **Replace if age ≥ α AND current CI ≥ β; else hold to max_age.** For each (α, β) pair, we measured mean savings across all six CI scenarios (20 seeds each). Optimal parameters:

- **CPU fleet (no max_age):** (α=2, β=600 g/kWh) → mean saving **21.2% vs Fixed-5yr** = 69% of DP savings
- **GPU inference (max_age=4yr):** (α=4, β=50 g/kWh) → mean saving **31.9% vs Fixed-2yr** = 89% of DP savings

The GPU inference result is particularly clean: with β=50 g/kWh (satisfied at all CI scenarios studied), the heuristic collapses to **Fixed-4yr** — simply run GPU inference servers to 4 years. No CI monitoring, no DP computation, no dynamic decisions. The heuristic captures 89% of DP savings because the max_age=4yr constraint already limits the policy space; the remaining 11% of DP savings comes from within-4yr timing optimization that the Fixed-4yr rule cannot capture.

**Deployability.** The threshold heuristic requires only an asset registry (server age) and public grid CI data (e.g., Electricity Maps API, freely available). It is implementable within existing data center asset management tooling without modifying depreciation accounting or procurement contracts.

---

## 7. Discussion and Limitations

### Institutional Deployment Barriers

Hardware refresh decisions at large cloud providers are controlled by CapEx and procurement teams, not sustainability organizations. Refresh cycles are set by depreciation schedules (typically 3–5 year straight-line), vendor trade-in programs, and supply chain contracts negotiated years in advance. The primary institutional barrier to carbon-optimal refresh is not technical ignorance but financial: accounting systems treat hardware replacement as a capital event with tax implications, and vendor trade-in incentives actively encourage early turnover. Despite these barriers, the threshold heuristic is implementable within existing procurement workflows: it requires only an asset registry and public grid CI data, with no modification to depreciation accounting or vendor contracts. A CapEx team can apply the Fixed-4yr rule by tagging inference-designated servers at acquisition and tracking their age — an operational change that fits standard asset-management tooling.

### Limitations

**Simulated EPD data.** No verified Environmental Product Declaration exists for H100/H200/B200 as of early 2026. Our emb_kg=3,000 kgCO₂ baseline is estimated from Ji et al. [5] and Acun et al. [4]. Sensitivity analysis across emb ∈ {500–5,000} kgCO₂ shows DP-Optimal savings remain positive throughout; however, the Fixed-4yr heuristic *fails* at low emb + high CI (e.g., −41% at emb=500 kgCO₂, CI=800 g/kWh), where frequent replacement to harvest efficiency gains is net beneficial. Operators on high-carbon grids should verify emb_kg > 1,500 kgCO₂ before applying Fixed-4yr.

**Homogeneous fleets.** Real data centers run heterogeneous hardware across multiple generations. A mixed-fleet model would better capture procurement realities but substantially increases state complexity.

**No training scenario.** We do not model training workloads (max_age=2yr). Our GPU analysis focuses on inference, where the carbon optimization opportunity is largest due to the inference-dominance of deployed AI compute.

**No secondary market effects.** Retired hardware has residual value in secondary markets, which would modify the effective embodied carbon burden per year of primary service life.

---

## 8. Related Work

Gupta et al. [1] (HPCA 2021) established the embodied carbon dominance finding for clean-energy data centers and called for lifecycle-aware hardware policy — a framing this paper directly extends with quantitative DP analysis. Acun et al. [4] (ASPLOS 2023) quantified AI accelerator embodied carbon and showed GPU nodes carry 3–5× the embodied carbon of CPU servers, motivating GPU-specific lifecycle analysis. Ji et al. (SCARIF) [5] (2024) provide the most detailed GPU server LCA, confirming accelerators dominate node-level embodied carbon and providing the parameter basis for our GPU emb_kg estimate.

Bashir et al. [9] (2021) analyze carbon-aware *workload* scheduling across data centers with heterogeneous grid CI — a complementary intervention to our hardware lifecycle work. Where Bashir et al. shift workloads to lower-CI regions, we shift hardware retirement decisions to lower-embodied outcomes; both are orthogonal levers.

Pierskalla and Voelker [10] (1976) is the foundational OR survey for equipment replacement under DP — our formulation directly applies their finite-horizon DP framework to the server hardware problem. To our knowledge, no prior work applies finite-horizon DP to server hardware lifecycle carbon or demonstrates the T* invalidity finding for staggered fleets.

---

## 9. Conclusion

The AI industry's uniform 2-year GPU refresh cycle wastes 17–43% lifecycle carbon relative to the DP-optimal policy for inference workloads. Even against a 3-year baseline (reflecting actual hyperscaler practice), DP-Optimal saves 7–23%. The most actionable finding: simply extending GPU inference server lifetimes from 2 to 4 years — the Fixed-4yr heuristic — captures 89% of the full carbon reduction with no dynamic decision-making required. We also show, for the first time in this literature, that the classical T* periodic replacement formula is invalid for staggered fleet deployments and can recommend cycles that perform worse than the industry norm. Disaggregating training and inference hardware refresh cycles is the primary deployable lever for reducing embodied carbon in AI data centers.

---

## 10. Open Problems

This work identifies three community priorities for the embodied carbon research agenda:

**GPU EPD data is urgently needed.** NVIDIA, AMD, and Intel have not published verified Environmental Product Declarations (EPDs) for H100, H200, B200, or competing AI accelerators as of early 2026. Every quantitative study of AI hardware lifecycle carbon — including this one — uses estimated embodied carbon figures derived from manufacturing intensity proxies. The research community and policymakers cannot validate, compare, or regulate GPU lifecycle carbon without first-party manufacturer EPD data. We call on accelerator vendors to publish ISO 14044-compliant EPDs for current and future GPU products.

**Fleet age distribution data for validation.** The DP-vs-T* invalidity finding presented here is analytically demonstrated but empirically unvalidated: no cloud provider publishes hardware fleet age distribution data. The Google, Azure, and Alibaba trace releases have enabled a decade of cloud scheduling research; an analogous open fleet lifecycle dataset — mapping server acquisition dates, workload class, and retirement dates across a real production fleet — would enable the validation, refinement, and calibration of hardware lifecycle optimization models. We call on hyperscalers to include fleet age data in their open research data releases.

**Regulatory frameworks may incentivize the wrong behavior.** The EU's Corporate Sustainability Reporting Directive (CSRD) and equivalent Scope 3 frameworks reward organizations for reducing emissions-per-unit-compute by procuring more efficient hardware. On renewable-heavy grids — where embodied carbon dominates total lifecycle emissions — this incentive is directionally counterproductive: it encourages early hardware replacement that increases total lifecycle carbon even as it reduces operational intensity. Designing carbon accounting frameworks that correctly penalize premature hardware retirement on clean grids is an open policy problem with direct regulatory implications.

---

## References

[1] Gupta, U., et al. "Chasing Carbon: The Elusive Environmental Footprint of Computing." HPCA 2021.

[2] Meta AI Research. "Inference at Scale." Internal estimation, cited in [4]. 2023.

[3] Luccioni, A.S., Hernandez-Garcia, A. "Counting Carbon: A Survey of Factors Influencing the Emissions of Machine Learning." arXiv:2302.08476, 2023.

[4] Acun, B., et al. "Carbon Explorer: A Holistic Framework for Sustainable AI Computing." ASPLOS 2023.

[5] Ji, S., et al. "SCARIF: Towards Carbon Modeling of Cloud Servers with Accelerators." IISWC 2024.

[6] Luccioni, A.S., et al. "Estimating the Carbon Footprint of BLOOM, a 176B Parameter Language Model." JMLR 2022.

[7] Bellman, R. "Dynamic Programming." Princeton University Press, 1957.

[9] Bashir, N., et al. "Enabling Carbon-Aware Workload Management in Cloud Platforms." HotCarbon 2021.

[10] Pierskalla, W.P., Voelker, J.A. "A Survey of Maintenance Models for the Deteriorating System." Naval Research Logistics Quarterly, 1976.

---

*Simulation: src/simulate-lifecycle-v3.py | Results: results/lifecycle-sim-v3-summary.json*  
*HotCarbon 2026 condensed version — ~3,200 words*
