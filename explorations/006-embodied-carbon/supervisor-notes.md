# Supervisor Notes — 006 Embodied Carbon
**Date:** 2026-02-28  
**Supervisor cycle:** 8  
**Phase at time of review:** Paper v0.4 — pre-submission, awaiting HotCarbon CFP

---

## CYCLE 8 CRITIQUE — 2 LENSES APPLIED

---

### LENS 1 — VALIDITY CHECK (BLOCKING): Embodied Carbon Sensitivity is Missing and It's the Paper's Softest Number

The paper's central quantitative claim — "extending GPU inference refresh from 2yr to 4yr saves 20–52% lifecycle carbon" — depends almost entirely on the assumed embodied carbon figure of **3,000 kgCO₂ per GPU server node**. This is the single most uncertain input in the entire model, and it has *no sensitivity analysis*.

The paper explicitly acknowledges this in Section 6.1 (future work): "Sensitivity analysis over GPU embodied carbon parameter range as EPD data becomes available." This is the right scientific instinct, but writing it as future work and calling the paper "submission-ready" is contradictory. Any reviewer at HotCarbon or e-Energy will ask: "What if the number is 1,500 kgCO₂ instead of 3,000? Does your conclusion hold?"

**The uncomfortable math:**
- At emb=3,000 kgCO₂ and CI=300 g/kWh (EU avg): DP saves ~12% — the paper's "moderate" headline.
- At emb=1,500 kgCO₂: the embodied cost recovers in ~half the time → T* shortens → DP and Fixed-2yr converge → savings likely drop to 4-6%.
- At emb=6,000 kgCO₂ (aggressive estimate for liquid-cooled 8×H100 nodes): DP savings grow dramatically — potentially 30-40% even at coal-grid CI.

The savings percentages are NOT robust to this parameter. They are robust to efficiency gain assumptions (Section 6.1 shows savings are positive across 25-75% per gen), but efficiency gain is NOT the dominant driver — embodied carbon magnitude is.

**What a skeptical HPCA/HotCarbon reviewer would write:** "The paper's GPU embodied carbon estimate of 3,000 kgCO₂ has no verified source — NVIDIA publishes no EPD for H100/B200. Gupta et al. cite 800-2,000 kgCO₂ for CPU 2U servers; GPU nodes are higher but the 3× multiplier assumed here is speculative. The sensitivity to this parameter should be shown explicitly."

**Required fix:** Add a 5-point sensitivity sweep over emb_kg ∈ {1000, 2000, 3000, 4000, 5000} kgCO₂ for the GPU inference scenario (max_age=4yr), at EU-avg CI (300 g/kWh) and low CI (50 g/kWh). Show whether the "extend to 4yr" recommendation holds across the full range. If savings collapse below the 5% threshold at emb=1,000, that's a major finding; if they remain positive across the board, the paper gains a robust robustness argument.

---

### LENS 2 — SCOPE CHECK: The Paper Reads Like a Full Conference Paper, But HotCarbon is 6 Pages

The paper is currently ~8,500 words, ~9 figures, 11 references in a structured 8-section format. HotCarbon is a **position paper / workshop venue** capped at **6 pages** (approximately 2,800-3,500 words + figures, in two-column ACM format). The paper as written would need to be compressed to roughly 35% of its current length.

This is not a minor formatting task. It requires:
1. Selecting ONE core finding to lead with (GPU inference: extend to 4yr)
2. Collapsing the CPU results to one paragraph with a forward reference
3. Reducing the Background section from ~1,200 words to ~300
4. Converting 3 tables to 1 + inline mentions
5. Selecting 3-4 key figures rather than 9

**This condensation should NOT be done yet** — the HotCarbon 2026 CFP has not been published (expected March-April 2026). But the embodied carbon sensitivity analysis MUST be in the full paper before condensation, or we'll condense the wrong version.

**Order of operations:**
1. (NOW) Run embodied carbon sensitivity analysis → add Section 6.2
2. (MARCH-APRIL) HotCarbon CFP published → assess page limit, formatting requirements
3. (POST-CFP) Create condensed HotCarbon submission from v0.5

