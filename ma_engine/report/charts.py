"""Charts: the football field and the premium × synergy sensitivity heatmap.

Palette follows the validated design-system reference:
  * standalone-value methods (trading comps, DCF) -> blue  (#2a78d6)
  * acquisition-value method (precedents, embeds control premium) -> orange (#eb6834)
  * the offer price is a red reference line (#e34948)
The sensitivity grid uses a diverging green<->red map with a neutral-gray
midpoint pinned at 0% accretion; every cell is also numerically labelled so
identity never rests on color alone.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from ..models import Valuation

# --- design-system palette ---
BLUE = "#2a78d6"
ORANGE = "#eb6834"
RED = "#e34948"
GREEN = "#008300"
GRAY_MID = "#f0efec"
INK = "#0b0b0b"
INK2 = "#52514e"
SURFACE = "#fcfcfb"

# diverging colormap: red (dilutive) -> gray (neutral) -> green (accretive)
DIVERGING = LinearSegmentedColormap.from_list("acc_dil", [RED, GRAY_MID, GREEN])


def _style_ax(ax):
    ax.set_facecolor(SURFACE)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)


def football_field(valuation: Valuation, offer_price_per_share: float | None = None,
                   ax=None, title: str | None = None):
    """Horizontal per-method value ranges (per-share), with the offer as a red line."""
    own_ax = ax is None
    if own_ax:
        fig, ax = plt.subplots(figsize=(7.2, 3.4))
    _style_ax(ax)

    short = {
        "Trading comps": "Comps",
        "Precedent transactions": "Precedents",
        "DCF (Gordon)": "DCF · Gordon",
        "DCF (exit)": "DCF · exit",
    }
    shares = valuation.shares_diluted or 1.0
    methods = valuation.methods
    labels, lows, mids, highs, colors = [], [], [], [], []
    for m in methods:
        lo, mid, hi = m.per_share(shares)
        labels.append(short.get(m.method, m.method))
        lows.append(lo)
        mids.append(mid)
        highs.append(hi)
        colors.append(ORANGE if m.includes_control_premium else BLUE)

    y = np.arange(len(labels))
    for i in range(len(labels)):
        width = max(highs[i] - lows[i], 1e-6)
        ax.barh(y[i], width, left=lows[i], height=0.5, color=colors[i],
                alpha=0.85, edgecolor=SURFACE, linewidth=1.0, zorder=2)
        # midpoint tick + range label
        ax.plot([mids[i]], [y[i]], marker="|", color=INK, markersize=12, zorder=3)
        ax.text(highs[i], y[i], f"  ${lows[i]:.0f}–${highs[i]:.0f}",
                va="center", ha="left", fontsize=7.5, color=INK2)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel("Implied value per share (USD)", fontsize=8, color=INK2)

    # headroom on the right so the range labels drawn past each bar don't clip
    right_edge = max(highs + ([offer_price_per_share] if offer_price_per_share else []))
    ax.set_xlim(left=0, right=right_edge * 1.28)

    if offer_price_per_share:
        ax.axvline(offer_price_per_share, color=RED, linestyle="--", linewidth=1.6, zorder=4)
        y_bottom = ax.get_ylim()[0]  # inverted axis -> largest value is the bottom
        ax.text(offer_price_per_share, y_bottom, f" Offer ${offer_price_per_share:.0f}",
                color=RED, fontsize=7.5, va="top", ha="left")

    if title:
        ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
    if own_ax:
        fig.tight_layout()
        return fig, ax
    return ax


def sensitivity_heatmap(grid: pd.DataFrame, ax=None, title: str | None = None):
    """Diverging heatmap of accretion/dilution %, centered at 0."""
    own_ax = ax is None
    if own_ax:
        fig, ax = plt.subplots(figsize=(6.2, 3.6))

    values = grid.values * 100.0  # to percent
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    im = ax.imshow(values, cmap=DIVERGING, norm=norm, aspect="auto")

    ax.set_xticks(range(len(grid.columns)))
    ax.set_xticklabels([f"{c:.0%}" for c in grid.columns], fontsize=8, color=INK2)
    ax.set_yticks(range(len(grid.index)))
    ax.set_yticklabels([f"{p:.0%}" for p in grid.index], fontsize=8, color=INK2)
    ax.set_xlabel("Synergy realization", fontsize=8, color=INK2)
    ax.set_ylabel("Premium paid", fontsize=8, color=INK2)

    # numeric labels in every cell (identity not color-alone)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v = values[i, j]
            ax.text(j, i, f"{v:+.1f}%", ha="center", va="center", fontsize=7.5,
                    color=INK if abs(v) < 0.6 * vmax else "white")

    if title:
        ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
    if own_ax:
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Accretion / (Dilution) %")
        fig.tight_layout()
        return fig, ax
    return ax, im
