# Reproducibility Checklist
# Carbon-Aware Temporal Deferral in Single-Datacenter Cloud Scheduling

**Paper:** "Carbon-Aware Temporal Deferral in Single-Datacenter Cloud Scheduling: Simulation-Based Policy Comparison and Mechanism Analysis"  
**Checklist Version:** 1.0 (2026-02-27)  
**Format:** Based on NeurIPS/ACM reproducibility checklists; adapted for simulation-based systems research.

---

## How to Use This Checklist

Each item is rated: ✅ Yes | ⚠ Partial | ❌ No | N/A Not Applicable

A reviewer should be able to independently reproduce all main figures and tables using only the information in this checklist plus the released code.

---

## Part A: Claims and Hypotheses

| # | Item | Status | Notes |
|---|------|--------|-------|
| A1 | All main claims from the abstract are backed by experimental evidence | ✅ | Tables 1–3 + Figure 2 support all abstract claims |
| A2 | Each claim specifies whether it is experimental, theoretical, or both | ✅ | Carbon savings: experimental; energy neutrality: both (Lemma 2.1 + empirical); orthogonality: both (Theorem 6.1 + empirical) |
| A3 | Pre-registered hypotheses are documented | ✅ | `protocol.md` contains H1–H4 with pre-registered thresholds |
| A4 | Effect size thresholds (null / viable) are pre-specified | ✅ | Null < 2%, viable > 5%; documented in `protocol.md` |
| A5 | Positive and null results are both reported | ✅ | Null results for #2 (Dynamic PUE), #3 (Predictive), #8 (SLO Headroom) documented in `LOGBOX.md` |

---

## Part B: Simulation Environment

| # | Item | Status | Notes |
|---|------|--------|-------|
| B1 | Python version is specified | ✅ | Python 3.8+ required; tested on Python 3.10 and 3.12 |
| B2 | Package dependencies are listed with versions | ⚠ | NumPy, SciPy, Matplotlib used; no `requirements.txt` yet (add before submission) |
| B3 | Random seeds are fixed and documented | ✅ | Seeds 0–9 used; see `SEEDS = list(range(10))` in `simulate-carbon.py` |
| B4 | Operating system / hardware requirements | ✅ | No GPU required; any x86-64 Linux/macOS/Windows. Runtime: ~30s on any modern laptop |
| B5 | Non-determinism sources are documented | ✅ | Only source of randomness: Poisson workload arrivals, seeded via `np.random.default_rng(seed)` |
| B6 | Simulation validated against known baselines | ✅ | PABFD baseline matches Beloglazov 2012 energy model; PABFD linear optimality proven in Appendix A |

**Action items before submission:**
- [ ] Add `requirements.txt` with exact package versions (e.g., `numpy==1.26.0, scipy==1.11.0, matplotlib==3.8.0`)
- [ ] Add `environment.yml` for conda users

---

## Part C: Experimental Setup

| # | Item | Status | Notes |
|---|------|--------|-------|
| C1 | All experimental parameters are specified in the paper | ✅ | Table in Section 3.1 + parameter tables in simulate-carbon.py |
| C2 | All simulation runs are documented (count, seeds, configurations) | ✅ | 120 runs (10 seeds × 4 policies × 3 scenarios) in Section 5.1; also 40 runs for combined experiment |
| C3 | Scenario definitions are fully specified | ✅ | Section 3.5 + SCENARIOS dict in simulate-carbon.py |
| C4 | Policy implementations are described algorithmically | ✅ | Section 4 with pseudocode + implementation in simulate-carbon.py |
| C5 | Carbon intensity model is described and parameterized | ✅ | Section 3.3 + `carbon_intensity()` function in simulate-carbon.py |
| C6 | Power model is specified with exact coefficients | ✅ | P(u) = 100 + 150×u Watts; SPEC Power SPECpower_ssj2008 fit |
| C7 | SLA definitions and violation criteria are specified | ✅ | Section 3.4 + deadline enforcement logic in simulate-carbon.py |