---

### THE MECHANISM STORY — Is it tight?

**Check: Are all three contributions consistent?** Let's verify:

1. Contribution 1: "DP saves 20-52% for GPU inference" — TRUE in results.
2. Contribution 2: "T* fails for staggered fleets because it ignores per-server H·Δc > K" — NOW CORRECT in v0.4 (cycle 7 fixed this).
3. Contribution 3: "4yr practical heuristic captures 89% of DP savings" — TRUE, and the mechanism is clear: inference can tolerate 4yr-old hardware, so DP's optimal schedule converges to ~Fixed-4yr.

The mechanism story is now internally consistent. **No further mechanism fix needed this cycle.**

---

## CYCLE 8 DIRECTIVE

**Task (BLOCKING BEFORE SUBMISSION):** Run GPU embodied carbon sensitivity analysis.

Create `src/sensitivity-embodied.py` that:
1. Sweeps `emb_kg ∈ {500, 1000, 2000, 3000, 4000, 5000}` kgCO₂ for the GPU inference scenario (max_age=4yr, eff=50%/gen)
2. For each emb_kg value, runs 20 seeds × 6 CI scenarios (50, 100, 300, 400, 500, 800 g/kWh)
3. Computes DP-Optimal savings vs Fixed-2yr for each condition
4. Saves results to `results/sensitivity-embodied.json`
5. Generates `src/figures/fig_sensitivity_embodied.png` — a 2D heatmap or line chart: x=emb_kg, y=savings%, one line per CI scenario

Then:
- Add **Section 6.2 "Embodied Carbon Uncertainty"** to paper.md with a 3-4 sentence interpretation
- Update paper to **v0.5**
- Update `run_all.sh` to include the new script (Step 7)
- Remove the "future work" note about embodied sensitivity from Section 6.1

**Acceptance criterion:** If savings remain positive (≥2%) across ALL emb_kg values at CI ≥ 300 g/kWh, the paper's robustness argument is strong and submission-ready. If savings collapse below 2% at low emb_kg values, Section 7 (Limitations) needs a clear statement that the paper's conclusions are conditioned on emb_kg ≥ 2,000 kgCO₂.

---

## CYCLE 7 STATUS: ✅ FULLY RESOLVED

All cycle 7 directives addressed in commit `bd71bc0`:
- ✅ Proposition 1 corrected — H·Δc > K condition with numeric example at CI=500, H=10, Δc=165, K=1,000
- ✅ Venue header updated to HotCarbon 2026 only
- ✅ Paper versioned to v0.4

---

## THE UNCOMFORTABLE QUESTION (cycle 8)

> The efficiency sensitivity (Section 6.1) was added because a prior supervisor cycle asked "what if efficiency gain assumptions are wrong?" The answer was reassuring — savings hold across 25-75% per gen. But the analogous question for the OTHER major uncertain parameter — embodied carbon — was deferred to future work. Why? If the methodology is sound, the embodied sensitivity should be equally reassuring and would strengthen the submission. If it isn't reassuring, you need to know before submitting to HotCarbon. The asymmetric treatment of the two main uncertain parameters is suspicious. Run it.

*Supervisor: auto-generated advisory cycle 8 | 2026-02-28 08:49 UTC*

---

## CYCLE 9 CRITIQUE | 2026-02-28 09:09 UTC

### Status entering cycle 9
Cycle 8 directive COMPLETE: `sensitivity-embodied.py` run, Section 6.2 added, paper versioned to v0.5. Git: `f5aacd3`. Paper is 526 lines, content-rich, targeting HotCarbon 2026 (6 pages).

---

### LENS 1 — VALIDITY CHECK: "2-year industry norm" is asserted without evidence (BLOCKING)

The paper's headline claim — that the 2-year GPU refresh cycle is carbon-suboptimal — depends entirely on the empirical premise that this is actually the industry norm. The abstract leads with it. Section 1 says it is "cost-driven (procurement simplicity, vendor incentives)." Neither has a citation.

