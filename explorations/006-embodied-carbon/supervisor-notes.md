# Supervisor Notes — 006 Embodied Carbon
**Date:** 2026-02-28  
**Supervisor cycle:** 2  
**Phase at time of review:** Post-fleet-simulation-v2 (simulate-lifecycle-v2.py complete, DP-Optimal fix verified)

---

## Summary of Current State

The previous cycle's validity problem (CRITICAL: myopic CI-Aware policy making zero replacements at EU-average CI) has been fixed. `simulate-lifecycle-v2.py` correctly implements backward-induction DP-Optimal, and the DP-Oracle matches DP-Optimal exactly (0.000000% gap) — confirming the DP implementation is correct.

Current results (DP-Optimal vs Fixed-5yr, CPU fleet):
- nuclear_fr (CI=50): **+60.4%** savings
- norway_hydro (CI=100): **+41.0%**
- eu_avg (CI=300): **+12.4%**
- us_avg (CI=400): **+10.2%**
- uk_grid (CI=500): **+11.0%**
- coal_pl (CI=800): **+16.2%**

GPU results (DP-Optimal vs Fixed-2yr):
- nuclear_fr: **+92.2%** (0 replacements)
- eu_avg: **+60.2%** (50 replacements, T*=10yr)
- us_avg: **+55.4%**
- coal_pl: **+44.5%** (T*=5yr)

---

## 🟡 CYCLE 2 CRITIQUE — THREE PROBLEMS

### Problem 1 (CRITICAL): GPU scenario assumes performance obsolescence doesn't exist

**This is the biggest unaddressed problem in the paper.**

DP-Optimal saves 92.2% on nuclear/hydro grids by making **zero GPU replacements** over 10 years. The model is numerically correct — if you keep a 10-year-old GPU server, you avoid 226.7 embodied carbon events per fleet, each at 3000 kgCO₂ = 680,100 kgCO₂ saved.

**The problem:** The model assumes old hardware can continue serving workloads indefinitely. For AI accelerators, this is false in most deployment contexts:
- Large model training (GPT-5 scale) requires H200/B200 memory bandwidth and FP8 tensor cores — cannot run on H100 hardware at all
- Even inference loads grow: serving a model that requires 192GB VRAM cannot run on 80GB H100s

**The question the paper must answer:** *What fraction of GPU workloads can tolerate n-year-old hardware?*

If the answer is "0% for training, maybe 30% for legacy inference," then the headline finding of "92% savings by never replacing" is operationally meaningless for the primary use case.

**The valid framing:** "For inference workloads on non-frontier models (code completion, document analysis, etc.), 4-year-old GPUs remain competitive. For this subset, the 2-year industry refresh cycle is unjustified and wastes 44-92% embodied carbon." This is still a strong finding, but requires explicit scoping.

**Required action before paper writing:** Add a **workload obsolescence parameter** `max_useful_age_yr` (e.g., 4yr for inference, 2yr for training). The DP should be constrained: if `server.age >= max_useful_age_yr`, forced replacement regardless of CI. Re-run GPU scenario with `max_useful_age_yr = 4` and show that savings drop to X% but remain substantial.

---

### Problem 2 (MEDIUM): Policy D (Fixed-T*) underperforms Fixed-5yr at uk_grid

From the JSON results:
```
uk_grid (CI=500): T*=10, Policy D saves -1.06% vs Fixed-5yr (i.e., WORSE)
```

Policy D replaces every T*=10yr. Fixed-5yr replaces every 5yr. At CI=500, more frequent replacement should save operational carbon. If T*=10yr is the "analytically optimal" cycle, it must outperform T*=5yr. The fact that it doesn't is a bug — either in `compute_total_carbon_fixed()` (computes T* incorrectly) or in the simulation (executes Fixed-T* policy incorrectly).

This is observable by any reviewer who runs the code. It undermines the "Fixed-T* policy" as a deployable recommendation.

**Diagnostic question:** At CI=500, with eff_gain=0.15, emb=1000, what does the closed-form T* formula return? The falsification script should give this. If it returns T*=5 (not T*=10), then the simulation's T* lookup is wrong.

**Required action:** Debug `compute_optimal_T_star()` at CI=500 and verify the result matches the DP-Optimal's effective replacement period. If the analytical T* is 5yr at CI=500, fix the T* lookup in simulate-lifecycle-v2.py.

---

### Problem 3 (MEDIUM): Zero variance across 20 seeds for DP policies

```json
"policy_Bdp": { "std_carbon": 0.0, "mean_replacements": 0.0 }  (nuclear_fr)
"policy_Bdp": { "std_carbon": 0.0, "mean_replacements": 100.0 }  (us_avg)
```

ALL DP policies have exactly zero standard deviation across 20 Monte Carlo seeds. The stated purpose of multi-seed simulation is "Monte Carlo fleet heterogeneity." But if every seed gives identical carbon, the seeds aren't doing anything.

**Likely cause:** The DP replacement decision is purely a function of `(gen, years_remaining, CI)` — it's deterministic. If all servers start at generation 0 and age identically, there is no fleet heterogeneity to sample. The randomness in the simulation may only affect the *stochastic arrival of VMs*, but if lifecycle carbon is calculated from fleet totals independent of VM arrivals, the 20-seed spread is vacuous.

