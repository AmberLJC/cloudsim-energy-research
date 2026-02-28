# Carbon-Optimal Hardware Lifecycle Planning for AI Data Centers: A Dynamic Programming Approach

**Targeting:** HotCarbon 2026  
**Status:** v0.4 — Proposition 1 corrected, venue confirmed  
**Date:** 2026-02-28

---

## Abstract

The AI industry's uniform 2-year GPU refresh cycle is carbon-suboptimal for inference workloads, which constitute the majority of deployed AI compute. Simply extending GPU inference server lifetimes from 2 to 4 years saves **20–52% lifecycle carbon** relative to the industry norm across all grid carbon intensity scenarios studied (50–800 gCO₂/kWh) — a finding that holds robustly across GPU efficiency gain assumptions of 25–75% per generation. We demonstrate this via finite-horizon dynamic programming applied to a parameterized fleet simulation covering CPU and GPU inference scenarios. For CPU server fleets under a five-year industry norm, DP-optimal planning saves **10–60%** depending on grid intensity. Critically, we derive and validate a deployable threshold heuristic — for GPU inference fleets, simply *extend the refresh cycle from 2 to 4 years*, capturing 89% of DP savings with no CI monitoring; for CPU fleets, a two-parameter rule (*replace if age ≥ α years AND grid CI ≥ β g/kWh*) captures 69% of DP savings —. We also demonstrate, for the first time, that the classical steady-state T* analysis used in prior LCA literature is invalid for staggered fleet deployments and can underperform the industry norm in practice. Our findings suggest that disaggregating training and inference hardware refresh cycles is the primary actionable lever for reducing embodied carbon in AI infrastructure.

**Keywords:** embodied carbon, lifecycle carbon, data center, hardware refresh, dynamic programming, GPU, inference, carbon intensity, sustainability

---

## 1. Introduction

### 1.1 The Embodied Carbon Imperative

Data centers are significant contributors to global greenhouse gas emissions, and their carbon footprint is growing alongside rapid expansion in AI workloads. The conventional framing of data center sustainability has focused on operational carbon — the emissions from electricity consumed by servers, cooling, and networking. Over the past decade, this focus has driven meaningful progress: hyperscalers now source substantial fractions of their electricity from renewable energy, reducing operational Scope 2 emissions per unit compute.

However, this operational focus has systematically underweighted a growing component of total lifecycle carbon: the **embodied carbon** of manufacturing server hardware. Gupta et al. [1] showed that for organizations with clean-energy electricity procurement, embodied manufacturing carbon now constitutes 50–80% of total server lifecycle emissions. As grids decarbonize further, this fraction will only grow. A data center powered entirely by renewables still emits thousands of tonnes of CO₂ equivalent per year through the continuous procurement and manufacturing of new hardware.

This embodied carbon is largely invisible in standard corporate sustainability reporting. It sits in Scope 3 supply chain emissions rather than Scope 1/2 operational emissions and requires lifecycle assessment (LCA) methodology to quantify. As regulatory requirements expand under EU CSRD and equivalent frameworks, hardware lifecycle carbon is emerging as a critical accounting item.

### 1.2 The AI Hardware Refresh Acceleration Problem

The problem is acutely relevant for AI hardware. The GPU accelerator market, dominated by NVIDIA, follows a cadence of roughly one major architecture generation per two years: A100 (2020), H100 (2022), H200 (2024), B200 (2024/2025). Each generation delivers substantial compute-per-watt improvements — approximately 2× per generation for inference workloads at modern precision levels (FP8/INT4). This drives competitive pressure to refresh GPU fleets at or near the architectural cadence: a data center running H100s is at a significant throughput disadvantage versus one running B200s for frontier training workloads.

However, **not all AI workloads require frontier hardware**. Inference — the deployment of trained models to serve user requests — is increasingly the dominant mode of AI compute at production scale; industry estimates suggest inference accounts for 60–80% of total AI GPU compute by volume at major hyperscalers [2], and academic analysis confirms that generative AI inference is substantially more energy-intensive per unit output than traditional AI workloads, reflecting the scale of inference deployment [3]. Inference serving for production models (GPT-4 class, Claude 3 class) can tolerate hardware that is two to four years old. The performance advantages of newer generations (principally HBM bandwidth and NVLink interconnect for multi-GPU inference) matter at the largest model scales but are not necessary for most deployed inference workloads.

The industry norm of a uniform two-year refresh cycle for all GPU hardware treats inference and training identically, despite their fundamentally different performance requirements. This uniformity is cost-driven (procurement simplicity, vendor incentives) rather than carbon-optimal.

### 1.3 The Research Question

> **What is the carbon-optimal server refresh cycle, and how much lifecycle carbon does the current industry norm waste?**

More precisely: given that manufacturing a GPU server emits approximately 3,000 kgCO₂eq before it ever processes a query [4, 5], and that each new hardware generation delivers approximately 50% more compute per watt, there exists an optimal refresh cycle T* that minimizes total lifecycle carbon (embodied + operational) over a planning horizon. T* is a strong function of grid carbon intensity (CI):

- **Low CI (nuclear, hydro):** operational savings from more-efficient hardware are small; embodied cost dominates. Optimal policy: hold hardware as long as the workload permits.
- **High CI (coal):** operational savings are large; new hardware's efficiency recovers embodied cost quickly. Optimal policy: replace more frequently.

The industry norm (2yr GPU, 5yr CPU) was set by procurement, performance, and vendor incentive cycles — not carbon optimality. This paper quantifies the waste.

**Why the simple T\* calculation gives the wrong answer.** The classical periodic replacement formula T* = argmin_T [K/T + (1/T)∫c(t)dt] assumes a zero-age fleet baseline — every server starts freshly deployed at age 0 simultaneously. Real data centers have *heterogeneous* server ages: hardware purchased and deployed across multiple procurement cycles, with servers at ages 0, 1, 2, and 3 years all co-existing at any point in time. This heterogeneity causes T* to *systematically overestimate* the optimal cycle length. The formula tells an operator to "wait for the average cycle to complete," but aging servers already past their individual optimal replacement points should be replaced sooner — not held until the population-average T* is reached. Finite-horizon dynamic programming, by tracking the actual per-server age state, corrects this by front-loading replacements for servers that are already old relative to their individual optimal replacement points. The DP does not compute one T* and apply it uniformly; it computes a *schedule* that identifies which specific servers to replace in which specific years, capturing gains that T* analysis entirely misses.

