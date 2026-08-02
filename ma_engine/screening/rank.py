"""Combine strategic + financial fit into a ranked target shortlist.

    total_score = alpha*strategic_score + (1-alpha)*financial_score

Returns a DataFrame with every sub-score exposed, so the teaser can explain *why*
a target ranked where it did.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from ..config import Config, DEFAULT_CONFIG
from ..embeddings import Embedder
from ..models import Company
from . import financial_fit, strategic_fit


def rank_targets(acquirer: Company, universe: list[Company],
                 cfg: Config = DEFAULT_CONFIG,
                 embedder: Optional[Embedder] = None,
                 top_n: Optional[int] = None) -> pd.DataFrame:
    """Score and rank every universe company (except the acquirer) as a target."""
    candidates = [c for c in universe if c.ticker != acquirer.ticker]
    if not candidates:
        return pd.DataFrame()

    strat = {s.ticker: s for s in strategic_fit.score_candidates(acquirer, candidates, cfg, embedder)}
    fin = {s.ticker: s for s in financial_fit.score_candidates(acquirer, candidates, cfg)}

    alpha = cfg.strategic_vs_financial_alpha
    rows = []
    for c in candidates:
        s, f = strat[c.ticker], fin[c.ticker]
        total = alpha * s.strategic_score + (1 - alpha) * f.financial_score
        rows.append({
            "ticker": c.ticker,
            "name": c.name,
            "total_score": total,
            "strategic_score": s.strategic_score,
            "financial_score": f.financial_score,
            "adjacency": s.adjacency,
            "segment_fit": s.segment_fit,
            "digestibility": s.digestibility,
            "overlap": s.overlap,
            "complementarity": s.complementarity,
            "margin_accretion": f.margin_accretion,
            "fundability": f.fundability,
            "pro_forma_leverage": f.pro_forma_leverage,
            "target_ev": c.enterprise_value,
            "target_market_cap": c.market_cap,
        })

    df = pd.DataFrame(rows).sort_values("total_score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    if top_n is not None:
        return df.head(top_n).reset_index(drop=True)
    return df


def rationale_bullets(row: pd.Series) -> list[str]:
    """Auto-write 2-3 plain-English rationale bullets from the sub-scores."""
    bullets = []
    if row["adjacency"] >= 0.30:
        bullets.append(
            f"Strong business adjacency (similarity {row['adjacency']:.0%}) — closely related product space.")
    elif row["adjacency"] >= 0.12:
        bullets.append(
            f"Moderate adjacency (similarity {row['adjacency']:.0%}) — a plausible expansion, not a pure overlap.")
    if row["complementarity"] >= 0.5:
        bullets.append(
            f"Highly complementary product line — adds capabilities the acquirer largely lacks "
            f"(complementarity {row['complementarity']:.0%}).")
    elif row["overlap"] >= 0.34:
        bullets.append(
            f"Meaningful segment overlap ({row['overlap']:.0%}) — consolidation and cost-synergy potential.")
    if row["digestibility"] >= 0.9:
        bullets.append(
            f"Digestible size — target EV is {row['target_ev'] / max(row['target_market_cap'], 1):.0%}-scale "
            "and comfortably fundable.")
    elif row["digestibility"] <= 0.4:
        bullets.append("Size is a stretch — either too small to move the needle or hard to fund.")
    if row["margin_accretion"] >= 0.6:
        bullets.append("Margin-accretive — target runs higher EBITDA margins than the acquirer.")
    if row["fundability"] <= 0.35:
        bullets.append(
            f"Fundability is tight — 100%-debt pro forma leverage ~{row['pro_forma_leverage']:.1f}x.")
    return bullets[:3] if bullets else ["Balanced strategic and financial profile."]
