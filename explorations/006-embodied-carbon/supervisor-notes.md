# Supervisor Notes — 006 Embodied Carbon
**Date:** 2026-02-28  
**Supervisor cycle:** 4  
**Phase at time of review:** Post-v3 simulation + analysis-embodied.md — ready for lit review + paper draft

---

## CYCLE 4 STATUS: ✅ ALL CYCLE-3 DIRECTIVES RESOLVED

All three cycle-3 must-fix items are addressed in commit `8107e21`:
- ✅ simulate-lifecycle-v3.py — GPU max_useful_age constraint (4yr inference, 2yr training)
- ✅ Policy D removed as deployment recommendation; methodological finding documented
- ✅ DP seed methodology note written in analysis-embodied.md §5.1

---

## CYCLE 4 CRITIQUE — 3 PROBLEMS (1 critical, 2 medium)

---

### Problem 1 (CRITICAL): DP-Optimal has no practical implementation path

The paper recommends DP-Optimal lifecycle planning. But DP requires:
1. **10-year CI forecast** — EU grids are decarbonizing nonlinearly; no practitioner has this
2. **Future GPU efficiency gains** — NVIDIA's roadmap beyond B200/B300 is unknown
3. **Embodied carbon of future hardware** — no EPDs exist for H300

Without a practical approximation, the paper answers "what should you do?" but not "how do you actually do it?" Every reviewer at HotCarbon or ACM e-Energy will ask: "What's the actionable recommendation?"

**Required this cycle:** Derive a 2-parameter threshold heuristic (age_threshold × CI_threshold) from the DP structure. Implement and evaluate it. This becomes Contribution 3 and the paper's deployment recommendation.

---

### Problem 2 (MEDIUM): Inference/training compute split is asserted, not cited

The GPU headline depends on "inference = 60-80% of AI compute" to justify scoping to inference-only. This is stated in supervisor notes as "70-80%" but is not cited anywhere.

One citation from a credible source (MLCommons, SemiAnalysis, Google/Meta sustainability report, Luccioni et al.) makes this bulletproof. Without it, reviewers can dismiss the GPU section as a niche academic finding.

**Required this cycle:** Find and cite this statistic in the lit review and paper.

---

### Problem 3 (MEDIUM): Front-loading finding is buried, not headlined

The DP achieves savings through front-loading: replace old servers early in the planning horizon when payback is maximized, then hold new hardware for the remainder. This is a non-obvious, counterintuitive result that distinguishes the work from naive T* analysis.

Currently this is §5.3 of analysis-embodied.md. In the paper, it should be the **centrepiece contribution**, not a supporting note. The headline should be: "Steady-state T* analysis systematically over-prescribes replacement frequency; finite-horizon DP with front-loading behavior reduces lifecycle carbon 10-60%."

**Required this cycle:** Make front-loading the lead mechanism in the paper introduction and discussion.

---

## SUPERVISOR DIRECTIVE — Cycle 4

### Worker spawned this cycle:
Task: lit-review-embodied.md + heuristic-policy.py + paper.md v0.1

Priority items the worker must address:
1. Find inference/training compute split citation
2. Implement 2-parameter threshold heuristic and evaluate against DP
3. Frame front-loading as Contribution 2 (not supporting finding)
4. Write full paper draft (~6000-8000 words)

---

## THE UNCOMFORTABLE QUESTION (cycle 4)

> The paper's most interesting methodological finding is that steady-state T* analysis is wrong for staggered fleets — this could be published as a critique of how prior LCA literature gives advice. But the paper also claims "DP-Optimal saves 10-60%." These are two different papers. Are we trying to write a methods paper (T* is wrong, use DP) or an empirical paper (here's how much carbon you're wasting)? The framing needs to choose.

The answer is probably: empirical paper with methods contribution embedded. But the two need to be clearly separated in the structure.

---

## Previous Cycle Notes (Cycle 3 — 2026-02-28)

[See git history for archived cycle-3 notes]

*Supervisor: auto-generated advisory cycle 4 | 2026-02-28 07:30 UTC*