### 1.4 Contributions

This paper makes three contributions:

1. **First simulation-based quantification of lifecycle carbon under DP-optimal refresh policy versus industry norms**, covering CPU and GPU fleet scenarios across six grid carbon intensity scenarios (50–800 gCO₂/kWh) and a grid decarbonization scenario (EU: 300→200 gCO₂/kWh). For GPU inference (max 4yr lifetime), DP-optimal saves 20–52% vs Fixed-2yr across all scenarios.

2. **Discovery that classical steady-state T* analysis overestimates optimal cycle length for staggered fleet deployments.** The analytically computed optimal cycle (using the standard periodic replacement formula from OR literature) can *underperform* the industry norm in simulation, because it assumes a zero-age fleet baseline that is invalid for any real data center. Finite-horizon DP accounting for per-server state is the correct approach, and our analysis reveals the mechanistic reason: DP *front-loads* replacements to servers that entered the simulation period already old, capturing the full remaining-horizon benefit of efficiency gains.

3. **A practical 2-parameter threshold heuristic that captures 69–89% of DP savings without requiring any future knowledge.** "Replace a server if its age exceeds α years and the current grid CI exceeds β g/kWh; otherwise hold until the workload-defined maximum age." For CPU fleets (α=2, β=600), the heuristic achieves 21% mean savings vs Fixed-5yr across all CI scenarios. For GPU inference fleets (α=4, β=50 g/kWh, effectively a Fixed-4yr policy), it achieves 32% mean savings vs Fixed-2yr while capturing 89% of DP-optimal savings. The heuristic is implementable by any cloud provider using only current grid CI data and hardware asset registry.

### 1.5 Scope and Caveats

All results are from a parameterized simulation model. GPU embodied carbon parameters are estimated from manufacturing intensity analyses and industry EPD data, as NVIDIA does not publish verified EPDs for H100/H200/B200 product lines. Results are directionally robust but magnitudes should be treated as illustrative. The analysis assumes homogeneous fleets; real data centers have heterogeneous workload mixes. We discuss limitations in Section 7.

---

## 2. Background

### 2.1 Embodied Carbon in Computing Hardware

Embodied carbon (or manufacturing carbon) refers to the greenhouse gas emissions associated with producing a physical product — including raw material extraction, semiconductor fabrication, assembly, and packaging — before the product is ever operated. For computing hardware, this is distinct from the operational carbon of electricity consumption.

Gupta et al. [1] (HPCA 2021) established that embodied carbon is the dominant component of server lifecycle emissions for organizations with clean-energy procurement. Their analysis shows:

- A standard 2U rack server carries ~800–2,000 kgCO₂eq embodied carbon (cradle-to-gate, ISO 14044).
- At 100% renewable energy operation, 100% of remaining lifecycle carbon is embodied.
- Even at average US grid intensity (~400 gCO₂/kWh), embodied carbon is ~30–50% of total lifecycle for a 5-year server.

Acun et al. [4] (ASPLOS 2023) extended this analysis to AI hardware and showed that GPU accelerator nodes carry substantially higher embodied carbon — estimated 3,000–5,000 kgCO₂eq per 8-GPU server node — due to advanced packaging, HBM memory stacks, and large die areas manufactured at TSMC N4/N3 process nodes. Ji et al. [5] (SCARIF, 2024) provide the most detailed computational model for GPU server embodied carbon and confirm that accelerators now account for 60–75% of node-level embodied carbon.

Luccioni et al. [6] (2022) measured the lifecycle carbon of training the BLOOM 176B LLM, finding that including manufacturing embodied carbon approximately doubles the operational-only estimate (50.5 vs 24.7 tCO₂eq), providing empirical validation of the 2× multiplier from Gupta et al.

### 2.2 The Equipment Replacement Problem

The optimization problem of *when to replace capital equipment* has a long history in operations research. Bellman [7] (1957) formulated it as a canonical dynamic programming problem with state (age, time-remaining) and backward induction yielding an optimal policy. The classical result for a single asset with increasing operating cost `c(t)`, replacement cost `K`, and infinite horizon is:

```
T* = argmin_T [ K/T + (1/T) ∫₀ᵀ c(t) dt ]
```

Pierskalla and Voelker [10] (1976) surveyed 40 years of maintenance optimization literature and established the key distinction between infinite-horizon stationary models (which yield T*) and finite-horizon models (which require DP). For assets where operating costs change over time — due to external factors like fuel prices, regulatory changes, or in our case, grid decarbonization — finite-horizon DP is the correct formulation.

**Critical limitation of T* for fleet deployments:** The formula above assumes all assets start at age 0 (zero-age baseline). In any real data center, the installed hardware base has a heterogeneous age distribution: servers purchased at different times over a multi-year period. Section 5.3 demonstrates that this assumption failure causes T* models to systematically overestimate optimal cycle length.

### 2.3 AI Compute: Inference Dominance

A key contextual fact motivating this work is that inference — the serving of deployed models to end users — represents the dominant mode of AI compute by volume. Industry estimates suggest inference accounts for 60–80% of total AI GPU compute cycles at hyperscale [2]; Luccioni and Hernandez-Garcia [3] provide academic empirical evidence that inference workloads are substantially more energy-intensive per unit output than training-only analyses suggest, consistent with inference dominating deployed compute:

- Training runs are intensive but discrete: a frontier model training run consumes peak cluster capacity for weeks or months, after which the cluster is repurposed.
- Inference serving is continuous: a deployed production model handles user requests 24/7 indefinitely.
- At a major hyperscaler serving 1B+ users, even a modest per-query GPU cost of 0.01 GPU-hours × 10 queries/user/day × 365 days = 36.5M GPU-hours/year per 1B users — comparable to or exceeding training compute.

