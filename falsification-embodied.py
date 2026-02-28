"""
falsification-embodied.py — Embodied Carbon Lifecycle Optimization
===================================================================
Models the tradeoff between embodied carbon (manufacturing) and operational
carbon (electricity) for server refresh cycles.

Model:
  - P_old = 250W baseline server power
  - After N years of hardware improvement, P_new = 250 × (1 - efficiency_gain)^N W
  - Embodied carbon: C_emb ∈ {500, 1000, 1500, 2000} kgCO2
  - Grid CI: 50–800 gCO2/kWh
  - Operational carbon per year: P_kW × 8760h × CI_kg_per_kWh
  - Planning horizon: 15 years
  - Find optimal refresh lifetime T* minimising total lifecycle carbon

Key questions:
  Q1. How does T* vary with grid CI?
  Q2. At what CI does the crossover occur (refreshing MORE often becomes WORSE)?
  Q3. How far is industry norm (5yr) from optimal?
  Q4. Carbon debt of AI-driven 2-year GPU refresh cycles vs optimal?
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from itertools import product
import os

HORIZON = 15          # years
P_OLD_W = 250         # watts, baseline 5+ yr old server
HOURS_PER_YEAR = 8760

EFFICIENCY_GAINS = [0.10, 0.15, 0.20]   # annual efficiency improvement
EMBODIED_CARBONS = [500, 1000, 1500, 2000]  # kgCO2 per server
CI_VALUES = np.arange(50, 850, 50)       # gCO2/kWh, 50..800
LIFETIMES = list(range(1, HORIZON + 1))  # T* candidates 1..15 yrs

INDUSTRY_NORM = 5     # years (typical enterprise refresh)
AI_CYCLE = 2          # years (aggressive GPU replacement)


def compute_total_carbon(efficiency_gain, embodied_kg, ci_g_per_kwh, lifetime_T, horizon=HORIZON):
    """
    Compute total carbon (kg CO2) over `horizon` years for a fleet of 1 server
    refreshed every `lifetime_T` years.

    Strategy: at t=0 we deploy a server that is already 'lifetime_T years old'
    in terms of its efficiency vintage. Every lifetime_T years we pay embodied_kg
    and deploy a server that is vintage=0 (new, most efficient at time of deployment).
    For simplicity, the operational power after k full cycles is P_new = P_OLD_W *
    (1-efficiency_gain)^(k*lifetime_T) — i.e., each replacement buys the efficiency
    of a server manufactured T years after the previous one.

    Carbon accounting:
      - Refresh events: floor(horizon / lifetime_T) replacements (first one is at t=0)
      - Last server runs to end of horizon
    """
    ci_kg_per_kwh = ci_g_per_kwh / 1000.0

    total_carbon = 0.0
    t = 0
    cycle = 0
    while t < horizon:
        # Embodied carbon for this server generation
        total_carbon += embodied_kg

        # Power of this server generation (cumulative efficiency improvement)
        p_w = P_OLD_W * ((1.0 - efficiency_gain) ** cycle)
        p_kw = p_w / 1000.0

        # Operational years until next refresh (or end of horizon)
        run_years = min(lifetime_T, horizon - t)
        op_carbon = p_kw * HOURS_PER_YEAR * ci_kg_per_kwh * run_years
        total_carbon += op_carbon

        t += lifetime_T
        cycle += 1

    return total_carbon


def find_optimal_lifetime(efficiency_gain, embodied_kg, ci_g_per_kwh):
    """Return (T*, min_carbon) — the lifetime minimising total carbon."""
    best_T = None
    best_carbon = float('inf')
    for T in LIFETIMES:
        c = compute_total_carbon(efficiency_gain, embodied_kg, ci_g_per_kwh, T)
        if c < best_carbon:
            best_carbon = c
            best_T = T
    return best_T, best_carbon


# ─────────────────────────────────────────────────────────────────────────────
# Main analysis
# ─────────────────────────────────────────────────────────────────────────────

results = {}  # (eff_gain, embodied) -> {ci: (T*, total_carbon)}

print("=" * 70)
print("FALSIFICATION: Embodied Carbon Lifecycle Optimisation")
print("=" * 70)

for eff, emb in product(EFFICIENCY_GAINS, EMBODIED_CARBONS):
    key = (eff, emb)
    results[key] = {}
    for ci in CI_VALUES:
        T_star, c_opt = find_optimal_lifetime(eff, emb, ci)
        results[key][ci] = (T_star, c_opt)

# ─────────────────────────────────────────────────────────────────────────────
# Q1: T* range across CI for each efficiency gain (pick median embodied = 1000)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Q1: Optimal T* across CI range (Embodied=1000 kgCO2) ──")
print(f"{'CI (gCO2/kWh)':>18} | " + " | ".join(f"eff={e:.0%} T*" for e in EFFICIENCY_GAINS))
print("-" * 65)
for ci in CI_VALUES:
    row = f"{ci:>18} |"
    for eff in EFFICIENCY_GAINS:
        T_star = results[(eff, 1000)][ci][0]
        row += f"  {T_star:>10}      |"
    print(row)

# T* range per efficiency gain
print("\n── T* variation summary (Embodied=1000 kgCO2) ──")
for eff in EFFICIENCY_GAINS:
    t_stars = [results[(eff, 1000)][ci][0] for ci in CI_VALUES]
    print(f"  eff={eff:.0%}: T* range = [{min(t_stars)}, {max(t_stars)}] yrs  "
          f"(span={max(t_stars)-min(t_stars)} yrs)")

# ─────────────────────────────────────────────────────────────────────────────
# Q2: Crossover CI — where refreshing MORE often (T<5) becomes WORSE than T=5
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Q2: Crossover CI (where T*=5yr becomes optimal or T* transitions) ──")
for eff in EFFICIENCY_GAINS:
    prev_T = None
    crossovers = []
    for ci in CI_VALUES:
        T_star = results[(eff, 1000)][ci][0]
        if prev_T is not None and T_star != prev_T:
            crossovers.append((ci, prev_T, T_star))
        prev_T = T_star
    print(f"  eff={eff:.0%} crossovers at CI: {crossovers}")

# ─────────────────────────────────────────────────────────────────────────────
# Q3: Industry norm (5yr) error vs optimal
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Q3: Industry norm (5yr) carbon vs. optimal — worst-case per CI ──")
print(f"{'CI':>6} | {'eff':>6} | {'emb':>6} | {'C_opt':>10} | {'C_5yr':>10} | {'excess%':>8} | T*")
print("-" * 70)

max_excess_pct = 0.0
max_excess_config = None

for ci in [50, 100, 200, 400, 600, 800]:
    for eff in EFFICIENCY_GAINS:
        for emb in EMBODIED_CARBONS:
            T_star, c_opt = results[(eff, emb)][ci]
            c_5yr = compute_total_carbon(eff, emb, ci, INDUSTRY_NORM)
            excess_pct = (c_5yr - c_opt) / c_opt * 100
            if excess_pct > max_excess_pct:
                max_excess_pct = excess_pct
                max_excess_config = (ci, eff, emb, T_star, c_opt, c_5yr, excess_pct)
            if abs(excess_pct) > 20 or (ci in [50, 400, 800] and eff == 0.15 and emb == 1000):
                print(f"{ci:>6} | {eff:>6.0%} | {emb:>6} | {c_opt:>10.1f} | {c_5yr:>10.1f} | "
                      f"{excess_pct:>7.1f}% | {T_star}")

print(f"\nMAX excess carbon from industry 5yr norm: {max_excess_pct:.1f}%")
if max_excess_config:
    ci, eff, emb, T_s, c_o, c_5, ep = max_excess_config
    print(f"  at CI={ci}, eff={eff:.0%}, emb={emb}: T*={T_s}, "
          f"excess={ep:.1f}% ({c_5:.0f} vs {c_o:.0f} kgCO2)")

# ─────────────────────────────────────────────────────────────────────────────
# Q4: Carbon debt of AI-driven 2-yr refresh vs optimal
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Q4: Carbon debt of 2yr AI refresh cycle vs optimal ──")
print(f"{'CI':>6} | {'eff':>6} | {'emb':>6} | {'T*':>4} | {'C_2yr':>10} | "
      f"{'C_opt':>10} | {'debt%':>8}")
print("-" * 65)

debt_cases = []
for ci in [50, 100, 200, 400, 600, 800]:
    for eff in EFFICIENCY_GAINS:
        for emb in [500, 1000, 1500, 2000]:
            T_star, c_opt = results[(eff, emb)][ci]
            c_2yr = compute_total_carbon(eff, emb, ci, AI_CYCLE)
            debt_pct = (c_2yr - c_opt) / c_opt * 100
            debt_cases.append((ci, eff, emb, T_star, c_2yr, c_opt, debt_pct))
            if (ci in [50, 100, 400] and eff == 0.15 and emb in [1000, 1500]):
                print(f"{ci:>6} | {eff:>6.0%} | {emb:>6} | {T_star:>4} | "
                      f"{c_2yr:>10.1f} | {c_opt:>10.1f} | {debt_pct:>7.1f}%")

max_debt = max(debt_cases, key=lambda x: x[6])
print(f"\nMAX 2yr-cycle carbon debt: {max_debt[6]:.1f}% at "
      f"CI={max_debt[0]}, eff={max_debt[1]:.0%}, emb={max_debt[2]}")

# ─────────────────────────────────────────────────────────────────────────────
# FALSIFICATION VERDICT
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FALSIFICATION VERDICT")
print("=" * 70)

# Check 1: T* variation > 2 years
all_t_spans = []
for eff in EFFICIENCY_GAINS:
    for emb in EMBODIED_CARBONS:
        t_stars = [results[(eff, emb)][ci][0] for ci in CI_VALUES]
        all_t_spans.append(max(t_stars) - min(t_stars))

max_t_span = max(all_t_spans)
check1 = max_t_span > 2
print(f"CHECK 1 — T* varies >2 years across CI range: "
      f"{'✅ PASS' if check1 else '❌ FAIL'} (max span = {max_t_span} yrs)")

# Check 2: Industry norm (5yr) wrong by >20% carbon for any CI regime
check2 = max_excess_pct > 20.0
print(f"CHECK 2 — Industry norm >20% excess carbon for some regime: "
      f"{'✅ PASS' if check2 else '❌ FAIL'} (max = {max_excess_pct:.1f}%)")

# Check 3: PIVOT condition — T* always 4–6 yrs regardless of CI
always_narrow = all(
    4 <= results[(eff, emb)][ci][0] <= 6
    for eff in EFFICIENCY_GAINS
    for emb in EMBODIED_CARBONS
    for ci in CI_VALUES
)
check3_pivot = always_narrow
print(f"CHECK 3 — PIVOT condition (T* always 4–6 yrs): "
      f"{'⚠️  YES' if check3_pivot else '✅ NO (interesting variation)'}")

if check1 and check2 and not check3_pivot:
    verdict = "✅ INTERESTING — PROCEED TO FULL SIMULATION"
elif check3_pivot:
    verdict = "⚠️  PIVOT — T* shows no interesting variation"
elif check1 or check2:
    verdict = "✅ BORDERLINE INTERESTING — worth proceeding"
else:
    verdict = "❌ NULL RESULT — pivot direction"

print(f"\nFINAL VERDICT: {verdict}")

# ─────────────────────────────────────────────────────────────────────────────
# Figures
# ─────────────────────────────────────────────────────────────────────────────
os.makedirs("figures", exist_ok=True)

# Figure A: T* vs CI for each efficiency gain (embodied=1000 kgCO2)
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
fig.suptitle("Optimal Server Lifetime T* vs Grid Carbon Intensity\n"
             "(Embodied = 1000 kgCO₂, Horizon = 15 yr)", fontsize=13)

colors = ['#e74c3c', '#2980b9', '#27ae60']
for ax, eff, color in zip(axes, EFFICIENCY_GAINS, colors):
    t_stars = [results[(eff, 1000)][ci][0] for ci in CI_VALUES]
    ax.step(CI_VALUES, t_stars, where='mid', color=color, linewidth=2.5,
            label=f"eff={eff:.0%}/yr")
    ax.axhline(INDUSTRY_NORM, color='gray', linestyle='--', linewidth=1.5,
               label='Industry norm (5 yr)')
    ax.axhline(AI_CYCLE, color='orange', linestyle=':', linewidth=1.5,
               label='AI cycle (2 yr)')
    ax.set_xlabel("Grid CI (gCO₂/kWh)", fontsize=11)
    ax.set_title(f"Efficiency gain = {eff:.0%}/yr", fontsize=11)
    ax.set_xlim(50, 800)
    ax.set_ylim(0, 16)
    ax.set_yticks(range(1, 16))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

axes[0].set_ylabel("Optimal Lifetime T* (years)", fontsize=11)
plt.tight_layout()
plt.savefig("figures/embodied_fig1_tstar_vs_ci.png", dpi=150, bbox_inches='tight')
plt.close()
print("\n[Figure] Saved figures/embodied_fig1_tstar_vs_ci.png")

# Figure B: T* vs CI for different embodied carbons (eff=0.15)
fig, ax = plt.subplots(figsize=(9, 5))
cmap = cm.get_cmap('RdYlGn_r', len(EMBODIED_CARBONS))
for i, emb in enumerate(EMBODIED_CARBONS):
    t_stars = [results[(0.15, emb)][ci][0] for ci in CI_VALUES]
    ax.step(CI_VALUES, t_stars, where='mid', color=cmap(i), linewidth=2.5,
            label=f"Embodied = {emb} kgCO₂")
ax.axhline(INDUSTRY_NORM, color='gray', linestyle='--', linewidth=1.5,
           label='Industry norm (5 yr)')
ax.axhline(AI_CYCLE, color='orange', linestyle=':', linewidth=1.5,
           label='AI GPU cycle (2 yr)')
ax.set_xlabel("Grid CI (gCO₂/kWh)", fontsize=12)
ax.set_ylabel("Optimal Lifetime T* (years)", fontsize=12)
ax.set_title("T* vs CI for Different Embodied Carbon Values\n"
             "(Efficiency gain = 15%/yr, Horizon = 15 yr)", fontsize=12)
ax.set_xlim(50, 800)
ax.set_ylim(0, 16)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("figures/embodied_fig2_tstar_vs_embodied.png", dpi=150, bbox_inches='tight')
plt.close()
print("[Figure] Saved figures/embodied_fig2_tstar_vs_embodied.png")

# Figure C: Carbon excess (%) of industry norm vs optimal — heatmap over CI × embodied
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("Industry Norm (5yr) Carbon Excess vs Optimal T* (%)\n"
             "Positive = 5yr wastes carbon; Negative = 5yr too conservative", fontsize=12)

for ax, eff in zip(axes, EFFICIENCY_GAINS):
    matrix = np.zeros((len(EMBODIED_CARBONS), len(CI_VALUES)))
    for i, emb in enumerate(EMBODIED_CARBONS):
        for j, ci in enumerate(CI_VALUES):
            T_star, c_opt = results[(eff, emb)][ci]
            c_5yr = compute_total_carbon(eff, emb, ci, INDUSTRY_NORM)
            matrix[i, j] = (c_5yr - c_opt) / c_opt * 100

    im = ax.imshow(matrix, aspect='auto', cmap='RdYlGn_r',
                   vmin=-5, vmax=max(50, matrix.max()),
                   extent=[CI_VALUES[0], CI_VALUES[-1],
                           -0.5, len(EMBODIED_CARBONS) - 0.5])
    ax.set_xlabel("Grid CI (gCO₂/kWh)", fontsize=10)
    ax.set_title(f"Eff={eff:.0%}/yr", fontsize=11)
    ax.set_yticks(range(len(EMBODIED_CARBONS)))
    ax.set_yticklabels([f"{e} kg" for e in EMBODIED_CARBONS])
    plt.colorbar(im, ax=ax, label="Carbon excess (%)")

plt.tight_layout()
plt.savefig("figures/embodied_fig3_industry_norm_error.png", dpi=150, bbox_inches='tight')
plt.close()
print("[Figure] Saved figures/embodied_fig3_industry_norm_error.png")

# Figure D: 2yr AI cycle carbon debt heatmap (eff=0.15)
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("AI-Driven 2yr GPU Refresh Carbon Debt vs Optimal T* (%)\n"
             "(Higher = more carbon wasted by 2yr cycle)", fontsize=12)
for ax, eff in zip(axes, EFFICIENCY_GAINS):
    matrix = np.zeros((len(EMBODIED_CARBONS), len(CI_VALUES)))
    for i, emb in enumerate(EMBODIED_CARBONS):
        for j, ci in enumerate(CI_VALUES):
            T_star, c_opt = results[(eff, emb)][ci]
            c_2yr = compute_total_carbon(eff, emb, ci, AI_CYCLE)
            matrix[i, j] = (c_2yr - c_opt) / c_opt * 100

    im = ax.imshow(matrix, aspect='auto', cmap='YlOrRd',
                   vmin=0, vmax=matrix.max(),
                   extent=[CI_VALUES[0], CI_VALUES[-1],
                           -0.5, len(EMBODIED_CARBONS) - 0.5])
    ax.set_xlabel("Grid CI (gCO₂/kWh)", fontsize=10)
    ax.set_title(f"Eff={eff:.0%}/yr", fontsize=11)
    ax.set_yticks(range(len(EMBODIED_CARBONS)))
    ax.set_yticklabels([f"{e} kg" for e in EMBODIED_CARBONS])
    plt.colorbar(im, ax=ax, label="2yr debt (%)")

plt.tight_layout()
plt.savefig("figures/embodied_fig4_ai_cycle_debt.png", dpi=150, bbox_inches='tight')
plt.close()
print("[Figure] Saved figures/embodied_fig4_ai_cycle_debt.png")

print("\n[DONE] falsification-embodied.py complete.")
