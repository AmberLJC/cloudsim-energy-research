# Supervisor Notes — 006 Embodied Carbon
**Date:** 2026-02-28  
**Supervisor cycle:** 3  
**Phase at time of review:** Post-fleet-simulation-v2 (STALLED — cycle-2 directives not actioned)

---

## ⚠️ CYCLE 3 STATUS: THREE MUST-FIX ITEMS FROM CYCLE-2 REMAIN UNADDRESSED

No new research files have been committed since the cycle-2 supervisor notes (commit `a04251a`). The last research commit is `c5c13b5` (simulate-lifecycle-v2.py). All three "must-fix before proceeding" items from cycle-2 are still open. **Spawning a worker this cycle to address them directly.**

---

## CYCLE 3 CRITIQUE — FOUR PROBLEMS (1 new, 3 carried from cycle-2)

---

### Problem 1 (CRITICAL — CARRIED): GPU performance obsolescence still unmodeled

`simulate-lifecycle-v2.py` still has no `max_useful_age_yr` constraint. DP-Optimal recommends **zero GPU replacements** at CI ≤ 300 g/kWh (nuclear, hydro, EU average). The interpretation: keep a 2024 H100 until 2034.

This is operationally impossible for:
- **Training workloads**: GPT-5/6-scale models need FP8 tensor cores, 192GB+ HBM, NVLink bandwidth that H100 simply cannot provide.
- **Inference at scale**: Models growing from 70B→405B→2T parameters cannot run on 2024 VRAM sizes.

The 92.2% savings headline on nuclear grids is a number computed from a model that ignores hardware obsolescence. **Without bounding this, no program committee will accept the GPU result as valid.**

**Required action (STILL OPEN):** Create `simulate-lifecycle-v3.py` with `max_useful_age_yr` parameter (set to 4yr for GPU inference use case, 3yr for training). Show how GPU savings change with this constraint. The finding will still be strong (comparing DP-optimal to Fixed-2yr within a 4yr max lifetime is still a meaningful question), but it will be honest.

---

### Problem 2 (CRITICAL — NEW): Policy D analytical T* has a structural flaw

Running the analytical formula reveals: at CI=500, `find_t_star()` returns **T*=10**, but the DP policy replaces each server approximately once in the first 5 years (100 total replacements for 50 servers) — an effective cycle of ~5yr. These cannot both be right.

**Root cause, confirmed by manual calculation:**

The `compute_total_carbon_fixed()` formula starts with a fresh server at generation 0 at t=0 (no initial age). For T=10 at CI=500: 1 deployment, 10yr gen-0 operation = 11,950 kgCO₂ per server. For T=5: 2 deployments, 5yr gen-0 + 5yr gen-1 = 12,125 kgCO₂. T=10 wins by 175 kgCO₂ (1.5%).

**But the simulation starts with staggered initial ages 0..4.** A server starting at age 4 under Fixed-5yr replaces at year 1, getting **9 more years of gen-1 savings** (9 × 165 kgCO₂/yr = 1,485 kgCO₂) for 1,000 kgCO₂ embodied — a net +485 kgCO₂ saving. The analytical formula never sees this early-replacement case, so it underestimates the value of Fixed-5yr.

**This is not just a bug in Policy D** — it reveals a richer finding:

> DP-Optimal does NOT do periodic replacement. It does **front-loaded replacement**: it replaces servers that are old at deployment time and then holds new servers for the remainder of the horizon. The analytical T* formula (assuming all servers start fresh) gives a systematically wrong policy for realistic fleet deployments.

This is actually a **publishable insight**: "Steady-state T* analysis overestimates optimal cycle length by 40-100% for typical fleet age distributions; finite-horizon DP should be used instead."

