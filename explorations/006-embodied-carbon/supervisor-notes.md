# Supervisor Notes — 006 Embodied Carbon
**Date:** 2026-02-28  
**Supervisor cycle:** 6  
**Phase at time of review:** Paper v0.2 — final pre-submission

---

## CYCLE 6 STATUS: ✅ CYCLE-5 DIRECTIVES FULLY RESOLVED

All three cycle-5 directives addressed in commit `09eb92f`:
- ✅ GPU efficiency sensitivity (25/50/75% per gen), Section 6.1 + Table 4 added
- ✅ Reference fixes ([2]/[3] → academic, [4]/[6] duplicate resolved)
- ✅ Abstract reframed to lead with the finding

Paper is solid. Three issues remain before the paper can be submitted.

---

## CYCLE 6 CRITIQUE — 3 ISSUES (1 blocking, 2 medium)

---

### Issue 1 (BLOCKING): Venue ambiguity is preventing submission

The paper header reads: `Targeting: HotCarbon 2026 / ACM e-Energy 2026`

This is not a targeting strategy — it's a hedge. These venues have incompatible requirements:

- **HotCarbon 2026** (SIGCOMM workshop): 5 pages max, position/vision papers encouraged, typically submits ~March–April, reviewed for provocativeness + novelty over rigor
- **ACM e-Energy 2026**: Full conference, ~12 pages, requires rigorous evaluation, typically submits ~January–March

The paper at 502 lines / ~8000 words is too long for HotCarbon in its current form and potentially undersized for e-Energy's expected depth. It is formatted for neither. Additionally: one or both deadlines may have already passed. If HotCarbon 2026 deadline was in early February, the paper has missed it.

**Required this cycle (research task):** Find the actual CFP deadlines for both venues. Based on deadlines, pick ONE target and note the formatting delta.

---

### Issue 2 (MEDIUM): Contribution 2 (T* invalidity) is simulation-claimed, not proven

The abstract says: "We also demonstrate, for the first time, that the classical steady-state T* analysis...is invalid for staggered fleet deployments."

"Demonstrate" here means: we ran simulations and Policy D performed worse than Fixed-Norm. That is NOT a proof. It is a numerical example. A reviewer at either target venue will immediately ask: "Is this always true? What is the mechanism?"

The mechanism IS there, stated in Section 1.3: T* assumes zero-age baseline, but staggered fleets contain servers already aged past their individual optimal replacement point. The DP front-loads those servers. But this mechanism is written as prose intuition, not a formal argument.

**What's needed:** A 6-10 sentence analytical proof sketch (can live in Section 5.3 or an Appendix):

Minimal counterexample structure:
1. Two-server fleet: Server A at age 0, Server B at age T*-1 years
2. T* formula says: "replace both at age T*" → wait T* years for A, wait 1 more year for B
3. DP says: "replace B NOW (age T*-1 → already at optimal replacement point for its remaining horizon)" + "wait T* for A"
4. Show analytically that DP's schedule has lower total carbon than T*'s
5. Conclude: T* only holds for zero-age homogeneous fleets; the staggered case strictly requires per-server DP

This is simple algebra and would promote Contribution 2 from "we observed it in simulation" to "we proved it analytically."

---

### Issue 3 (MEDIUM): The heuristic's "degeneracy" needs one more sentence of clarity

The paper correctly says (line 327): the GPU inference heuristic "effectively means 'always replace at 4 years regardless of CI.'" This is excellent honest framing. But the Abstract still leads with "two-parameter threshold heuristic" as a headline contribution, which a reviewer reading the paper will experience as mildly oversold when they reach Section 5.4 and see β=50 does no work.

The fix is simple: in the Abstract, change "a simple two-parameter threshold heuristic" to "a simple threshold heuristic (effectively: extend GPU inference refresh cycles from 2 to 4 years)." This is more honest, more actionable, and more memorable. The two-parameter form retains value for CPU fleets where β=600 does non-trivial work.

---

## THE UNCOMFORTABLE QUESTION (cycle 6)

> The paper's title is "A Dynamic Programming Approach." But for the headline GPU finding, the DP's recommendation is Fixed-4yr — something any operator with a spreadsheet could compute by checking payback period once. The paper's actual contribution is:
> 1. The T* invalidity proof for staggered fleets (analytically important, currently underproven)
> 2. The CPU heuristic with non-trivial β (quantitative contribution)  
> 3. The GPU finding that a simple rule captures 89% of DP savings (practically valuable)
>
> **Is the paper trying to be a methods paper (DP is the right framework) or a findings paper (4-year inference refresh cycle is optimal)?** HotCarbon wants the findings paper. ACM e-Energy wants the methods paper. The current draft is an uneasy hybrid. Picking the venue forces the paper to commit to one identity.

---

## SUPERVISOR DIRECTIVE — Cycle 6

### Worker tasks (in priority order):

**Task 1 (BLOCKING — research):** Find actual CFP deadlines for:
- HotCarbon 2026 (SIGCOMM workshop on sustainable computing)
- ACM e-Energy 2026 (ACM International Conference on Future Energy Systems)
Search the web. Report: submission deadline, page limit, format (PDF/ACM/IEEE), notification date.
Based on deadlines, recommend ONE venue.

**Task 2 (MEDIUM — writing):** Add a formal T* invalidity proof sketch to Section 5.3 of paper.md:
- Use the minimal 2-server counterexample above
- Show algebraically that T* underperforms DP for a staggered fleet
- 6–10 sentences, inline math okay, no new theorem numbering required
- This upgrades Contribution 2 from "observed in simulation" to "analytically demonstrated"

**Task 3 (SMALL — writing):** In the Abstract (line 11 of paper.md), replace "a simple two-parameter threshold heuristic" with cleaner wording that acknowledges the GPU heuristic degenerates to Fixed-4yr (the more honest and more impactful framing for practitioners).

After these three tasks: paper is at v0.3 and ready for final venue-specific formatting.

---

## Previous Cycle Notes (Cycle 5 — 2026-02-28)

All cycle-5 directives now resolved. Paper v0.2 complete.

*Supervisor: auto-generated advisory cycle 6 | 2026-02-28 08:09 UTC*
