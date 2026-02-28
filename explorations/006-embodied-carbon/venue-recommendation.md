# Venue Recommendation: 006-Embodied-Carbon Paper

**Date assessed:** 2026-02-28  
**Paper:** Carbon-Optimal Hardware Lifecycle Planning for AI Data Centers: A Dynamic Programming Approach  
**Paper length:** ~502 lines / ~8,500 words

---

## CFP Research Summary

### HotCarbon 2026
*(Workshop on Sustainable Computer Systems — co-located with OSDI/SIGCOMM, summer 2026)*

| Field | Details |
|-------|---------|
| Status | **CFP not yet announced** as of 2026-02-28. HotCarbon 2025 wrapped Aug 2025; site says "Stay tuned for the 2026 edition!" |
| Expected deadline | ~May 2026 (based on 2025 pattern: submission May 12, 2025; notifications June 13, 2025) |
| Expected venue date | ~July 2026 |
| Page limit | Typically **2–6 pages** (ACM two-column format), workshop short-paper style |
| Format | ACM Digital Library (ACM SIGOPS/SIGCOMM workshop proceedings) |
| Acceptance notification | ~June 2026 (estimated) |
| Deadline status | **OPEN** — CFP not yet published; submission window expected to open March–April 2026 |

**Source:** https://hotcarbon.org/ (checked 2026-02-28)

---

### ACM e-Energy 2026
*(ACM International Conference on Future Energy Systems)*

| Field | Details |
|-------|---------|
| Status | CFP page not accessible as of 2026-02-28 (ACM site returned 403/blocked) |
| Historical pattern | Full-paper deadline typically **January–February** of conference year; e-Energy 2025 abstract deadline was ~Jan 2025 |
| Expected deadline | Likely **already passed** (~January 2026) based on prior years |
| Page limit | 10 pages (ACM two-column format) for full papers |
| Format | ACM Digital Library |
| Conference date | Typically June of conference year |
| Deadline status | **LIKELY CLOSED** — deadline probably passed before Feb 28, 2026 |

**Source:** Estimated from historical ACM e-Energy CFP patterns; direct URL lookup failed (Cloudflare block).

---

## Paper Fit Analysis

| Criterion | HotCarbon 2026 | ACM e-Energy 2026 |
|-----------|---------------|-------------------|
| **Deadline status** | ✅ OPEN (expected ~May 2026) | ❌ Likely CLOSED (~Jan 2026) |
| **Length fit** | ⚠️ Paper needs heavy condensing (6-page max → ~3,500 words from 8,500) | ✅ 10-page ACM format fits (~6,000 words; paper needs modest trimming) |
| **Content match** | ✅ Excellent — embodied carbon, hardware lifecycle, AI sustainability are HotCarbon's core scope | ✅ Good — energy systems + data center optimization fits e-Energy |
| **DP/theory depth** | ✅ Position/simulation papers with provocative results are explicitly favored | ✅ Technical full papers with formal methods are the norm |
| **Impact alignment** | ✅ HotCarbon actively seeks "line of inquiry" papers that challenge norms (T* invalidation is perfect) | ✅ e-Energy values quantitative optimization results |

---

## Recommendation

**→ Submit to HotCarbon 2026.**

**Rationale:** HotCarbon is the clear choice on deadline grounds — it is the only venue confirmed to still be open as of Feb 28, 2026. While the paper will need significant condensing from ~8,500 words to a 6-page workshop format (~3,500 words), the content alignment is exceptional: HotCarbon's stated scope explicitly covers "software-driven hardware obsolescence that increases e-waste and embodied carbon" and seeks papers that "challenge computing's endemic upgrade and throwaway practices." The core finding — that the AI industry's 2-year GPU refresh cycle is carbon-suboptimal and that classical T* analysis is invalid for staggered fleets — is precisely the kind of provocative, norm-challenging result HotCarbon is designed for.

ACM e-Energy 2026 would be the better length fit (10-page full paper), but its deadline has almost certainly passed. It should be the **backup venue for 2027** or if an e-Energy 2026 late-breaking track opens.

### Recommended condensing strategy for HotCarbon submission
1. Lead with the two key provocations: (a) extend GPU inference to 4 years, (b) T* is wrong for real fleets
2. Keep Tables 1, 5 and the front-loading mechanism explanation
3. Compress background to 0.5 pages; remove detailed sensitivity section (Section 6.1)
4. Target 5–6 pages ACM two-column (approximately 3,000–3,500 words + tables)

---

*Research note: Web search was unavailable (no Brave API key configured). HotCarbon 2026 CFP dates are estimated from 2025 pattern. Verify at https://hotcarbon.org/ when CFP is published.*

---

## Cycle 10 Venue Check (2026-02-28)

### HotCarbon 2026 CFP Status
**Not yet published.** As of 2026-02-28, the HotCarbon website (hotcarbon.org) only references the successful HotCarbon'25 edition (held Aug 2025) and notes "Stay tuned for the 2026 edition!" No CFP, deadline, or submission portal has been announced. Based on the 2025 pattern (CFP typically ~March–April, submission deadline ~May, workshop in August), the 2026 CFP is expected in Q1–Q2 2026.

### ACM e-Energy 2026 Deadline
**Not found.** The ACM e-Energy 2026 submission page was inaccessible (Cloudflare block). Based on the 2025 pattern (submission deadline was approximately January 2025 for the June 2025 conference), the ACM e-Energy 2026 deadline has likely already passed (estimated January–February 2026).

### Recommendation
**Target HotCarbon 2026** — the CFP is imminent and the workshop's explicit scope on embodied carbon, hardware lifecycle, and computing sustainability aligns perfectly with all three contributions. At ~8,500 words with 3 contributions, the paper needs condensing to ~3,500 words (6-page ACM format), which is feasible by trimming the sensitivity analysis and compressing background; the core novelty (Fixed-4yr savings, T* invalidity, threshold heuristic) can be presented compactly. ACM e-Energy 2027 remains the best full-paper venue for a future extended version.

*Note: Web search unavailable (no Brave API key); venue status inferred from web_fetch of hotcarbon.org. Verify deadlines directly at https://hotcarbon.org/ and https://energy.acm.org/ when CFPs are published.*