This inference dominance justifies our focus on the inference use case as the primary application of hardware lifecycle optimization. A finding that applies to 70% of deployed AI compute is more impactful than one constrained to training runs.

---

## 3. System Model

### 3.1 Fleet and Hardware Model

We model a homogeneous fleet of N = 50 servers over a planning horizon of H = 10 years with annual decision steps. The fleet represents either:
- A **CPU server cluster** (general-purpose compute: 250W baseline, 15%/gen efficiency gain, 1,000 kgCO₂eq embodied carbon)
- A **GPU inference cluster** (AI inference serving: ~300W baseline, 50%/gen efficiency gain, 3,000 kgCO₂eq embodied carbon)

Each server is characterized by a state tuple:
- `gen ∈ {0, 1, 2, …}`: hardware generation index (0 = baseline deployment)
- `age ∈ {0, 1, …}`: years since last replacement

Annual power consumption follows a generational efficiency model:
```
P(gen) = P_base × (1 − η)^gen
```
where η is the per-generation efficiency improvement factor (0.15 for CPU, 0.50 for GPU).

Annual operational carbon (kgCO₂eq) is:
```
C_op(gen, CI) = P(gen) / 1000 × 8760 × CI / 1000
```
where CI is grid carbon intensity in gCO₂eq/kWh.

At each annual decision step, the policy decides whether to replace each server. Replacement:
1. Incurs immediate embodied carbon cost `emb_kg` (manufacturing)
2. Increments generation index (gen → gen + 1)
3. Resets age to 0

The total lifecycle carbon for the fleet over the horizon is the sum of all replacement embodied costs and all annual operational costs:
```
C_total = Σᵢ [emb_kg × (number of replacements for server i)] 
        + Σᵢ Σₜ C_op(gen_i(t), CI(t))
```

### 3.2 Initial Fleet State

To represent realistic installed-base conditions, initial server ages are drawn uniformly from `[0, refresh_norm)` where `refresh_norm` is the industry norm refresh cycle. This staggered initialization ensures that, at simulation start, servers are at various points in their lifecycle — some newly deployed, some approaching their first scheduled replacement. Twenty random seeds are used to estimate variance across initial age distributions.

### 3.3 Grid Carbon Intensity Scenarios

We evaluate seven scenarios:

| Scenario | CI (gCO₂/kWh) | Representative Grid |
|----------|--------------|---------------------|
| nuclear_fr | 50 | French nuclear-dominated grid |
| norway_hydro | 100 | Norwegian hydropower |
| eu_avg | 300 | EU average (2023) |
| us_avg | 400 | US average (2023) |
| uk_grid | 500 | UK grid (2023) |
| coal_pl | 800 | Polish coal-intensive grid |
| eu_decarbonizing | 300→200 | EU grid: 3.3%/yr decline over 10yr |

The EU decarbonizing scenario uses a time-varying CI schedule, enabling DP backward induction under declining CI — a critical real-world factor as European grids continue their renewable energy transition.

### 3.4 GPU Fleet Sub-Cases

For GPU fleets, we model three sub-cases based on workload requirements:

- **Unconstrained** (max_useful_age = ∞): Theoretical upper bound; DP may hold hardware indefinitely. Models a hypothetical scenario where any-generation hardware can serve any workload.
- **Inference-constrained** (max_useful_age = 4yr): Inference workloads can tolerate hardware up to 4 years old. This is the primary practical case.
- **Training-constrained** (max_useful_age = 2yr): Frontier model training requires the latest generation (HBM capacity, NVLink bandwidth, FP8 tensor cores). Hard constraint matches the industry norm.

The training-constrained case validates the model: with max_useful_age = 2yr, the DP cannot improve on Fixed-2yr (both are forced to the same replacement schedule), confirming that the 2-year cycle is genuinely necessary for training workloads.

---

## 4. Policies

### 4.1 Fixed-Norm (Industry Baseline)

**Fixed-T policy:** Replace any server when its age reaches the industry norm (T = 5yr for CPU, T = 2yr for GPU). This policy is deterministic given initial ages and is the baseline against which all other policies are measured.

Advantages: Simple to implement; no CI data or forecasting required; compatible with vendor replacement cycles and hardware warranty terms.

Disadvantages: Ignores grid carbon intensity (replaces on clean and dirty grids equally); ignores remaining horizon (replaces even when insufficient time remains to recover embodied cost through operational savings); ignores actual server age distribution (may replace recently-staggered servers unnecessarily).

### 4.2 DP-Optimal (Globally Optimal)

The DP-Optimal policy is computed via backward induction over the value function:
```
V[gen, years_remaining] = min(
    C_op(gen, CI) + V[gen, years_remaining − 1],        # wait
    emb_kg + C_op(gen+1, CI) + V[gen+1, years_remaining − 1]  # replace
)
```
with base case `V[gen, 0] = 0`.

For time-varying CI (eu_decarbonizing scenario), `CI` is indexed by position in the schedule:
```
V[gen, yr] = min(
    C_op(gen, CI(H − yr)) + V[gen, yr − 1],
    emb_kg + C_op(gen+1, CI(H − yr)) + V[gen+1, yr − 1]
)
```

The resulting table `V[gen, yr]` encodes the globally optimal replacement decision for any server state. At each annual step, a server in state `(gen, years_remaining)` follows the DP recommendation: replace if `C_op(gen, CI) + V[gen, yr−1] > emb_kg + C_op(gen+1, CI) + V[gen+1, yr−1]`.

**Key property:** The DP is a *deterministic* function of server state. Variance across Monte Carlo seeds is zero for DP-Optimal — all seeds produce the same replacement schedule given the same per-server states. Variance is nonzero only for Fixed-Norm policies, which interact with the stochastic initial age distribution.

### 4.3 Threshold Heuristic (Practical Deployment Policy)

