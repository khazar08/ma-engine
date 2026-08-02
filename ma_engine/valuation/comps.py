"""Trading comparables with automatic peer selection.

Peers are the nearest neighbours to the target by business-description embedding
similarity, restricted to the same sector and a size band. Median peer multiples
(EV/Revenue, EV/EBITDA, P/E) are applied to the target's own metric to imply a
standalone equity value range.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from ..embeddings import Embedder, get_embedder
from ..models import Company, MethodRange


@dataclass
class CompsResult:
    peers: list[str]
    ev_revenue_multiples: list[float]
    ev_ebitda_multiples: list[float]
    pe_multiples: list[float]
    median_ev_revenue: Optional[float]
    median_ev_ebitda: Optional[float]
    median_pe: Optional[float]
    implied_equity_by_method: dict = field(default_factory=dict)


def select_peers(target: Company, universe: list[Company],
                 embedder: Optional[Embedder] = None,
                 n: int = 8, size_band: float = 8.0) -> list[Company]:
    """Nearest neighbours by embedding similarity, same sector, size within a band.

    ``size_band`` is a multiplicative EV band (target EV / band .. target EV * band).
    """
    candidates = [c for c in universe
                  if c.ticker != target.ticker
                  and c.sector == target.sector]
    # size filter (skip if target EV is non-positive)
    if target.enterprise_value > 0:
        lo, hi = target.enterprise_value / size_band, target.enterprise_value * size_band
        sized = [c for c in candidates if lo <= max(c.enterprise_value, 1e-9) <= hi]
        if len(sized) >= 5:
            candidates = sized

    if not candidates:
        return []

    embedder = embedder or get_embedder()
    texts = [target.business_description] + [c.business_description for c in candidates]
    sim = embedder.similarity_matrix(texts)[0, 1:]  # target vs each candidate
    ranked = sorted(zip(candidates, sim), key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked[:n]]


def _median_positive(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None and v > 0]
    return statistics.median(vals) if vals else None


def compute_comps(target: Company, universe: list[Company],
                  embedder: Optional[Embedder] = None,
                  n_peers: int = 8) -> CompsResult:
    peers = select_peers(target, universe, embedder=embedder, n=n_peers)

    ev_rev, ev_ebitda, pe = [], [], []
    for p in peers:
        if p.revenue > 0:
            ev_rev.append(p.enterprise_value / p.revenue)
        if p.ebitda > 0:
            ev_ebitda.append(p.enterprise_value / p.ebitda)
        if p.eps > 0:
            pe.append(p.share_price / p.eps)

    med_ev_rev = _median_positive(ev_rev)
    med_ev_ebitda = _median_positive(ev_ebitda)
    med_pe = _median_positive(pe)

    implied = {}
    if med_ev_rev is not None and target.revenue > 0:
        implied["EV/Revenue"] = med_ev_rev * target.revenue - target.net_debt
    if med_ev_ebitda is not None and target.ebitda > 0:
        implied["EV/EBITDA"] = med_ev_ebitda * target.ebitda - target.net_debt
    if med_pe is not None and target.net_income > 0:
        implied["P/E"] = med_pe * target.net_income  # equity value directly

    return CompsResult(
        peers=[p.ticker for p in peers],
        ev_revenue_multiples=ev_rev,
        ev_ebitda_multiples=ev_ebitda,
        pe_multiples=pe,
        median_ev_revenue=med_ev_rev,
        median_ev_ebitda=med_ev_ebitda,
        median_pe=med_pe,
        implied_equity_by_method=implied,
    )


def comps_range(result: CompsResult) -> Optional[MethodRange]:
    """Collapse the per-method implied equity values into a min/median/max range."""
    vals = [v for v in result.implied_equity_by_method.values() if v is not None]
    vals = [v for v in vals if v > 0]
    if not vals:
        return None
    return MethodRange(
        method="Trading comps",
        low_equity=min(vals),
        mid_equity=statistics.median(vals),
        high_equity=max(vals),
        includes_control_premium=False,
    )