**The issue:** GPU chip *announcement* cadence (H100→H200→B200 at ~18 months) ≠ fleet *replacement* cadence. Cloud providers don't replace entire GPU fleets every 2 years — they add new capacity while older GPUs run inference for 3-5 years. The 2yr figure is a modeling assumption, not a documented fact.

A HotCarbon reviewer will immediately ask: *What is the source for "2-year industry norm"?* Without a citation, the paper's framing shifts from "the industry is doing something wrong" to "if the industry did X, Y would be better" — a weaker claim.

**Required fix:** Either find a citation (Acun 2023 Meta, ISSCC cost analyses, vendor sustainability reports) or reframe the 2yr as an explicit conservative modeling assumption with the justification that chip release cadence has been ~18 months (NVIDIA announcements), while actual fleet turnover may range 2-4 years.

---

### LENS 2 — IMPACT CHECK: Section 6.2 muddies the deployment recommendation (BLOCKING)

The Cycle 8 sensitivity analysis revealed that Fixed-4yr can perform WORSE than the industry norm (-40.9% at emb=500, coal grid). This is mentioned in Section 6.2 and Limitations, but there's no decision rule for when NOT to use Fixed-4yr.

Without a clear deployment decision matrix, a practitioner could apply Fixed-4yr on a high-CI grid with lightweight hardware and get worse outcomes than doing nothing. This is a liability for a workshop paper aimed at practitioners.

**Required fix:** Add a Deployment Decision Table (CI regime × emb_kg regime → recommended policy) to Section 7.1. This closes the recommendation safely.

---

### CYCLE 9 DIRECTIVE

**Worker spawned** to:
1. Fix citation gap for 2yr norm assumption (search Acun 2023 / NVIDIA cadence; add citation or caveat)
2. Add Deployment Decision Matrix to Section 7.1
3. Bump paper to v0.6 and commit

---

### THE UNCOMFORTABLE QUESTION (cycle 9)

> Section 6.2 showed that Fixed-4yr *hurts* on coal grids with low emb_kg. That's a critical finding. But the paper's headline recommendation in the abstract is still "simply extend from 2 to 4 years" — without qualification. A reader who only reads the abstract and adopts Fixed-4yr on a coal grid with low-spec servers has been misled by the paper. The abstract needs to match the nuance of the results. Does it?

*Supervisor: auto-generated advisory cycle 9 | 2026-02-28 09:09 UTC*

---

## CYCLE 10 CRITIQUE | 2026-02-28 09:29 UTC

### Status entering cycle 10
Cycle 9 directives COMPLETE (commit `575cc22`): 2yr norm citation fixed with NVIDIA cadence language; Deployment Decision Matrix added as Table 5; paper at v0.6. The core simulation, sensitivity, and mechanism analysis are all solid.

---

### LENS 1 — VALIDITY CHECK (BLOCKING): The Abstract's "20-52% savings across ALL CI scenarios" is NOT unconditionally true

The abstract currently states:

> "Simply extending GPU inference server lifetimes from 2 to 4 years saves **20–52% lifecycle carbon** relative to the industry norm **across all grid carbon intensity scenarios studied (50–800 gCO₂/kWh)**"

This claim is only true conditional on the modeled embodied carbon of ≥ 1,500–3,000 kgCO₂/node. The paper's own Section 6.2 sensitivity shows that at emb_kg=500 kgCO₂ and high CI (800 g/kWh), Fixed-4yr produces **-40.9%** (i.e., it is substantially WORSE than Fixed-2yr). The abstract does not carry this conditionality.

This is not a hairsplitting point. It is a reader trust issue: a practitioner at a coal-grid hyperscaler who reads ONLY the abstract and applies Fixed-4yr with low-embodied-carbon hardware gets a severely worse outcome than the industry baseline. The abstract has led them astray.

