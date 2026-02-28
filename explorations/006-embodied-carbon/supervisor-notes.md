# Supervisor Notes — 006 Embodied Carbon
**Date:** 2026-02-28  
**Supervisor cycle:** 1  
**Phase at time of review:** Post-fleet-simulation (simulate-lifecycle.py complete)

---

## 🔴 CRITICAL VALIDITY PROBLEM — REVIEW BEFORE PROCEEDING

I ran the actual simulation. The results are substantially different from what LOGBOX Entry #37 implies.

### Actual summary table from simulate-lifecycle.py:

| Scenario | CI (g/kWh) | B (CI-Aware) vs A | C (Oracle) vs A |
|---|---|---|---|
| nuclear_fr | 50 | +50.0% ✅ | +50.0% ✅ |
| norway_hydro | 100 | +14.6% ✅ | +13.9% ✅ |
| **eu_avg** | **300** | **-61.6% 🔴 CATASTROPHIC FAILURE** | -3.7% |
| us_avg | 400 | +69.6% ✅ | -2.3% 🟡 |
| uk_grid | 500 | +72.7% ✅ | +16.5% ✅ |
| coal_pl | 800 | +78.9% ✅ | +19.9% ✅ |

**LOGBOX #37 cherry-picked** the low and high CI extremes and called this "14.6–78.9% savings." It skipped eu_avg, which is -61.6% (CI-Aware is 61.6% WORSE than the industry norm at the global average carbon intensity).

---

## Root Cause Diagnosis

### Bug 1: CI-Aware policy is a myopic greedy comparison, not a multi-period optimizer

The CI-Aware logic compares: `fwd_old(keep forever)` vs `fwd_new(replace once + keep until horizon)`.

At CI=300 g/kWh, for a gen-0 server:
- fwd_old = 250W × 8760h × 0.3 kg/kWh × 10yr = 6,570 kgCO₂  
- fwd_new = 212.5W × 8760h × 0.3 kg/kWh × 10yr + 1000 = 5,584 + 1000 = 6,584 kgCO₂  
- **Result: fwd_old < fwd_new → NEVER replace (at any year in the horizon)**

The policy assumes you only ever replace once. It never asks "what if I replace at year 5 AND year 10?" A multi-period policy would identify that replacing at T*=5yr is optimal at CI=300 — which is exactly what Fixed-5yr does.

**Diagnostic confirmed**: Oracle T* calculation returns T*=5yr at CI=300–400, validating that Fixed-5yr IS near-optimal at global-average CI. CI-Aware's zero-replacement decision is wrong.

### Bug 2: Oracle performs worse than Fixed-5yr at CI=300 and CI=400

Oracle saves -3.7% (CI=300) and -2.3% (CI=400) vs Fixed-5yr. By definition an oracle should be ≥ Fixed-5yr.

Diagnosis: The Oracle implementation calls `optimal_T_star(ci, srv.gen_at_deploy, horizon)` every year, but this function assumes you start fresh from `gen_at_deploy` — it doesn't correctly account for the fleet's current accumulated state. The dynamically-recomputed T* gets confused as gen_at_deploy and remaining horizon change, leading to slightly suboptimal replacement timing.

### Bug 3: CI-Aware's claimed 72–79% savings at high-CI grids require scrutiny

At coal/UK grids, CI-Aware makes fewer total replacements (62–66) than Fixed-5yr (~90), yet saves 72–79%. This happens because CI-Aware correctly performs an initial burst of replacements to reach a highly-efficient generation, then stops replacing (embodied payback period becomes too long as efficiency approaches a floor). Fixed-5yr keeps blindly replacing every 5 years, paying embodied carbon for diminishing returns. This behavior is plausibly correct, but it operates differently from what the LOGBOX implies.

---

## 🔴 Implication for the Paper

If submitted as-is, any reviewer from the EU or Google/Microsoft (US-avg grids at CI≈300–400) would immediately run the simulation and find that your "CI-Aware" policy is catastrophically wrong for their deployment context. The paper would be rejected.

