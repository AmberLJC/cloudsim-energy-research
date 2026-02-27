# Literature Review — Direction #3: Proactive/Predictive VM Consolidation

**Phase:** Lit Review | **Started:** 2026-02-27 | **Target:** ≥15 papers
**Direction:** Proactive host power management via demand prediction in cloud datacenters
**Research statement:** Reactive consolidation policies leave hosts idle for 5-15 minutes per
cycle before shutting them down. A lightweight temporal predictor (ARIMA or exponential
smoothing) over per-host utilization time series can anticipate demand troughs and initiate
host shutdown earlier, reducing idle host energy by a measurable and practically significant
margin. We call this policy P-PABFD (Predictive-PABFD) and compare to PABFD, FFD, and
an oracle (perfect future knowledge).

---

## Novelty Hypothesis (to confirm or refute during review)

**Claim:** No published paper has specifically compared REACTIVE vs. PROACTIVE host shutdown
timing as a primary energy optimization lever in CloudSim simulations, isolating the
contribution of prediction accuracy to idle host energy savings.

Related but different work exists:
- Workload prediction for SLA management (many papers)
- Consolidation policy design (PABFD, RR, MMT — many papers)
- Energy-aware autoscaling (some papers)

**Gap to confirm:** Prediction specifically for HOST POWER STATE MANAGEMENT (on/off timing),
not just VM placement or SLA-driven scaling.

---

## Search Strategy

Databases:
- arXiv (cs.DC, cs.NI, cs.SY)
- Semantic Scholar
- ACM Digital Library
- IEEE Xplore

Search terms:
- "predictive VM consolidation energy"
- "proactive host power management cloud"
- "workload prediction CloudSim energy"
- "ARIMA cloud energy scheduling"
- "temporal prediction datacenter energy"
- "idle host energy cloud simulation"

---

## Papers Surveyed (Target: ≥15)

### P1 — [TO BE FILLED]
**Citation:**
**Venue/Year:**
**Method:**
**Claim:**
**Relevance:**
**Novelty gap assessment:**

### P2 — [TO BE FILLED]
...

---

## Evidence Map (to be updated as papers are added)

| Mechanism | Papers using it | Notes |
|-----------|----------------|-------|
| Workload prediction (ARIMA/LSTM) | — | |
| Reactive consolidation (PABFD baseline) | — | |
| Proactive host power management | — | |
| Idle host energy as primary metric | — | |

---

## Novelty Gap Status

**Status: UNCONFIRMED (pending review)**

Will update to CONFIRMED or CLOSED as papers are surveyed.

---

## Exit Criteria Checklist

- [ ] ≥15 papers surveyed and summarized
- [ ] Novelty gap confirmed (no paper does proactive host-level shutdown with energy focus)
- [ ] Evidence map written showing where our work sits
- [ ] At least 2 directly comparable baselines identified for protocol

---

## Notes

- Prior lit-review.md (for #2 Dynamic PUE) may contain relevant papers on CloudSim energy
  baselines — carry forward P1–P15 where applicable (Beloglazov 2012 at minimum).
- Key prior work to check: Lorido-Botran 2014 (survey of auto-scaling), Urgaonkar 2005
  (resource overbooking), Meng 2010 (imMEDIAte), Shen 2011 (cloudscale).