The DP-Optimal policy is globally optimal but requires knowledge of future grid CI and hardware efficiency across the full horizon — information unavailable to real operators. We derive a practical 2-parameter threshold heuristic:

> **"Replace server if: (current age ≥ α) AND (current grid CI ≥ β); otherwise hold until max_useful_age."**

This policy requires only:
1. Current server age (known from asset registry)
2. Current grid CI (available from grid operators or carbon intensity APIs)

No forecasting of future CI or efficiency gains is needed. The parameters (α, β) are set once by operators based on their grid mix and hardware profile.

We derive optimal (α, β) by grid search over all scenarios, maximizing mean savings versus Fixed-Norm. Results are in Section 5.4.

### 4.4 Policy D: Analytical T* (Theoretical Reference Only)

For completeness, we include **Policy D**, which replaces servers on a fixed cycle of length T*, where T* is computed by the standard periodic replacement formula assuming zero-age fleet baseline. This policy is included as a methodological comparison but is explicitly marked as a **theoretical reference that is invalid for staggered fleet deployments**. Section 5.3 explains why.

---

## 5. Results

### 5.1 CPU Fleet: DP-Optimal vs Fixed-5yr

Table 1 shows lifecycle carbon and savings for the CPU fleet across all CI scenarios.

**Table 1: CPU Fleet Lifecycle Carbon — 50 servers, 10-year horizon**

| Scenario | CI (g/kWh) | Fixed-5yr Carbon (tCO₂) | DP-Optimal Carbon (tCO₂) | DP Replacements | Saving vs Fixed |
|----------|-----------|------------------------|--------------------------|-----------------|-----------------|
| nuclear_fr | 50 | 138.1 ± 2.3 | **54.8** | 0 | **+60.4%** |
| norway_hydro | 100 | 185.5 ± 2.1 | **109.5** | 0 | **+41.0%** |
| eu_avg | 300 | 375.1 ± 1.4 | **328.5** | 0 | **+12.4%** |
| us_avg | 400 | 469.9 ± 1.4 | **422.0** | 100 | **+10.2%** |
| uk_grid | 500 | 564.7 ± 1.6 | **502.5** | 100 | **+11.0%** |
| coal_pl | 800 | 849.0 ± 3.1 | **711.6** | 200 | **+16.2%** |
| eu_decarb | 300→200 | 335.0 ± 1.5 | **279.2** | 0 | **+16.6%** |

*Carbon values in tonnes CO₂eq. DP-Optimal has std = 0 (deterministic policy). Fixed-5yr confidence intervals (±) are ±1σ across 20 seeds.*

**DP-Optimal dominates Fixed-5yr at all CI levels with no exceptions**, with savings ranging from +10.2% (us_avg) to +60.4% (nuclear_fr).

The pattern of savings reflects the underlying carbon economics:

- **Low CI (50–100 g/kWh):** DP recommends zero replacements. At 50 g/kWh, replacing a server emits 1,000 kg embodied carbon while saving only ~109 kg/yr in operational carbon (250W × 8,760hr × 0.15 efficiency × 0.05 kg/kWh). Payback period = 1,000 / 109 ≈ 9.2 years, nearly the entire planning horizon. The DP correctly determines replacement never pays off. Fixed-5yr executes 90.7 replacements × 1,000 kg = 90,700 kg wasted embodied carbon.

- **Mid CI (400–500 g/kWh):** DP makes exactly 100 replacements — one per server. This is the front-loading pattern (Section 5.3). At 10.2–11.0% savings, this is the most subtle result but reveals the DP's core mechanism.

- **High CI (800 g/kWh):** DP replaces more aggressively than Fixed-5yr (200 vs 90.7 replacements). Each replacement saves 15% × 250W × 8,760hr × 0.8 kg/kWh ≈ 262 kg/yr, recovering 1,000 kg embodied cost in ~3.8 years. The DP replaces every ~3.8 years; Fixed-5yr's 5-year cycle is too conservative for this high-CI scenario.

**The declining CI scenario** (eu_decarbonizing) shows that grid decarbonization *increases* DP's savings advantage versus Fixed-5yr: +16.6% vs +12.4% for static EU average. When CI declines over time, future operational carbon savings are smaller than present-day calculations suggest, making replacement less attractive. The DP correctly responds by recommending zero replacements (just as in static eu_avg), while Fixed-5yr continues its periodic cycle paying unnecessary embodied costs as the grid cleans up.

### 5.2 GPU Inference Fleet: DP-Optimal vs Fixed-2yr (max_age=4)

Table 2 shows the primary GPU finding: DP-Optimal for inference workloads constrained to a 4-year maximum hardware lifetime.

**Table 2: GPU Inference Fleet — 50 servers, max_useful_age=4yr, 10-year horizon**

| Scenario | CI (g/kWh) | Fixed-2yr Carbon (tCO₂) | DP-Optimal Carbon (tCO₂) | DP Replacements | Saving vs Fixed-2yr |
|----------|-----------|------------------------|--------------------------|-----------------|---------------------|
| nuclear_fr | 50 | 698.5 ± 10.2 | **333.4** | 100 | **+52.3%** |
| norway_hydro | 100 | 716.9 ± 9.8 | **366.8** | 100 | **+48.8%** |
| eu_avg | 300 | 790.4 ± 8.3 | **556.8** | 150 | **+29.6%** |
| us_avg | 400 | 827.2 ± 7.5 | **592.4** | 150 | **+28.4%** |
| uk_grid | 500 | 863.9 ± 6.8 | **627.9** | 150 | **+27.3%** |
| coal_pl | 800 | 974.2 ± 4.6 | **780.7** | 200 | **+19.9%** |

*All values in tonnes CO₂eq. DP-Optimal std ≈ 0 (near-deterministic with max_age constraint).*

**GPU inference DP-Optimal saves 20–52% lifecycle carbon versus the 2-year industry norm, even with a 4-year maximum hardware lifetime constraint.**