The claim "CI-Aware policy achieves the best lifecycle carbon outcome" is **only true for extreme-CI grids** (CI < 150 or CI > 450). For the global average (CI ≈ 300–400), CI-Aware either fails or is marginally correct.

---

## 🟡 What IS correct and publishable in this direction

1. **The T* analytical result is valid and striking**: T* ranges from ~4yr (coal) to ~15yr (nuclear), a 3–4× span. This is a genuine contribution independent of the policy comparison.

2. **The nuclear/hydro case is clean**: CI-Aware correctly makes zero replacements, avoiding 90.7 × 1000 kgCO₂ = 90,700 kg of embodied carbon, saving 50% vs. industry norm.

3. **The embodied carbon payback framework** (F9 inversion: "new hardware is NOT always better") is genuinely novel vs. prior CloudSim work.

4. **The crossover CI concept** (below ~280 g/kWh, never refresh; above ~450 g/kWh, refresh aggressively) is a clean, policy-relevant finding.

---

## Required Fix Before Any Paper Writing

### Option A (Minimal fix — recommended):
Replace the CI-Aware greedy policy with a **multi-period dynamic programming policy**:
- At each decision point, compute the DP-optimal remaining schedule given current gen, CI, and remaining horizon
- This is O(H²) per server per year — trivially fast for a Python simulation
- This will correctly identify T*=5yr at CI=300 and outperform Fixed-5yr at all CI values

### Option B (Research reframing):
Reframe the contribution as **"Analytical T* Derivation + Simulated Policy Comparison"**:
- Primary contribution: closed-form T*(CI, eff_gain, emb_C) formula
- Policy comparison: show FIXED-T* policy (using the formula) vs. industry norm
- Don't claim CI-Aware is optimal; instead claim that knowing the correct T* matters

Option B is actually STRONGER for publication because:
1. It has a closed-form analytical result (Theorem-level contribution)
2. It doesn't depend on simulation quality for the main finding
3. The simulation validates the theory

---

## Specific Questions for the Researcher

1. **Do you accept the validity problem** as described? Run the simulation yourself and check the eu_avg row.

2. **Which fix do you prefer?** DP policy vs. analytical T* reframing?

3. **Untested assumption**: The model uses constant CI. Real grids have decarbonizing CI trends (EU CI drops 3-5%/yr). Does T* change significantly if you model CI as declining over the horizon?

4. **IMPACT CHECK**: Who changes their behavior if this paper is published?
   - EU cloud operators: Currently at CI≈300; result says "Fixed-5yr is already near-optimal." Mildly interesting but doesn't change anything.
   - US cloud operators: at CI≈400, same story. Not compelling.
   - French nuclear datacenter operators: "Never replace hardware" — genuinely counterintuitive, potentially actionable.
   - AI companies with 2-year GPU cycles: "You're accruing massive embodied carbon debt on nuclear/hydro grids." VERY compelling.
   
   → **AI GPU refresh cycle is the compelling angle.** The current simulation uses CPU servers with 15%/yr efficiency gain. GPU efficiency gain is 2–3× per generation (Moore's Law on steroids). This changes T* dramatically. Consider pivoting to GPU/accelerator lifecycle as the primary scenario.

---

## Recommended Next Step (Supervisor Directive)

**Before proceeding to lit review or paper writing:**

1. Implement DP-Optimal policy replacing the CI-Aware greedy policy
2. Re-run simulate-lifecycle.py and verify Oracle ≥ Fixed-5yr at ALL CI values (Oracle should always be optimal)
3. Add GPU scenario: eff_gain=40%/yr (H100→H200→B200 cycle), emb=3000 kgCO₂ (GPU server), refresh_norm=2yr
4. Produce clean results table with NO cherry-picking

Only after clean results should lit review and paper writing proceed.

---
*Supervisor: auto-generated advisory cycle | 2026-02-28 00:05 UTC*