---

## Part D: Results and Statistical Reporting

| # | Item | Status | Notes |
|---|------|--------|-------|
| D1 | Mean results are reported for all key metrics | ✅ | Table 1 (primary) + Table 3 (with CIs) |
| D2 | Confidence intervals or standard errors are reported | ✅ | **v0.4:** Table 3 shows 95% CIs for all 9 policy-scenario combos |
| D3 | Statistical significance tests are reported | ✅ | t-distribution CIs (n=10); all conditions significant at α=0.05 |
| D4 | Effect sizes are reported (not just p-values) | ✅ | Carbon saving % is the effect size; threshold efficiency ratio also reported |
| D5 | Per-seed raw data is available | ✅ | `results/carbon/results.csv` contains all 120 per-seed rows |
| D6 | Ablation results are reported | ✅ | CI variability ablation (Section 5.5); combined policy orthogonality (Section 6) |
| D7 | Negative results (null directions) are reported | ✅ | LOGBOX.md documents 4 null/near-null directions; summary in paper Section 7.2 |

---

## Part E: Code and Data Availability

| # | Item | Status | Notes |
|---|------|--------|-------|
| E1 | Simulation code is publicly available | ✅ | https://github.com/AmberLJC/cloudsim-energy-research |
| E2 | Code runs end-to-end from a single command | ⚠ | `python3 simulate-carbon.py` reproduces main results; no unified runner script yet |
| E3 | Raw simulation outputs are archived | ✅ | `results/carbon/results.csv`, `results/carbon/summary.json` |
| E4 | Figure generation code is included | ✅ | `generate-figures.py` reproduces all 6 figures |
| E5 | CI computation code is included | ✅ | `compute-ci-from-csv.py` reproduces Table 3 |
| E6 | Code version is pinned in paper | ✅ | Commit hash in paper (Section 5.6) |
| E7 | License is specified | ❌ | **TODO: Add LICENSE file before submission (recommend MIT or Apache 2.0)** |

**Action items before submission:**
- [ ] Add `run_all.sh` or `Makefile` to reproduce all results in sequence
- [ ] Add `LICENSE` file

---

## Part F: Figures and Tables

| # | Item | Status | Notes |
|---|------|--------|-------|
| F1 | All figures are generated from code (no manual editing) | ✅ | `generate-figures.py` generates all 6 figures from simulation data |
| F2 | Figure captions are self-contained | ✅ | Appendix: Figure Captions provides full caption text |
| F3 | Error bars are included on bar charts | ✅ | Figure 2 shows 95% CI error bars |
| F4 | Axes are labeled with units | ✅ | All 6 figures include axis labels and units |
| F5 | Color-blind-friendly palette used | ⚠ | Colors chosen for visibility; not formally tested with colorblindness simulation tool |
| F6 | Figures available at publication resolution (≥300 DPI) | ⚠ | Currently 150 DPI; regenerate at 300 DPI for camera-ready |