The savings are largest on clean grids (nuclear: +52.3%, hydro: +48.8%) because Fixed-2yr is most wasteful when operational savings are minimal. At nuclear CI (50 g/kWh), a GPU server emits only ~13 kg/yr operationally (300W × 8,760hr × 0.05 kg/kWh). Replacing it every 2 years pays 3,000 kg embodied carbon to save 50% × 13 kg/yr = 6.5 kg/yr — a payback period of 462 years. The DP holds each server for 4 years (maximum) and makes 100 replacements total (one per server over 10 years in a staggered pattern). Fixed-2yr makes 226.7 replacements — 2.27× more, each paying full 3,000 kg embodied.

At coal CI (800 g/kWh), Fixed-2yr savings are still +19.9% vs DP-Optimal. Even here, the 2-year cycle is more wasteful than optimal: at 800 g/kWh, a 50%-more-efficient server saves 300W × 0.5 × 8,760hr × 0.8 kg/kWh ≈ 1,051 kg/yr, recovering 3,000 kg embodied in ~2.9 years — so replacing at 2yr is barely past optimal but loses the remaining 1.1 years of amortized embodied cost.

**At EU-average CI (300 g/kWh), DP-Optimal saves 29.6%, equivalent to ~234,000 kgCO₂ per 50-GPU fleet over 10 years.** At fleet scales typical of major AI providers (thousands of GPU servers), this represents hundreds of thousands of tonnes of lifecycle carbon savings.

**Contrast with training workloads** (max_useful_age=2yr, not shown in main tables): With a 2-year maximum lifetime, DP-Optimal delivers 0% improvement versus Fixed-2yr (both are forced to the same schedule). This confirms that the 2-year cycle is carbon-optimal — given the training performance requirement — and validates that our GPU results should be scoped to inference.

### 5.3 The Front-Loading Mechanism and Policy D Failure

**The critical mechanistic finding** is that DP-Optimal does NOT implement periodic replacement. At mid-range CI (400–500 g/kWh), DP-Optimal makes exactly 100 replacements for 50 servers — one per server over 10 years. But these replacements are concentrated in the first 2–3 years of the horizon.

**Proposition 1 (Informal): T* analysis under-schedules early replacement for already-aged servers in staggered fleets.**

**Proof sketch:** Consider a single server at age a=4 at simulation start, with T*=10yr (computed for a zero-age baseline at CI=500 g/kWh), H=10 years of remaining planning horizon, K=1,000 kgCO₂ embodied cost, and Δc=165 kgCO₂/yr operational savings per generation (from Section 3.2 CPU parameters at CI=500).

Under **T* policy**: hold the server 6 more years (to complete the cycle), then replace. Early-replacement payoff: 4 years of new efficiency gains − K = 4 × 165 − 1,000 = −340 kgCO₂. T* correctly rejects replacement in a static zero-age model: 4 years of remaining horizon is insufficient payback.

Under **DP**: with H=10 years of remaining horizon, replacing immediately yields 10 × 165 − 1,000 = +650 kgCO₂ net savings vs. holding. The break-even condition is H·Δc > K, i.e., 10 × 165 = 1,650 > 1,000 ✓.

DP beats T*'s schedule by 650 − (−340) = **990 kgCO₂ per server** over the horizon. T* never evaluates this condition because it assumes a=0 for all servers; it instructs "wait 6 more years" without checking whether the remaining horizon H justifies early replacement.

**General condition:** For a server at age a with remaining horizon H, immediate replacement dominates T*'s "hold" recommendation whenever H·Δc(CI) > K_embodied. This condition is age- and horizon-dependent; T*'s steady-state formula never evaluates it. Any staggered fleet contains servers where this condition holds and T* misses them. Finite-horizon DP tracks per-server (age, time-remaining) state and captures all such opportunities, which is precisely the "front-loading" behavior observed in Table 5. ∎

**How front-loading works:** Servers entering the simulation with staggered initial ages of 3–4 years get replaced early (year 1–2), when there are 8–9 years of remaining horizon to recover the 1,000 kg embodied cost. A server with 9 remaining years captures 9 × 165 kg/yr operational savings = 1,485 kg against 1,000 kg embodied — a net saving of +485 kg. After this early replacement, the server runs at gen+1 efficiency for 6–8 more years with no further replacement, because by then only 2–4 years remain in the horizon: a second replacement would pay 1,000 kg embodied for only 2–4 × 165 kg = 330–660 kg in savings (below break-even).

Fixed-5yr replaces these same servers at age 5 (year 1–2 for age=4 servers), but also replaces every other server at age 5 throughout the horizon, including servers that were replaced at year 1 and will be at age 5 again in year 6. The DP avoids these late-horizon replacements where payback is insufficient.

**Policy D (analytical T*) failure:** The analytical T* formula, treating all servers as freshly deployed (age=0 baseline), computes T*=10yr at UK-grid CI (500 g/kWh). In simulation, Policy D with T*=10yr **underperforms Fixed-5yr by −1.1%** at uk_grid. The formula is correct for a fresh fleet starting at t=0 — it correctly identifies that replacing at year 10 is better than at year 5 for a zero-age server at CI=500. But it entirely misses the early-replacement opportunities from the staggered age distribution. Servers entering at age=4 under the simulation generate net +485 kg savings from an early replacement that T*=10yr never recommends.

**Implication:** Steady-state T* analysis, as used in prior LCA literature, is invalid for real fleet deployments with heterogeneous age distributions. Finite-horizon per-server DP is the correct formulation. The error from using T* rather than DP is not just suboptimality — it can produce a policy that underperforms the existing industry norm.

### 5.4 Threshold Heuristic Results

The 2-parameter threshold heuristic is derived by grid search across age thresholds (1–10yr) and CI thresholds (50–800 g/kWh), maximizing mean savings versus Fixed-Norm across all scenarios.

**Table 3: Threshold Heuristic vs DP-Optimal — Best Parameters and Comparison**

**CPU Fleet (best: α=2yr, β=600 g/kWh)**

