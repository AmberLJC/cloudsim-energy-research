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

---

## CYCLE 11 CRITIQUE | 2026-02-28 09:49 UTC

### Status entering cycle 11
Paper at v0.7. Cycles 8–10 have all been incremental polish (citations, abstract conditionality, novelty scope, venue check). The cycle 10 uncomfortable question — "Is the researcher using completeness as a reason not to submit?" — was not resolved; we enter cycle 11 in the same state.

---

### LENS 1 — IMPACT CHECK (Blocking): No theory of who acts on the recommendations

Section 7.1 (Deployment Decision Matrix) tells practitioners *what* to do but is silent on *who* controls hardware refresh decisions at hyperscalers (CapEx/procurement, NOT sustainability teams) and what the primary institutional barrier is (depreciation schedules, vendor incentive programs). A HotCarbon reviewer will probe this immediately. "Deployable" is in the abstract but the paper doesn't explain the deployment path.

**Fix dispatched to worker:** Add 3–5 sentence paragraph naming decision-making actors, the institutional barrier, and why the threshold heuristic is implementable (asset registry + public grid CI data).

---

### LENS 2 — VALIDITY CHECK (Moderate): Fixed-3yr baseline missing

The paper's headline GPU savings (44–92%) compare DP-Optimal against Fixed-2yr. But the paper's own introduction acknowledges "actual hyperscaler fleet turnover may range 2–4 years in practice." If real practitioners already use 3–4 year cycles, the savings collapse. A reviewer can ask "What are savings vs Fixed-3yr?" and the paper has no answer.

**Fix dispatched to worker:** Run Fixed-3yr as additional baseline. Report savings of DP-Optimal vs Fixed-3yr. Decide whether to strengthen or caveat based on result.

---

### STRATEGIC DIRECTIVE (Most Urgent): Stop polishing, start publishing

The paper has been submission-ready since ~v0.2 (cycle 7). Three more cycles of polish have not produced a submission. HotCarbon 2026 CFP is expected ~March–April 2026. The embodied carbon space is moving fast (SCARIF 2024, Bashir 2024, CarbonFlex 2025 are all cited as very recent).

**Actions dispatched to worker:**
1. Produce condensed HotCarbon version (6 pages / ~3,000 words) — ready when CFP drops, same-day submission
2. Paper v0.8 commit

**Recommendation NOT yet dispatched but critical:** arXiv preprint should be posted NOW to establish priority. This requires author decision (cannot be automated). Amber/researcher should be made aware.

---

### THE UNCOMFORTABLE QUESTION (cycle 11)

> The Fixed-3yr baseline question is not a hairsplitting concern — it is the difference between "the industry is wasting 44–92% carbon" and "the industry is wasting 15–30% carbon." These are very different headlines. If the actual hyperscaler baseline is already 3 years (not 2), the paper's framing needs to change. Have we validated what the actual baseline is in practice, or are we assuming the worst case to maximize the headline savings?

*Supervisor: auto-generated advisory cycle 11 | 2026-02-28 09:49 UTC*

---

## CYCLE 12 CRITIQUE | 2026-02-28 10:09 UTC

### Status entering cycle 12
Paper at v0.8. Condensed HotCarbon version exists (~3,200 words). Four consecutive supervisor cycles (8-11) have produced polish but no submission. arXiv preprint has not been posted.

---

### LENS 1 — FALSIFICATION (Blocking): The 20-52% headline is now internally incoherent

Section 6.3 added Fixed-3yr data showing DP-Optimal saves only 7–23% vs a 3-year baseline. The paper's own introduction acknowledges "actual hyperscaler turnover may range 2–4 years." These two facts, taken together, mean the headline finding is contingent on an assumed worst-case baseline that the paper itself casts doubt on.

**The defensible reframe:** The paper's most robust, least assumption-dependent finding is NOT "DP-Optimal saves 20-52%." It is: **"Moving GPU inference refresh from 2 to 4 years saves 20-52% lifecycle carbon, regardless of whether DP-Optimal or a simple Fixed-4yr rule is used, across all CI scenarios."** That is a clean, falsification-resistant, policy-actionable finding. DP-Optimal is a validation tool, not the primary contribution.

