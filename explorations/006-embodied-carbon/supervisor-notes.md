# Supervisor Notes — 006 Embodied Carbon
**Date:** 2026-02-28  
**Supervisor cycle:** 7  
**Phase at time of review:** Paper v0.3 — pre-submission

---

## CYCLE 7 CRITIQUE — 2 ISSUES (1 blocking, 1 trivial)

---

### Issue 1 (BLOCKING): Proposition 1 proof sketch has the logic backwards

The proof sketch added in v0.3 claims T* "over-schedules replacements for recently-deployed servers (Server A, age 0)." This is **incorrect** and contradicts the prose that follows it.

**What the proof claims:** Server A (age=0), T*=10yr, 10-year horizon → T* "would trigger 2 replacements." This is simply wrong: T* says replace A at year 10 (once). DP would also replace at most once. They agree for a freshly-deployed server. A reviewer checking the arithmetic will reject the argument immediately.

**What actually causes Policy D to fail (from line 295 of paper.md):** "Servers entering at age=4 generate net +485 kg savings from an early replacement that T*=10yr never recommends." This is *under-scheduling of old servers*, the OPPOSITE of what the proof claims. The paper's own simulation narrative directly contradicts Proposition 1.

**The correct minimal counterexample** (replace the current sketch with this):

```
Server B: age=4 at simulation start, T*=10yr, H=10yr remaining, CI=500 g/kWh
K = 1,000 kgCO2 embodied; Δc = 165 kg/yr operational savings per generation

T* schedule for Server B: hold 6 more years → replace at age 10.
  Carbon cost: 6 years at old efficiency + K_embodied + 4 years at new efficiency
  = 0 + 1,000 + 4 × (−165) = 340 kg saved vs. holding forever (but DP comparison below)

DP schedule for Server B: replace NOW (age 4 → 0).
  Carbon cost: K_embodied + 10 years at new efficiency
  Net savings vs. T* schedule: 10 × 165 − 1,000 = 650 kg vs. (4 × 165 − 1,000) = −340 kg
  DP saves 650 kg; T* "saves" -340 kg (i.e., wastes carbon)
  DP beats T* by 650 − (−340) = 990 kg per server over the horizon.
```

Therefore: for a server at age T*−(H−T*) < age < T*, T* instructs waiting; DP instructs replacing immediately. The condition under which DP beats T* is simply: **H·Δc > K**, where H is remaining horizon. For H=10, Δc=165, K=1,000: 1,650 > 1,000 ✓. T* never checks this condition per-server; it blindly applies the steady-state cycle.

**The correct Proposition 1:** "For a server at age a > 0 with H years of remaining horizon, replacing immediately is optimal when H·Δc(CI) > K_embodied, regardless of T*. T* analysis assumes a=0 for all servers and therefore systematically misses early-replacement opportunities for servers with a > 0 in staggered fleets."

This single paragraph, with the arithmetic, is a complete analytical result. Replace the current Proposition 1 / proof sketch with this version.

---

### Issue 2 (TRIVIAL): Paper header still says dual venue

paper.md line 3: `**Targeting:** HotCarbon 2026 / ACM e-Energy 2026`

venue-recommendation.md says: **→ Submit to HotCarbon 2026.** 

Update the header to: `**Targeting:** HotCarbon 2026`

---

## SUPERVISOR DIRECTIVE — Cycle 7

**Task 1 (BLOCKING):** Replace Proposition 1 and its proof sketch in Section 5.3 with the correct counterexample described above. Use the algebraic argument: T* fails because it never checks H·Δc > K per-server; DP does. Include the numeric example with actual values from the simulation (H=10, Δc=165, K=1,000, CI=500). This upgrades Contribution 2 from "logically inconsistent observation" to "clean analytical result."

**Task 2 (TRIVIAL):** Update paper.md header targeting line from dual-venue to "HotCarbon 2026" only. Version bump to v0.4.

After these two tasks: paper is at v0.4 and analytically clean. The remaining pre-submission work is venue-specific condensing (6-page HotCarbon format), which should wait until the HotCarbon 2026 CFP is published (~March–April 2026).

---

## CYCLE 6 STATUS: ✅ FULLY RESOLVED

All three cycle-6 directives addressed in commit `abc9ddb`:
- ✅ Venue recommendation written (HotCarbon recommended)
- ✅ T* proof sketch added (BUT: has a logical error — see Cycle 7 Issue 1)
- ✅ Abstract heuristic language fixed

---

## THE UNCOMFORTABLE QUESTION (cycle 7)

> The paper now has v0.3 with a proof that contradicts itself: Proposition 1 claims T* over-schedules new servers, the simulation narrative says T* under-schedules old servers, and Section 1.3 correctly states T* "systematically overestimates the optimal cycle length." These three claims are not all compatible. The fix is simple arithmetic — but the fact that this passed three revision cycles without being caught suggests the proof was added to check a box rather than to actually close the argument. Before calling the paper submission-ready again, verify internally that the mechanism story is consistent end-to-end.

*Supervisor: auto-generated advisory cycle 7 | 2026-02-28 08:29 UTC*