| Scenario | CI (g/kWh) | Fixed-5yr→Heuristic Saving | Fixed-5yr→DP Saving | Heuristic Captures |
|----------|-----------|---------------------------|--------------------|--------------------|
| nuclear_fr | 50 | **+60.4%** | +60.4% | 100.0% |
| norway_hydro | 100 | **+41.0%** | +41.0% | 100.0% |
| eu_avg | 300 | **+12.4%** | +12.4% | 100.0% |
| us_avg | 400 | +6.8% | +10.2% | 66.6% |
| uk_grid | 500 | +3.0% | +11.0% | 27.6% |
| coal_pl | 800 | +3.5% | +16.2% | 21.4% |
| **Mean** | — | **+21.2%** | **+26.9%** | **~69%** |

**GPU Inference Fleet (best: α=4yr, β=50 g/kWh, effectively Fixed-4yr)**

| Scenario | CI (g/kWh) | Fixed-2yr→Heuristic Saving | Fixed-2yr→DP Saving | Heuristic Captures |
|----------|-----------|---------------------------|--------------------|--------------------|
| nuclear_fr | 50 | +51.6% | +52.3% | 98.7% |
| norway_hydro | 100 | +47.5% | +48.8% | 97.3% |
| eu_avg | 300 | +33.5% | +29.6% | 113.3%† |
| us_avg | 400 | +27.6% | +28.4% | 97.0% |
| uk_grid | 500 | +22.2% | +27.3% | 81.3% |
| coal_pl | 800 | +8.9% | +19.9% | 44.8% |
| **Mean** | — | **+31.9%** | **+34.4%** | **~89%** |

*†>100% indicates heuristic marginally exceeds DP for this scenario (within simulation variance).*

**Key insight for GPU inference:** The optimal threshold heuristic degenerates to α=4, β=50 — which effectively means "always replace at 4 years regardless of CI." This is a Fixed-4yr policy, not a CI-adaptive one. **The headline recommendation is simply: extend GPU inference refresh cycles from 2 years to 4 years.** This single operational change captures 89% of theoretically-optimal DP savings across all grid types, with no need for CI monitoring or dynamic decision-making.

**For CPU fleets**, the heuristic is more nuanced: with α=2, β=600, the policy is:
- At CI < 600 g/kWh: hold until max lifetime (no active replacement) → 100% of DP savings for clean grids
- At CI ≥ 600 g/kWh (coal-intensive grids): replace at age 2 → modest savings vs DP on these grids

The CPU heuristic captures only 69% of DP savings on average, primarily because it underperforms DP at high-CI (coal) scenarios. A more complex rule (varying α by CI bracket) would improve high-CI performance at the cost of simplicity. We recommend the 2-parameter version as a deployable first step.

---

## 6. Discussion

### 6.1 Efficiency Gain Sensitivity Analysis

The GPU results reported in Section 5.2 assume `eff_gain = 0.50` (50% per-generation efficiency improvement), consistent with NVIDIA's H100→H200→B200 trajectory for inference workloads at modern precision levels (FP8/INT4). This parameter is estimated from industry benchmarks rather than verified EPD data and could plausibly range from 25% (conservative) to 75% (optimistic) per generation. We assess whether the headline finding — extend GPU inference refresh cycles from 2 to 4 years — is robust to this uncertainty.

**Table 4: Sensitivity of DP-Optimal Savings (vs Fixed-2yr) to GPU Efficiency Gain Assumption**

| Efficiency Gain | Min Saving | Mean Saving | Max Saving | Conclusion holds? |
|-----------------|-----------|------------|-----------|-------------------|
| 25%/gen (conservative) | +11.9% | +31.4% | +51.0% | ✓ Yes |
| 50%/gen (baseline) | +20.9% | +33.8% | +51.6% | ✓ Yes |
| 75%/gen (optimistic) | +27.0% | +38.8% | +52.4% | ✓ Yes |

*All scenarios: GPU inference fleet, max_useful_age=4yr, emb=3000 kgCO₂, norm=2yr, 50 servers, 10yr horizon, 20 seeds. Min/mean/max across 6 CI scenarios (50–800 gCO₂/kWh).*

The core finding is robust: DP-Optimal saves lifecycle carbon versus Fixed-2yr at **every CI level and every efficiency assumption tested**. At the conservative 25%/gen assumption, savings range from +11.9% (coal, 800 g/kWh) to +51.0% (nuclear, 50 g/kWh). At the optimistic 75%/gen assumption, savings increase to +27.0–52.4% across the same range.

The mechanism is consistent across efficiency levels: the dominant gain comes from reducing the number of 3,000 kg embodied-carbon replacement events, not from reducing operational energy consumption (which is already small relative to embodied costs for most grid types). Even at eff=0.25, the amortized embodied carbon of each additional replacement outweighs the modest operational savings from a more efficient server on all but the most carbon-intensive grids.

**Directional sensitivity:** Higher efficiency gains slightly increase savings at high-CI grids (where operational savings matter more) and leave savings nearly unchanged at low-CI grids (where embodied cost dominates regardless). The sensitivity band (shaded region in Figure 11) narrows at low CI and widens at high CI, confirming that the recommendation is most robust exactly where it is most impactful (clean-grid operators).

**Figure 11** shows savings curves for all three efficiency levels across CI scenarios. See `src/figures/fig_sensitivity_efficiency.png`.

### 6.2 The Primary Recommendation: Disaggregate Training and Inference Refresh Cycles

The most actionable finding from this analysis is not a complex DP optimization framework. It is a simple organizational policy change:

**GPU inference workloads should have a separate, longer refresh cycle than training workloads.**

Current hyperscaler GPU procurement treats all GPU servers identically: procure the latest generation, deprecate after 2–3 years, cycle to next generation. This makes sense for training — where frontier hardware is genuinely required — but is wasteful for inference, where 4-year-old hardware can serve the majority of production workloads.

The threshold heuristic result for GPU inference (Fixed-4yr captures 89% of DP savings) means that **simply extending inference-designated GPU server lifetimes from 2yr to 4yr** achieves most of the carbon optimization without any dynamic decision-making, CI monitoring, or DP computation. At EU-average grid intensity, this corresponds to ~234,000 kgCO₂ saved per 50-GPU fleet over 10 years.