**Required action:** Reframe the abstract narrative to lead with Fixed-2yr→Fixed-4yr as the core finding, relegate DP-Optimal to "we verify this is near-optimal." The paper already has this data; it just doesn't lead with it.

---

### LENS 2 — IMPACT (Urgent, Not Blocking): arXiv preprint is the highest-leverage action

The embodied carbon + GPU refresh space is active. SCARIF 2024, Acun 2023, Bashir 2024 are all cited as very recent. Every week without an arXiv timestamp is a priority risk. Four supervisor cycles have flagged this. No action taken.

**This is an author decision, not a technical task.** The paper (v0.8 full version) is ready for deposit. The arXiv deposit workflow:
1. Create account at arxiv.org (cs.DC category: Distributed, Parallel, and Cluster Computing; or cs.LG cross-list)
2. Upload paper.md converted to PDF (LaTeX or Word, with figures embedded)
3. Submit — preprint public within 24h

The supervisor cannot do this. **Amber must decide: post arXiv preprint this week or accept priority risk.** This is the most important open item in the project.

---

### LENS 3 — SCOPE: HotCarbon condensed version needs position-paper reframing

HotCarbon is a position/vision paper venue. The current paper-hotcarbon.md reads as a condensed empirical paper. HotCarbon reviewers want: provocative claim → why the current practice is wrong → minimal evidence → forward-looking call to action.

The T* invalidity finding is the most HotCarbon-appropriate contribution. It should be the lede: "The formula data center sustainability teams use to optimize server refresh cycles is mathematically invalid for real fleets, and the AI industry's 2-year GPU refresh cycle is the most expensive consequence." Lead with the claim, then show the math, then show the simulation confirms it.

**Recommended action (worker task):** Rewrite the HotCarbon intro paragraph and abstract to lead with T* invalidity as the provocation, with Fixed-4yr finding as the operational punchline. Bump paper to v0.9.

---

### STRATEGIC DIRECTIVE FOR CYCLE 12

**STOP ADDING FEATURES. SUBMIT.**

The paper's core contribution (Fixed-4yr inference is carbon-optimal; T* is invalid for staggered fleets) was established in v0.2. Cycles 3-12 have been hardening. The value of marginal polish is now near zero; the cost of not posting an arXiv preprint is growing daily.

**Action dispatched (worker):** Reframe HotCarbon abstract + intro to lead with T* invalidity. Fix the internal inconsistency between 20-52% headline and 7-23% Fixed-3yr caveat. Bump to v0.9.

**Action NOT dispatched (requires Amber):** arXiv deposit. This is the #1 open item.

---

### THE UNCOMFORTABLE QUESTION (cycle 12)

> Five cycles ago, the cycle 7 supervisor note said "paper is submission-ready." Four polish cycles later, nothing has been submitted and no preprint has been posted. What is the actual barrier? Is it that the paper isn't ready, or that submission requires converting to LaTeX/PDF and neither the researcher nor the automation has done that conversion? If the barrier is formatting — say so explicitly and unblock it. If the barrier is perfectionism — stop. If the barrier is waiting for HotCarbon CFP — post on arXiv now so priority is established.

*Supervisor: auto-generated advisory cycle 12 | 2026-02-28 10:09 UTC*

---

## CYCLE 13 CRITIQUE | 2026-02-28 10:29 UTC

### Status entering cycle 13
Paper at v0.9 (full + HotCarbon condensed). Commit `dc4f1bc`. HotCarbon condensed version is ~3,200 words. T* reframe completed in cycle 12. Fixed-3yr dual baseline incorporated. HotCarbon CFP not yet open (expected ~March–April 2026). arXiv preprint not posted.

---

### LENS 1 — IMPACT CHECK (Blocking for Workshop Format)

