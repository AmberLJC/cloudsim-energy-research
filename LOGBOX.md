# Research Logbox — CloudSim Energy Optimization

## Decision Log
| # | Phase | Summary | Date |
|---|-------|---------|------|
| 1 | Init | Project created. Topic: cloud infra energy consumption optimization using CloudSim as simulation platform. CPU-only constraint. | 2026-02-27 |
| 2 | Brainstorm | Entering brainstorming phase. Goal: find a unique angle that is NOT just another VM consolidation scheduler. | 2026-02-27 |
| 3 | Brainstorm | Generated 15 candidate directions via literature survey (arXiv CloudSim/carbon-aware/energy-aware). Top scorer: #1 Migration-Energy-Aware Consolidation (4.6/5). Top novelty: #2 Dynamic PUE (4.3/5). Proposed combining both. Research statement written. Awaiting Amber confirmation before entering Lit Review. | 2026-02-27 |
| 4 | Brainstorm/Falsification | Ran falsification-check.py. CRITICAL NULL RESULT: Migration energy (#1) is ~0.20% of compute energy (all configs) — PIVOT. Dynamic PUE (#2) shows 32-50% energy difference between policies — VIABLE. | 2026-02-27 |
| 5 | Brainstorm/LitReview | Completed literature review (12 papers). Sources: Semantic Scholar, OpenAlex, GitHub. Key finding: Buyya 2023 explicitly identifies dynamic PUE as open work. Pasupuleti 2024 does thermal-aware CloudSim scheduling but uses CFD temperature, not PUE. No paper implements load-dependent PUE in CloudSim. Novelty gap CONFIRMED for #2. | 2026-02-27 |
| 6 | Protocol | Wrote protocol.md. Pre-registered hypothesis, locked PUE model (PUE(u)=1.8-0.6*u), D-PABFD algorithm design, metrics, stopping rule. Primary dataset: synthetic Poisson workload (10 seeds × 5 algos × 3 load scenarios = 150 runs). Null result threshold: <2% improvement. Proceed threshold: >5% in 2/3 scenarios. | 2026-02-27 |
| 7 | Pivot | Dropped #1 (migration energy) as primary direction. REASON: falsification shows <1% effect size — not publishable. #2 (Dynamic PUE) is now sole primary direction. #12 (non-linear power models) retained as complementary secondary. | 2026-02-27 |