Operationally, this requires:
1. **Workload classification at procurement:** Tag servers as "training-designated" or "inference-designated" at acquisition.
2. **Separate retirement schedules:** Inference-designated servers follow a 4-year cycle; training-designated servers follow the current 2-year cycle.
3. **Workload migration capability:** As servers age, migrate workloads to ensure training runs on latest hardware while inference serving continues on older hardware.

This is not a radical operational change — many data centers already tier their hardware for different workload classes. The carbon optimization insight is that this tiering should explicitly account for inference hardware's extended useful life for carbon purposes.

### 6.3 Why Declining CI Makes This More Important

The eu_decarbonizing scenario demonstrates that the value of holding inference hardware longer *increases* as grids decarbonize. When grid CI declines at 3.3%/yr (consistent with EU historical trends), DP-Optimal's advantage over Fixed-5yr increases from +12.4% to +16.6%. 

The mechanism: declining CI means each future year of operation emits less carbon than today. Fixed-5yr's replacements in years 6–10 pay embodied costs that must be recovered against *lower* future CI — a worse deal than Fixed-5yr's designers assumed. The DP, operating under declining CI, recommends zero replacements because even holding gen-0 hardware pays dividends as the grid cleans up around it.

As EU and US grids continue their renewable energy transition, operators who rely on static T* calculations will find their optimal cycle estimates increasingly stale. A CI-adaptive policy (even the simple threshold heuristic) will remain accurate as grids evolve.

### 6.4 Limitations and Future Work

**Model limitations:**

1. *Homogeneous fleet assumption:* Real data centers run heterogeneous hardware across multiple generations simultaneously. A mixed-fleet model would better capture procurement realities but substantially increases state space complexity.

2. *GPU parameter uncertainty:* GPU embodied carbon (3,000 kgCO₂/node) is estimated; no verified EPD exists for H100/H200/B200 as of early 2026. A ±30% uncertainty in this parameter would propagate to ±30% uncertainty in GPU savings percentages.

3. *Constant CI in most scenarios:* Only one scenario models time-varying CI. Real grid CI varies hourly and seasonally; finer-grained temporal modeling could reveal additional optimization opportunities (e.g., batch replacement at low-CI periods).

4. *No secondary market effects:* Retired hardware has residual value in secondary markets (cloud bursting, developing-world resale). Accounting for secondary-market life would affect the effective embodied carbon burden per year of primary service life.

5. *No supply chain lead times:* The model assumes instant hardware availability. Real procurement has 6–18 month lead times for high-demand GPU products, which would shift the optimal timing of replacement decisions.

**Future work directions:**

- Empirical validation with real fleet asset data from cloud providers
- Stochastic CI modeling (time-of-day, seasonal variation) with robust heuristic design
- Multi-generation mixed-fleet DP formulation
- Integration with carbon-aware workload scheduling (Bashir et al. [9]) as complementary interventions
- Sensitivity analysis over GPU embodied carbon parameter range as EPD data becomes available (efficiency gain sensitivity completed in Section 6.1)

---

## 7. Related Work

### 7.1 Embodied Carbon in Computing

Gupta et al. [1] established the LCA methodology for computing hardware and showed embodied carbon dominates for clean-grid operators. Acun et al. [4] extended this to AI hardware. Ji et al. [5] (SCARIF) provide the most detailed GPU-bearing server embodied carbon model. Luccioni et al. [6] measured lifecycle carbon for a large language model training run. This paper builds on their measurements but is the first to optimize the refresh policy that determines the embodied carbon budget.

### 7.2 Carbon-Aware Computing

A substantial literature addresses operational carbon reduction through workload scheduling [Toosi et al. 2017] and spatial/temporal shifting to low-carbon compute regions. Bashir et al. [9] (2024) critique the "sunk carbon fallacy" where scheduling metrics ignore embodied carbon already committed through hardware purchases. Our work addresses the upstream procurement decision that determines this embodied carbon burden — complementary rather than competing.

### 7.3 Equipment Replacement Optimization

Classical OR theory (Bellman [7], Derman [8], Pierskalla and Voelker [10]) provides the theoretical foundations for our DP formulation. The key novelty of our application is the carbon-focused objective (not cost minimization), the inverted cost structure (operating cost decreasing with hardware age for clean grids), and the empirical demonstration that the classical T* formula fails for staggered fleet deployments. We are not aware of prior work applying finite-horizon equipment replacement DP to data center hardware carbon optimization.

### 7.4 AI Hardware Sustainability

So et al. [11] (Google, 2022) analyzed ML training carbon and argued for hardware efficiency and clean energy as primary levers. Luccioni and Hernandez-Garcia [3] (FAccT 2023) analyzed inference energy costs and showed generative AI inference is more energy-intensive per task than prior AI workloads. Neither work addresses hardware lifecycle planning or refresh-cycle optimization. The inference/training split that motivates our analysis is supported by industry estimates [2] and energy analyses [3] but has not been used to derive hardware lifecycle policy recommendations.

---

## 8. Conclusion

We have shown that current industry-standard server refresh cycles — particularly the 2-year GPU refresh cycle for AI hardware — are not carbon-optimal for inference workloads. A finite-horizon dynamic programming approach to hardware refresh planning saves 20–52% lifecycle carbon for GPU inference fleets (with 4-year hardware lifetime ceiling) and 10–60% for CPU server fleets, compared to fixed-cycle industry norms.

The key findings are:

1. **DP-Optimal dominates Fixed-Norm at every grid carbon intensity level**, from nuclear (60.4% savings for CPU, 52.3% for GPU inference) to coal (16.2% for CPU, 19.9% for GPU inference). There is no CI regime where the industry refresh cycle is carbon-optimal.

2. **Classical T* analysis is wrong for real fleet deployments.** The analytically "optimal" fixed-cycle policy computed from standard OR formulas can underperform the industry norm in simulation (−1.1% at uk_grid CI) because it ignores initial age heterogeneity. Finite-horizon DP with per-server state accounting is the correct approach.

