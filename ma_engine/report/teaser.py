"""One-page deal teaser (PDF).

Composed with matplotlib gridspec so it is fully self-contained (no native PDF
toolchain required) and the football field / sensitivity charts embed directly.
The layout mimics an MD-desk one-pager: header, strategic rationale, football
field, accretion/dilution summary + EPS bridge, sensitivity heatmap, recommended
structure line.
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.gridspec import GridSpec

from ..models import Company, DealAnalysis
from . import charts

INK = charts.INK
INK2 = charts.INK2
BLUE = charts.BLUE
RED = charts.RED


def _fmt_m(x: float) -> str:
    """Format millions with a $ and thousands separators; scale to $bn if large."""
    if x == 0 or abs(x) < 0.5:
        return "$0m"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1000:
        return f"{sign}${x/1000:,.1f}bn"
    return f"{sign}${x:,.0f}m"


def render_teaser(analysis: DealAnalysis, acquirer: Company, target: Company,
                  out_dir: str = "out") -> str:
    os.makedirs(out_dir, exist_ok=True)
    s = analysis.structure
    acc = analysis.accretion
    syn = analysis.synergies
    val = analysis.valuation
    scores = analysis.screening_scores

    fig = plt.figure(figsize=(8.5, 11))  # US Letter portrait
    fig.patch.set_facecolor(charts.SURFACE)
    gs = GridSpec(6, 2, figure=fig, height_ratios=[0.7, 0.9, 2.2, 1.5, 2.4, 0.5],
                  hspace=0.6, wspace=0.28, left=0.12, right=0.95, top=0.95, bottom=0.04)

    # --- Header ---
    ax_h = fig.add_subplot(gs[0, :]); ax_h.axis("off")
    ax_h.text(0, 0.75, f"{acquirer.name}  →  {target.name}", fontsize=16,
              fontweight="bold", color=INK, transform=ax_h.transAxes)
    verdict = "ACCRETIVE" if acc.is_accretive else "DILUTIVE"
    vcolor = charts.GREEN if acc.is_accretive else RED
    ax_h.text(0, 0.30,
              f"Offer ${s.offer_price_per_share:,.2f}/sh  ·  {s.premium:.0%} premium  ·  "
              f"{s.cash_pct:.0%} cash / {s.stock_pct:.0%} stock / {s.new_debt_pct:.0%} new debt",
              fontsize=9.5, color=INK2, transform=ax_h.transAxes)
    ax_h.text(1.0, 0.72, f"{acc.accretion_dilution_pct:+.1%}", fontsize=20, fontweight="bold",
              color=vcolor, ha="right", transform=ax_h.transAxes)
    ax_h.text(1.0, 0.34, f"Year-1 EPS {verdict}", fontsize=9, color=vcolor, ha="right",
              transform=ax_h.transAxes)

    # --- Strategic rationale ---
    ax_r = fig.add_subplot(gs[1, :]); ax_r.axis("off")
    ax_r.text(0, 1.0, "Strategic rationale", fontsize=11, fontweight="bold", color=INK,
              transform=ax_r.transAxes, va="top")
    bullets = scores.get("rationale", ["Balanced strategic and financial profile."])
    for i, b in enumerate(bullets[:3]):
        ax_r.text(0.01, 0.68 - i * 0.30, f"•  {b}", fontsize=8.6, color=INK2,
                  transform=ax_r.transAxes, va="top", wrap=True)

    # --- Football field ---
    ax_ff = fig.add_subplot(gs[2, :])
    charts.football_field(val, offer_price_per_share=s.offer_price_per_share, ax=ax_ff,
                          title="Valuation — football field (implied $/share)")

    # --- Accretion / dilution summary + EPS bridge ---
    ax_b = fig.add_subplot(gs[3, 0]); ax_b.axis("off")
    ax_b.text(0, 1.0, "Pro forma EPS bridge", fontsize=11, fontweight="bold", color=INK,
              transform=ax_b.transAxes, va="top")
    bridge = [
        ("Acquirer net income", _fmt_m(acc.acquirer_net_income)),
        ("+ Target net income", _fmt_m(acc.target_net_income)),
        ("+ After-tax synergies", _fmt_m(acc.after_tax_synergies)),
        ("− After-tax new interest", _fmt_m(-acc.after_tax_new_interest)),
        ("− After-tax foregone interest", _fmt_m(-acc.after_tax_foregone_interest)),
        ("= Pro forma net income", _fmt_m(acc.pro_forma_net_income)),
        ("Standalone EPS", f"${acc.acquirer_standalone_eps:,.2f}"),
        ("Pro forma EPS", f"${acc.pro_forma_eps:,.2f}"),
    ]
    for i, (label, value) in enumerate(bridge):
        yb = 0.80 - i * 0.105
        weight = "bold" if label.startswith("=") or "EPS" in label else "normal"
        ax_b.text(0.0, yb, label, fontsize=8.2, color=INK2, transform=ax_b.transAxes, fontweight=weight)
        ax_b.text(1.0, yb, value, fontsize=8.2, color=INK, transform=ax_b.transAxes,
                  ha="right", fontweight=weight)

    ax_d = fig.add_subplot(gs[3, 1]); ax_d.axis("off")
    ax_d.text(0, 1.0, "Deal diagnostics", fontsize=11, fontweight="bold", color=INK,
              transform=ax_d.transAxes, va="top")
    be = acc.breakeven_premium
    diag = [
        ("Enterprise purchase price", _fmt_m(s.enterprise_purchase_price)),
        ("Equity purchase price", _fmt_m(s.equity_purchase_price)),
        ("Transaction fees", _fmt_m(s.transaction_fees)),
        ("New shares issued (m)", f"{s.new_shares_issued:,.1f}"),
        ("Run-rate synergies (a-t)", _fmt_m(syn.after_tax_run_rate)),
        ("Breakeven premium", f"{be:.1%}" if be is not None else "n/a (accretive in range)"),
        ("Synergies to neutral (a-t)", _fmt_m(acc.synergies_to_neutral or 0.0)),
    ]
    for i, (label, value) in enumerate(diag):
        yb = 0.80 - i * 0.12
        ax_d.text(0.0, yb, label, fontsize=8.2, color=INK2, transform=ax_d.transAxes)
        ax_d.text(1.0, yb, value, fontsize=8.2, color=INK, transform=ax_d.transAxes, ha="right")

    # --- Sensitivity heatmap ---
    ax_s = fig.add_subplot(gs[4, :])
    grid = pd.DataFrame(analysis.sensitivity["values"],
                        index=analysis.sensitivity["premiums"],
                        columns=analysis.sensitivity["realizations"])
    charts.sensitivity_heatmap(grid, ax=ax_s,
                               title="Sensitivity — EPS accretion/(dilution): premium × synergy realization")

    # --- Recommended structure footer ---
    ax_f = fig.add_subplot(gs[5, :]); ax_f.axis("off")
    if be is not None and be >= 0:
        be_txt = f"; breakeven {be:.0%} premium."
    elif be is not None and be < 0:
        be_txt = "."
    else:
        be_txt = "; accretive across feasible premiums."
    rec = (f"Recommended: {s.cash_pct:.0%} cash / {s.stock_pct:.0%} stock / "
           f"{s.new_debt_pct:.0%} debt at {s.premium:.0%} premium — "
           f"{'accretive' if acc.is_accretive else 'dilutive'} to Yr-1 EPS by "
           f"{abs(acc.accretion_dilution_pct):.1%}" + be_txt)
    ax_f.text(0, 0.75, rec, fontsize=8.2, color=INK, transform=ax_f.transAxes, va="center",
              style="italic")
    ax_f.text(0, 0.15, "Preliminary · auto-generated · not investment advice",
              fontsize=6.5, color=INK2, transform=ax_f.transAxes, va="center", ha="left")

    out_path = os.path.join(out_dir, f"teaser_{analysis.acquirer}_{analysis.target}.pdf")
    fig.savefig(out_path, format="pdf", facecolor=charts.SURFACE)
    png_path = out_path.replace(".pdf", ".png")
    fig.savefig(png_path, format="png", dpi=130, facecolor=charts.SURFACE)
    plt.close(fig)
    return out_path