**Implication:** The Monte Carlo confidence intervals in the paper will show zero width for DP policies. This looks suspicious. More importantly, it means the paper is *not* testing robustness to fleet heterogeneity, which is a real-world concern (servers fail, are deployed at different ages, have different workload patterns).

**Required action:** Clarify in the paper methodology section what the 20 seeds actually vary. If seeds don't produce variance in DP results, remove the multi-seed framing for DP policies and note that DP gives a deterministic optimum.

---

## 🟡 SECONDARY OBSERVATION: Contribution Framing Problem

The LOGBOX says: "DP-Optimal beats industry norm at ALL grid types."

**A skeptical reviewer will note:** DP is optimal BY CONSTRUCTION. Of course it beats fixed schedules. This is mathematical triviality, not a research contribution.

The actual contributions are:
1. **Quantification** — DP reveals that Fixed-5yr wastes 10-60% lifecycle carbon; Fixed-2yr GPU wastes 44-92%
2. **The T* insight** — optimal refresh period spans 2-10yr depending on CI; a simple lookup achieves most of the benefit
3. **The actionable policy** — "if CI < 280 g/kWh, never refresh within a 10yr horizon" is a clean, deployable rule

The paper should NOT be framed as "we propose DP-Optimal." It should be framed as "we characterize T*(CI, eff, emb) and show that simple T*-based policies achieve near-optimal results — and that the industry norm is dramatically suboptimal for renewable-heavy grids."

The **DP is a theoretical benchmark**, not the contribution. The contribution is the T* characterization and its gap from industry practice.

---

## 🔴 OPEN QUESTION: Declining CI trend

All simulations use **constant CI** over the 10-year horizon. But EU and US grids are actively decarbonizing (~3-5% CI reduction/year). If CI is declining:

- Old hardware becomes relatively MORE attractive over time (operational carbon per kWh decreases)
- T* increases (you should keep hardware even longer than the constant-CI model predicts)
- The savings from DP vs Fixed-5yr may be even larger than shown

Conversely, for coal-heavy grids, if they're also decarbonizing, T* there increases too.

This is a "robustness" question, but it's also potentially a significant finding that strengthens the paper. The paper should include at least a brief sensitivity analysis with linearly declining CI (e.g., EU: 300 → 200 g/kWh over 10yr).

---

## Supervisor Directive — Required Before Lit Review + Paper Writing

Do NOT proceed to lit-review-embodied.md until the following are resolved:

### Must-Fix (blocks paper validity):
1. **GPU performance obsolescence model** — add `max_useful_age_yr` parameter; re-run GPU scenario with `max_useful_age_yr=4`; show how findings change
2. **Policy D T* bug at uk_grid** — investigate and fix the -1.06% anomaly
3. **Clarify seed variance** — document what 20 seeds vary; if DP is deterministic, say so explicitly

### Should-Address (strengthens paper):
4. **Declining CI sensitivity** — run one additional condition: EU grid decarbonizing from 300→200 g/kWh over 10yr; show directional impact on T*
5. **Reframe contribution** — DP is a benchmark, not the contribution; T* characterization is the contribution

### Then Proceed to:
- lit-review-embodied.md (confirm novelty gap, especially for T* LCA literature)
- analysis-embodied.md (write up clean results with the fixed GPU model)
- paper.md first draft

---

## What IS publication-ready:

1. **T* framework** — clean analytical result showing 2-10yr range across CI values
2. **CPU fleet findings** — DP vs Fixed-5yr, savings 10-60%, well-motivated
3. **GPU comparison, scoped correctly** — "for workloads tolerant of n-year-old hardware..."
4. **Crossover CI concept** — below 280 g/kWh: never replace in 10yr horizon

The direction is strong (4.8/5 score) and the findings are genuinely interesting. But the GPU scenario needs operational grounding before it can anchor a paper headline.

---

## Specific Challenge for the Researcher

**The uncomfortable question:**

> If your main finding is "AI GPU companies should stop replacing hardware every 2 years on nuclear/hydro grids," but those companies *must* replace hardware every 2 years to train frontier AI models — are you solving the right problem? 

> The answer is probably "yes, for inference infrastructure" — but you need to say this explicitly, and your model needs to validate it (via `max_useful_age_yr`). Right now the model is agnostic about workload requirements, which means the GPU result is a theoretical number with unclear operational scope.

This is the question a program committee will ask at CCGRID or EuroSys. Answer it proactively in the model.

---
*Supervisor: auto-generated advisory cycle 2 | 2026-02-28 00:25 UTC*

---

## Previous Cycle Notes (Cycle 1 — 2026-02-28 00:05 UTC)

[Archived below — original bug report and DP fix directive; fixed in Entry #38]

---

### 🔴 CRITICAL VALIDITY PROBLEM (RESOLVED — Fixed in simulate-lifecycle-v2.py)

*(Entry #37 bug: CI-Aware policy was myopic greedy, made zero replacements at EU-avg CI, -61.6% "savings" was catastrophically wrong. Policy D implementation also had issues. Both fixed in v2 with DP-Optimal backward induction.)*

*Archived — no longer active problems.*