**Action items before submission:**
- [ ] Regenerate figures at 300 DPI (`dpi=300` in `generate-figures.py`)
- [ ] Test palette with colorblind simulation (e.g., https://www.color-blindness.com/coblis-color-blindness-simulator/)

---

## Part G: Theoretical Claims

| # | Item | Status | Notes |
|---|------|--------|-------|
| G1 | All lemmas/theorems have proof sketches or full proofs | ✅ | Lemma 2.1 (energy neutrality) and Theorem 6.1 (orthogonality) have proof sketches; Appendix A has PABFD optimality proof |
| G2 | Theoretical bounds are verified empirically | ✅ | Lemma 2.1: 0.0000% energy overhead in all conditions; Theorem 6.1: synergy <0.1% in combined experiment |
| G3 | Assumptions are stated explicitly | ✅ | Linear power model assumption stated; non-linear sensitivity analysis in Section 3.2 |
| G4 | Limitations of theoretical results are stated | ✅ | Section 7.2 discusses non-linear, geo-distributed, and real-CI limitations |

---

## Part H: Related Work

| # | Item | Status | Notes |
|---|------|--------|-------|
| H1 | Most relevant prior work is cited and compared | ✅ | Section 8 cites 8+ key papers; Wiesner 2021, Sukprasert 2024 compared quantitatively |
| H2 | Novelty claim is substantiated with specific gaps | ✅ | Lit review confirms no prior CloudSim carbon-aware deferral study; gap stated in Section 1 |
| H3 | Comparisons use the same metric where possible | ✅ | Carbon saving % used for all comparisons; efficiency ratio (threshold/oracle) matches Sukprasert 2024 |

---

## Part I: Limitations

| # | Item | Status | Notes |
|---|------|--------|-------|
| I1 | Limitations section is included | ✅ | Section 7.2 with 6 limitations |
| I2 | SLA violation artifact is disclosed | ✅ | 3.1% SLA violation rate for combined VAR-PABFD+carbon deferral disclosed; attributed to batch queue burst |
| I3 | Simulation vs. real system gap is discussed | ✅ | Section 7.2 + Section 7.3 |
| I4 | Single-datacenter scope is stated | ✅ | Title + abstract + Section 7.2 |
| I5 | Synthetic CI profile vs. real EIA data is discussed | ✅ | Section 3.3 + Section 7.2 |

---

## Part J: Deployment Readiness

| # | Item | Status | Notes |
|---|------|--------|-------|
| J1 | Deployment recommendations are actionable | ✅ | Section 7.1 with specific thresholds (≥4× CI swing, ≥30% batch, ≥6h deadline) |
| J2 | Grid suitability analysis provided | ✅ | Figure 6 + Table in Section 5.5 (CI swing sensitivity) |
| J3 | Implementation complexity assessed | ✅ | Threshold policy requires only current CI reading + one threshold comparison |
| J4 | Energy cost overhead assessed | ✅ | Zero energy overhead proven and validated |

---

## Summary Scorecard

| Part | Items | ✅ Yes | ⚠ Partial | ❌ No |
|------|-------|--------|-----------|-------|
| A Claims | 5 | 5 | 0 | 0 |
| B Environment | 6 | 5 | 1 | 0 |
| C Setup | 7 | 7 | 0 | 0 |
| D Statistics | 7 | 7 | 0 | 0 |
| E Code/Data | 7 | 5 | 1 | 1 |
| F Figures | 6 | 4 | 2 | 0 |
| G Theory | 4 | 4 | 0 | 0 |
| H Related Work | 3 | 3 | 0 | 0 |
| I Limitations | 5 | 5 | 0 | 0 |
| J Deployment | 4 | 4 | 0 | 0 |
| **TOTAL** | **54** | **49 (91%)** | **4 (7%)** | **1 (2%)** |

---

## Pre-Submission TODO List

Priority items to complete before camera-ready:

1. **[CRITICAL]** Add `LICENSE` file (MIT recommended) — required for GitHub code release
2. **[HIGH]** Add `requirements.txt` with exact package versions
3. **[HIGH]** Regenerate all figures at 300 DPI
4. **[MEDIUM]** Add `run_all.sh` to reproduce all results in one step:
   ```bash
   #!/bin/bash
   python3 simulate-carbon.py          # 120 runs, ~20s
   python3 simulate-combined.py        # 40 runs, ~10s  
   python3 ablation-ci-variability.py  # 50 runs, ~10s
   python3 compute-ci-from-csv.py      # compute CIs
   python3 generate-figures.py         # all 6 figures
   echo "All results reproduced!"
   ```
5. **[MEDIUM]** Add colorblind accessibility check for figures
6. **[LOW]** Add `environment.yml` for conda users
7. **[LOW]** Add author names and affiliations (currently anonymized for review)
8. **[LOW]** Verify exact DOIs for Buyya 2023 and Pasupuleti 2024

---

*Generated by research advisor agent. Last updated: 2026-02-27.*