**Required action:** 
1. Remove Policy D ("Fixed-T*") as a deployment recommendation from the paper (it's demonstrably wrong for staggered fleets).
2. Replace with a note that steady-state T* is only valid for single-server infinite-horizon analysis.
3. Add a short section on the DP's front-loading behavior as a finding.

---

### Problem 3 (MEDIUM — CARRIED): Zero variance in DP seeds is NOT documented

All DP policies have `std_carbon = 0.0` across 20 seeds. The simulation uses `rng.integers(0, max_initial_age)` for initial age stagger — this IS stochastic. But DP decisions are deterministic given `(gen, years_remaining)`, and all seeds start at the same generation distribution. The variance in Fixed-5yr comes from its interaction with stochastic initial ages — but the DP table is pre-built from CI alone, so every seed produces the SAME DP replacement schedule.

The 20-seed design is vacuous for DP policies. The paper must not present confidence intervals for DP results as if they were Monte Carlo validated. 

**Required action:** Add explicit methodology note to the paper: "DP-Optimal is a deterministic policy; variance across seeds is zero by construction. Confidence intervals are reported only for fixed-period heuristics, where initial age stagger introduces run-to-run variance."

---

### Problem 4 (MEDIUM — NEW): The DP result at us_avg/uk_grid needs mechanistic explanation

At CI=400 (us_avg) and CI=500 (uk_grid), DP-Optimal makes **100 replacements** for 50 servers — approximately one replacement per server over 10 years. This is the front-loading pattern: replace old servers early in the horizon, then hold.

The paper currently claims "DP-Optimal beats Fixed-5yr by 10.2-11.0%." But **how** DP achieves this is just as important as the quantitative result. Without explaining the front-loading mechanism, readers will assume DP is a dynamic version of Fixed-T* (periodically replacing based on CI), which is wrong.

**Required action:** Add mechanism analysis to analysis-embodied.md: "At mid-range CI (400–500 g/kWh), DP-Optimal replaces servers front-loaded in the first 3 years (when horizon is long and payback is favorable), then avoids further replacement. This contrasts with Fixed-5yr (uniform periodic cycles) and generates 10-11% savings because early replacements capture the full gen+1 efficiency benefit over the remaining horizon."

---

## SUPERVISOR DIRECTIVE — Cycle 3

### Must-Fix (blocks paper validity):
1. **`simulate-lifecycle-v3.py`** — add `max_useful_age_yr` constraint to GPU scenario (4yr inference, 3yr training); report how GPU savings change; still compare DP-optimal vs Fixed-2yr within the constraint
2. **Remove Policy D as a recommendation** — document the analytical T* flaw; add front-loading mechanism analysis
3. **Clarify seed methodology** — explicit methodology note on DP determinism

### Should-Do (strengthens paper):
4. **Declining CI sensitivity** — EU grid: 300→200 g/kWh linear decline over 10yr; show directional impact on T* and DP savings
5. **Write analysis-embodied.md** — full results writeup with the corrected model

### Then Proceed to:
- `lit-review-embodied.md`
- `paper.md` first draft

---

## What Should Be Done This Cycle (Worker Task)

The worker spawned this cycle should:
1. Create `simulate-lifecycle-v3.py` with `max_useful_age_yr` parameter and declining-CI sensitivity
2. Run it; save results to `results/lifecycle-sim-v3-summary.json`
3. Generate updated figures (update fig8/fig9 or add fig10/fig11 for GPU-constrained and declining-CI results)
4. Write `analysis-embodied.md` documenting: (a) clean CPU fleet findings, (b) GPU findings under 4yr constraint, (c) front-loading mechanism, (d) DP seed methodology note, (e) declining CI direction
5. Commit with message: "research: 006 v3 — max_useful_age GPU constraint + declining CI + analysis writeup"

---

## The Uncomfortable Question (still unasked until now)

> The paper's most dramatic finding is that AI companies waste 44-92% embodied carbon by following 2-year GPU refresh cycles. But the companies doing this are NOT doing it because they're ignorant of lifecycle carbon — they're doing it because the performance improvement (2× compute/watt per generation) is essential for competitive model training. If you cannot change the GPU refresh cycle for training workloads, and you need to scope the paper to "inference-only" — is the finding still headline-worthy?

The answer might be: "yes — inference workloads are 70-80% of total AI compute, so constraining to inference is still a big market." But **the paper needs to make this argument explicitly**, and the model needs to validate it by showing results for inference (max 4yr lifetime) as the primary case.

---

## Previous Cycle Notes (Cycle 2 — 2026-02-28 00:25 UTC)

[Archived below for reference — three problems identified: GPU obsolescence, Policy D bug, seed variance]

---

*Supervisor: auto-generated advisory cycle 3 | 2026-02-28 00:45 UTC*

---

## Previous Cycle Notes (Cycle 1 — 2026-02-28 00:05 UTC)

[Archived below — original bug report and DP fix directive; fixed in simulate-lifecycle-v2.py]

---

### 🔴 CRITICAL VALIDITY PROBLEM (RESOLVED — Fixed in simulate-lifecycle-v2.py)

*(Entry #37 bug: CI-Aware policy was myopic greedy, made zero replacements at EU-avg CI, -61.6% "savings" was catastrophically wrong. Policy D implementation also had issues. Both fixed in v2 with DP-Optimal backward induction.)*

*Archived — no longer active problems.*

---

## Archived: Cycle 2 Notes (Summary of Problems)

### Problem 1: GPU performance obsolescence not modeled (STILL OPEN)
DP-Optimal recommends 0 GPU replacements at nuclear/hydro. Unrealistic for AI workloads.
Fix: add `max_useful_age_yr` parameter. Re-run GPU with 4yr inference lifetime.

### Problem 2: Policy D T* bug at uk_grid (NOW DIAGNOSED — deeper than initially thought)
T*=10 gives -1.1% vs Fixed-5yr. Root cause: analytical formula assumes fresh fleet, simulation uses staggered ages. The formula is wrong for fleet deployments. Fix: remove Policy D as recommendation; document as methodological finding.

### Problem 3: Zero variance in DP seeds (STILL OPEN — needs documentation)
All DP policies have std=0.0. 20-seed Monte Carlo is vacuous for DP. Needs explicit methodology note.

### Secondary observation: Contribution framing
DP is a mathematical benchmark, not the contribution. T* characterization and front-loading finding are the contribution. Paper should be framed accordingly.

### Open question: Declining CI trend
All simulations use constant CI over 10yr. EU/US grids decarbonize ~3-5%/yr. Declining CI makes holding old hardware even MORE attractive. Brief sensitivity needed.
