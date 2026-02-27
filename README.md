# CloudSim Energy Research

**Carbon-Aware Temporal Deferral in Single-Datacenter Cloud Scheduling**

> *Simulation-Based Policy Comparison and Mechanism Analysis*

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Paper-Ready](https://img.shields.io/badge/status-paper--ready-brightgreen.svg)]()

---

## 📋 Overview

This repository contains the full simulation framework, experimental scripts, results, and paper draft for a research study on **carbon-aware cloud scheduling**. The core finding: a simple carbon-intensity threshold policy achieves **4.83–15.52% carbon reduction** in a single-datacenter simulation with **zero energy overhead**, and this gain is orthogonally composable with variance-aware VM consolidation (VAR-PABFD) for a combined **5% energy + 10% carbon** improvement.

---

## 🔑 Key Results

| Policy | Carbon Saving | Energy Saving | SLA Violations |
|--------|--------------|---------------|----------------|
| Threshold (simple) | 4.83–15.52% | 0.00% | 0% |
| Adaptive | 5.21–16.43% | 0.00% | 0% |
| Oracle (upper bound) | 7.51–18.43% | 0.00% | 0% |
| VAR-PABFD (spatial) | — | 2.73–5.47% | 0% |
| **Combined** | **~10%** | **~5%** | **<3.1%*** |

*\*SLA burst artifact from batch queue release, discussed in paper.*

**Threshold policy captures 76.4% of oracle savings** — confirming Sukprasert et al. (2024) empirical estimate (75–90%) via simulation for the first time.

---

## 🏗️ Repository Structure

```
cloudsim-energy-research/
├── paper.md                    # Full paper draft (v0.2, 9 sections, ~8000 words)
├── figures/                    # 6 publication-quality PNG figures
│   ├── fig1_ci_profile.png     # Diurnal CI profile with deferral window
│   ├── fig2_carbon_savings.png # Carbon savings by policy × scenario (grouped bars)
│   ├── fig3_energy_neutral.png # Energy overhead scatter (all 0.00%)
│   ├── fig4_threshold_efficiency.png # Threshold vs oracle efficiency
│   ├── fig5_orthogonality.png  # 2×2 factorial: VAR-PABFD × Carbon Deferral
│   └── fig6_ci_swing.png       # Carbon saving vs CI swing deployability map
│
├── # --- PRIMARY SIMULATION SCRIPTS ---
├── simulate-carbon.py          # Main experiment: 4 policies × 3 scenarios × 10 seeds
├── simulate-combined.py        # Orthogonality: 2×2 factorial VAR-PABFD × carbon deferral
├── simulate-slo.py / simulate_slo.py  # VAR-PABFD SLO headroom experiment
├── ablation-ci-variability.py  # CI swing sensitivity ablation
├── generate-figures.py         # Figure generation (matplotlib)
│
├── # --- FALSIFICATION SCRIPTS ---
├── falsification-carbon.py     # Direction #17 falsification (PASSED)
├── falsification-slo.py        # Direction #8 falsification (BORDERLINE→PROCEED)
├── falsification-scale.py      # Scale extension analysis
├── falsification-predictive.py # Direction #3 falsification (FAILED)
├── falsification-check.py      # Direction #1/#2 falsification
│
├── # --- ANALYSIS & DOCUMENTATION ---
├── analysis-carbon.md          # Full analysis: results, mechanism, hypothesis eval
├── lit-review-carbon.md        # Literature review (6 papers, novelty gap confirmed)
├── brainstorm.md               # 15 candidate directions with scoring
├── LOGBOX.md                   # Full decision log (all pivots, results, rationale)
├── protocol.md / protocol-predictive.md  # Pre-registered protocols
└── results/                    # Raw simulation output CSVs
```

---

## ⚙️ Reproducing the Experiments

### Requirements

```bash
pip install numpy scipy matplotlib pandas
```

No external dependencies beyond the Python standard library + NumPy/SciPy/Matplotlib.

### Main experiment (120 runs, ~2 minutes)

```bash
python simulate-carbon.py
```

Runs 4 policies × 3 batch-flexibility scenarios × 10 seeds. Prints results table to stdout and saves per-run CSV to `results/`.

### Combined orthogonality experiment (40 runs)

```bash
python simulate-combined.py
```

2×2 factorial: {PABFD, VAR-PABFD} × {no-deferral, threshold-deferral}. Verifies Theorem 6.1.

### CI variability ablation

```bash
python ablation-ci-variability.py
```

Varies grid CI swing from 1× to 8× to produce deployability threshold analysis (Fig. 6).

### Generate figures

```bash
python generate-figures.py
```

Produces all 6 figures in `figures/` at 150 DPI.

---

## 🧪 Simulation Model

The simulation implements a **CloudSim-style Python framework** with:

- **10 physical hosts**, each 100-core, 120W idle / 250W peak, linear power model
- **VM arrivals** following a Poisson process (λ varies by scenario), duration exponentially distributed
- **Scheduling policies:**
  - `PABFD` — Power-Aware Best Fit Decreasing (Beloglazov et al. 2012 baseline)
  - `VAR-PABFD` — Variance-Aware PABFD: sets per-host U_HIGH = 0.92 for low-variance VMs (σ² < 0.005), 0.75 for bursty VMs
  - `Threshold` — Defers batch jobs when CI > τ (120 gCO₂/kWh); dispatches immediately when CI ≤ τ
  - `Adaptive` — Adjusts τ based on CI forecast to match deadline distribution
  - `Oracle` — Schedules each job at the lowest-CI window within its deadline window
- **Carbon Intensity model:** US Midwest diurnal profile, 71–399 gCO₂/kWh, 5.6× swing
- **Batch flexibility:** controlled by `batch_fraction` (0.30) and `max_defer_hours` (2/4/6h)

---

## 📊 Theoretical Contributions

### Energy Neutrality Lemma (Lemma 2.1)

For any VM scheduling policy that defers (not discards) batch workloads:

```
E_total(shifted) = E_total(baseline)
```

*Proof sketch:* Under linear power models P(u) = a + bu, total energy consumed is
proportional to total compute-seconds of work. Deferral preserves total work volume;
only the time-placement changes. Therefore ΔE = 0 exactly, and carbon savings are
strictly zero-cost. ∎

### PABFD Optimality Theorem (Appendix A, Theorem A.1)

For linear host power P(u) = a + bu AND linear PUE(u_DC) = α + β·u_DC:

> *No VM placement policy outperforms PABFD in expected total energy.*

Because any permutation of VMs among active hosts yields identical total E_compute (the 
per-host contribution b·δ cancels), the only lever is HOST ON/OFF decisions — which PABFD 
maximizes by design. This explains why directions #2 (Dynamic PUE) and #3 (Predictive 
Consolidation) produced null results analytically.