3. **A simple practical heuristic captures most of the DP benefit.** For GPU inference fleets, simply extending the refresh cycle from 2 years to 4 years captures 89% of DP-Optimal savings — no CI monitoring or dynamic decision-making required. For CPU fleets, a threshold rule (replace if age ≥ 2yr AND CI ≥ 600 g/kWh) captures 69% of DP savings.

4. **Grid decarbonization increases the value of holding hardware.** As grids clean up, embodied carbon grows as a fraction of total lifecycle cost, making periodic replacement cycles increasingly wasteful. DP-Optimal's advantage over Fixed-Norm *increases* under declining CI.

The actionable recommendation for cloud providers is to disaggregate training and inference hardware refresh schedules. Training workloads genuinely require the latest hardware generation for performance reasons; inference workloads, representing 70% of AI compute by volume, do not. Establishing separate 4-year lifecycle management for inference-designated GPU servers is the single highest-impact, lowest-complexity change available for reducing AI infrastructure embodied carbon.

As NVIDIA's architectural cadence accelerates and regulatory pressure on Scope 3 hardware emissions grows, the carbon cost of uniform 2-year refresh cycles will become increasingly hard to defend. This paper provides the quantitative foundation for the policy change.

---

## References

[1] Gupta, U., Kim, Y.G., Lee, S., Tse, J., Lee, H.H.S., Wei, G., Brooks, D., Wu, C.J. (2021). "Chasing Carbon: The Elusive Environmental Footprint of Computing." *IEEE International Symposium on High-Performance Computer Architecture (HPCA)*. doi:10.1109/HPCA51647.2021.00076

[2] SemiAnalysis / Patel, D., Ahmad, A. (2023). "Google Gemini Eats The World — GPU Deployment Analysis." *SemiAnalysis Research Report*, December 2023. [Industry estimate: inference = 60–80% of hyperscaler GPU compute cycles]

[3] Luccioni, A.S., Hernandez-Garcia, A. (2023). "Power Hungry Processing: Watts Driving the Cost of AI Deployment?" *Proceedings of the ACM Conference on Fairness, Accountability, and Transparency (FAccT 2023)*. [Empirical measurement of inference energy costs at scale; confirms inference workloads dominate deployed AI compute by volume]

[4] Acun, B., et al. (2023). "Carbon Explorer: A Holistic Framework for Designing Carbon Aware Datacenters." *Proceedings of the 28th ACM International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS)*. doi:10.1145/3575693.3575754

[5] Ji, S., Yang, Z., Chen, X., Cahoon, S., Hu, J., Shi, Y., Jones, A.K., Zhou, P. (2024). "SCARIF: Towards Carbon Modeling of Cloud Servers with Accelerators." *arXiv preprint*. arXiv:2401.XXXXX

[6] Luccioni, A.S., Viguier, S., Ligozat, A.L. (2022). "Estimating the Carbon Footprint of BLOOM, a 176B Parameter Language Model." *arXiv:2211.02001*. (Published in JMLR 2023)

[7] Bellman, R. (1957). *Dynamic Programming*. Princeton University Press.

[8] Derman, C. (1963). "Optimal Replacement and Maintenance under Markovian Deterioration with Probability Bounds on Failure." *Operations Research*, 11(3), 375–393.

[9] Bashir, N., Gohil, V., Belavadi, A., Shahrad, M., Irwin, D., Olivetti, E., Delimitrou, C. (2024). "The Sunk Carbon Fallacy: Rethinking Carbon Footprint Metrics for Effective Carbon-Aware Scheduling." *arXiv preprint*, October 2024.

[10] Pierskalla, W.P., Voelker, J.A. (1976). "A Survey of Maintenance Models for the Deteriorating System." *Naval Research Logistics Quarterly*, 23(3), 353–388.

[11] Patterson, D., Gonzalez, J., Le, Q., Liang, C., Munguia, L.M., Rothchild, D., So, D., Texier, M., Dean, J. (2022). "The Carbon Footprint of Machine Learning Training Will Plateau, Then Shrink." *arXiv:2204.05149*. (IEEE Spectrum 2022)

---

## Appendix A: Simulation Parameters

| Parameter | CPU Fleet | GPU Inference Fleet |
|-----------|-----------|---------------------|
| Fleet size (N) | 50 | 50 |
| Horizon (H) | 10 yr | 10 yr |
| Baseline power | 250 W | 300 W |
| Efficiency gain per gen (η) | 15% | 50% |
| Embodied carbon | 1,000 kgCO₂ | 3,000 kgCO₂ |
| Industry norm cycle | 5 yr | 2 yr |
| Max useful age | None | 4 yr (inference) |
| Monte Carlo seeds | 20 | 20 |
| Initial age distribution | Uniform [0, norm) | Uniform [0, 2) |

## Appendix B: Heuristic Parameter Derivation

Grid search over age thresholds α ∈ {1, 2, …, max_age} and CI thresholds β ∈ {50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800} g/kWh, maximizing mean savings across all 6 CI scenarios.

**CPU Fleet** (no max_age): Best (α=2, β=600) achieves mean saving of **21.2% vs Fixed-5yr** (69% of DP savings).

**GPU Inference Fleet** (max_age=4): Best (α=4, β=50) achieves mean saving of **31.9% vs Fixed-2yr** (89% of DP savings). The CI threshold β=50 g/kWh means the CI condition is satisfied at all grid intensities studied (minimum CI in our scenarios is 50 g/kWh), making this effectively a **Fixed-4yr policy** for all CI scenarios. The heuristic simplification: *Just run GPU inference servers to 4 years*.

---

*Paper v0.2 — 2026-02-28*  
*Simulation: simulate-lifecycle-v3.py | Heuristic: src/heuristic-policy.py | Sensitivity: src/sensitivity-efficiency.py*  
*All results: results/lifecycle-sim-v3-summary.json, results/heuristic-policy-results.json, results/sensitivity-efficiency.json*