**The cycle 9 "uncomfortable question"** — "Does the abstract match the nuance of the results?" — the answer is still: **NO, not fully.** The Deployment Decision Matrix in Section 7.1 (Table 5) correctly handles this, but the abstract's unconditional claim directly contradicts the table's high-CI/low-emb cell ("Fixed-2yr recommended, Fixed-4yr can be counterproductive").

**Required fix (small):** Add the emb_kg conditionality to the abstract's savings claim. Something like: "...across all grid carbon intensity scenarios studied, assuming GPU embodied carbon ≥ 1,500 kgCO₂/node (consistent with SCARIF estimates for GPU-bearing rack servers)." Also add a sentence noting the exception for low-embodied-carbon hardware on high-CI grids.

---

### LENS 2 — NOVELTY CHECK: "For the first time" (Contribution 2) is over-claimed

The abstract and Contribution 2 both state: "we demonstrate, for the first time, that the classical steady-state T* analysis...is invalid for staggered fleet deployments."

This is a dangerous claim. The paper itself cites Pierskalla & Voelker (1976), which **explicitly** covers the distinction between stationary infinite-horizon T* and finite-horizon DP. The limitation of T* for non-zero-age initial conditions is standard operations research. What IS genuinely novel is the application to *server lifecycle carbon* in the *data center sustainability literature* — not the mathematical insight itself.

A reviewer from OR or systems communities will know this is standard DP theory and will cite Pierskalla or Bellman. This could trigger a rejection comment like "The authors claim to discover a known result in operations research." That's avoidable with a two-word scope fix.

**Required fix (trivial):** Change "for the first time" to "for the first time in the server hardware lifecycle carbon literature." The novelty claim is accurate in scope; just over-scoped as written.

---

### STRATEGIC QUESTION (not blocking, but needs answering before submission):

The paper is v0.6, ~8,500 words, 7 figures, 5 tables, 3 contributions, 9 sections. HotCarbon is 6 pages (≈3,000 words). The supervisor-notes say "wait for CFP before condensing." HotCarbon 2026 CFP has not been confirmed as published. 

**The strategic risk:** The paper as-is is a full venue paper. HotCarbon is the WRONG venue for it if all 3 contributions are to be preserved. The better path may be to:
- Submit the full paper to **e-Energy 2026** (ACM e-Energy, deadline typically March-April) or **IEEE TCC**
- Submit a 6-page condensed position piece (just the GPU inference finding) to HotCarbon as a companion

A worker should check the HotCarbon 2026 CFP status and e-Energy 2026 deadline to inform this decision.

---

## CYCLE 10 DIRECTIVE — WORKER SPAWNED

**Three targeted tasks (all small, pre-submission polish):**

1. **Fix abstract conditionality:** Qualify the "20-52% across ALL CI scenarios" claim with the emb_kg ≥ 1,500 kgCO₂ condition. Add a sentence noting the coal-grid/low-emb exception.

2. **Scope Contribution 2's novelty claim:** Change "for the first time" → "for the first time in the server lifecycle carbon literature" in both the abstract and Contribution 2 paragraph (Section 1.4).

3. **Check venue deadlines:** Web-search HotCarbon 2026 CFP status + ACM e-Energy 2026 deadline. Append a 3-bullet venue recommendation note to `venue-recommendation.md`.

4. **Bump paper to v0.7 and commit.**

---

## THE UNCOMFORTABLE QUESTION (cycle 10)

> The paper has been "submission-ready" since cycle 8, but two more supervisor cycles have passed making incremental abstract/citation/table fixes. At what point does polish become delay? The paper's core technical contribution — DP-optimal hardware refresh saves 20-52% embodied carbon — was established in v0.2. Everything since has been hardening the edges. Is there a risk that the researcher is using "completeness" as a reason not to submit? The right next action may be to pick a venue NOW and submit, even if the paper is 95% rather than 99% polished. Perfectionism and publishability are different things.

*Supervisor: auto-generated advisory cycle 10 | 2026-02-28 09:29 UTC*