### Orthogonality Theorem (Theorem 6.1)

VAR-PABFD (spatial consolidation) and Carbon Deferral (temporal shifting) are independent 
mechanisms. Their combined saving satisfies:

```
S_combined = S_spatial + S_temporal + ε,  |ε| < 0.1%
```

Proven by noting that spatial decisions (which host is active) are invariant to temporal 
reordering of jobs, and temporal decisions (when a job runs) are invariant to spatial 
packing policy. Validated empirically (synergy < 0.03% in all 40 combined-experiment runs).

---

## 📄 Paper

**Title:** Carbon-Aware Temporal Deferral in Single-Datacenter Cloud Scheduling: Simulation-Based Policy Comparison and Mechanism Analysis

**Target venues:**
- IEEE Transactions on Cloud Computing (primary)
- CCGrid 2026
- IEEE/ACM GreenCom 2026

**Paper draft:** [`paper.md`](paper.md) (v0.2, figures added 2026-02-27)

**Sections:** Abstract · Introduction · Background · System Model · Policy Definitions · Experimental Evaluation · Orthogonality Theorem · Discussion · Related Work · Conclusion · Appendix A (PABFD Optimality Proof)

---

## 🗺️ Research Journey & Pivots

This project explored 5+ directions before finding the publishable result. All decisions are logged in [`LOGBOX.md`](LOGBOX.md):

| Direction | Score | Result | Why Archived |
|-----------|-------|--------|--------------|
| #1 Migration energy | 4.6/5 | NULL (0.2%) | Migration energy < 1% of compute energy |
| #2 Dynamic PUE | 4.3/5 | NULL (0.0%) | Analytically degenerate for linear P/PUE (Theorem A.1) |
| #3 Predictive consolidation | 4.2/5 | NULL (0.6%) | PABFD fires every 300s; linger window too small |
| #8 SLO headroom (VAR-PABFD) | 4.0/5 | **VIABLE (2.7–5.5%)** | Sub-threshold standalone; included as contribution |
| **#17 Carbon deferral** | **4.5/5** | **✅ VIABLE (5–18%)** | **Primary result — paper contribution** |

The linear degeneracy theorem (proven during #2 analysis) is itself a publishable negative result explaining why a large class of scheduling improvements cannot outperform PABFD for single-datacenter deployments.

---

## 🔗 References

1. Beloglazov, A., Abawajy, J., & Buyya, R. (2012). Energy-aware resource allocation heuristics for efficient management of data centers for cloud computing. *FGCS* 28(5):755–768.
2. Wiesner, P., Behnke, I., Scheinert, D., Gontarska, K., & Thamsen, L. (2021). Let's Wait Awhile: How Temporal Workload Shifting Can Reduce Carbon Emissions in the Cloud. *Middleware 2021*. arXiv:2110.13234.
3. Sukprasert, T., Souza, A., Bashir, N., Irwin, D., & Shenoy, P. (2024). On the Limitations of Carbon-Aware Temporal and Spatial Workload Shifting in the Cloud. *EuroSys 2024*. arXiv:2306.06502.
4. Hanafy, W.A., Wu, L., Irwin, D., & Shenoy, P. (2025). CarbonFlex: Enabling Carbon-aware Provisioning and Scheduling for Cloud Clusters.
5. Souza, A., et al. (2024). CASPER: Carbon-Aware Scheduling and Provisioning for Distributed Web Services. *EuroSys 2024*.
6. Masanet, E., Shehabi, A., Lei, N., Smith, S., & Koomey, J. (2020). Recalibrating global data center energy-use estimates. *Science* 367(6481):984–986.
7. Calheiros, R.N., Ranjan, R., Beloglazov, A., De Rose, C.A.F., & Buyya, R. (2011). CloudSim: A toolkit for modeling and simulation of cloud computing environments. *Software: Practice and Experience* 41(1):23–50.

---

## 📜 License

MIT License. Simulation code, figures, and paper draft are freely available for research use.

---

*Last updated: 2026-02-27 | Research Advisor (auto) | OpenClaw*