The HotCarbon condensed paper ends with a declarative conclusion: *"Disaggregating training and inference hardware refresh cycles is the primary deployable lever for reducing embodied carbon in AI data centers."* This tells reviewers what was found but **asks nothing of the community**. HotCarbon explicitly wants papers that "open a line of inquiry" — the conclusion must provoke action, not summarize findings.

Three community-actionable open problems are missing:

1. **GPU EPD gap:** NVIDIA and AMD have published no verified EPD for H100/H200/B200/Rubin. This is the single most critical data gap for the entire embodied carbon research area. Calling this out explicitly, by name, in a HotCarbon paper will make this paper a mandatory citation for every future GPU lifecycle carbon study.

2. **Fleet age data gap:** No cloud provider publishes hardware fleet age distribution data. DP-vs-T* invalidity validation requires real fleet data. A call for an open fleet age dataset (analogous to the Google/Azure/Alibaba trace releases) would directly enable the follow-on empirical work.

3. **Regulatory contradiction:** CSRD (EU) Scope 3 reporting requirements — now mandatory for large EU-market companies — create incentives to procure the *latest, most efficient* hardware to reduce Scope 3 emissions per unit of compute. On clean-grid deployments, this incentive is directionally **backwards** — replacing functional hardware earlier emits more total lifecycle carbon. This regulatory mismatch is a genuine policy concern, not just a research footnote.

**Fix dispatched to worker:** Add Section 10 "Open Problems" to paper-hotcarbon.md.

---

### LENS 2 — NOVELTY CHECK (Moderate Risk)

The literature review was completed February 27, 2026. The embodied carbon + AI hardware space is active: SCARIF (Jan 2024), Bashir (Oct 2024), Acun (ASPLOS 2023) all appeared recently. The paper claims "first simulation-based quantification of lifecycle carbon under DP-optimal refresh policies" — this should be verified against January–February 2026 arXiv preprints before the HotCarbon submission. If anything has been posted in the last 8 weeks covering DP-based server hardware lifecycle carbon optimization, the novelty claim needs adjustment.

**Fix dispatched to worker:** Quick targeted arXiv search for Jan–Feb 2026 papers. Update related work section if needed.

---

### CYCLE 13 DIRECTIVE — Worker Spawned

**Task:** (1) arXiv novelty check Jan–Feb 2026 on "server lifecycle carbon optimization," "GPU embodied carbon refresh cycle," "hardware replacement policy carbon"; (2) Add Section 10 "Open Problems and Community Call to Action" to paper-hotcarbon.md with the 3 items above; (3) Bump condensed paper version header to v1.0-final; (4) Commit.

---

### STRATEGIC FLAG — CYCLE 13 IS THE FINAL TECHNICAL CYCLE

The research has been ready for submission for 7 cycles. Additional technical cycles on this paper have hit severe diminishing returns. The remaining blockers are:

| Blocker | Status | Owner |
|---------|--------|-------|
| HotCarbon CFP publication | Not yet open (~4–6 weeks) | External |
| arXiv preprint deposit | **UNBLOCKED — highest leverage action** | **Amber** |
| LaTeX/PDF conversion | Unblocked but tedious | Can be worker task when needed |
| HotCarbon submission | Blocked on CFP | External |

**After this cycle, the supervisor should not re-engage on this paper until (a) HotCarbon CFP is published, or (b) Amber posts the arXiv preprint and wants a submission readiness check.** The paper's technical content is as good as it needs to be.

---

### THE UNCOMFORTABLE QUESTION (cycle 13)

> The pattern has been: supervisor identifies a gap, worker fixes it, paper version increments, next cycle finds another gap. But the paper's actual scientific contribution has not changed since v0.2. The value of the last 8 cycles of polish has been marginal. Has this project taught us anything about research process? Yes: autonomous research loops without an external forcing function (a real deadline, a real submission) will cycle indefinitely on polish. The HotCarbon CFP opening is the external forcing function. When it opens, submit immediately — do not spend another 12 cycles re-reviewing the paper.

*Supervisor: auto-generated advisory cycle 13 | 2026-02-28 10:29 UTC*
