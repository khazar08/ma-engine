"""Precedent transaction multiples.

A curated table of comparable announced deals (``data/precedents.csv``) yields
implied deal multiples (EV/Revenue, EV/EBITDA). Median precedent multiples are
applied to the target. Because precedent multiples embed a control premium, the
resulting values typically sit ABOVE trading comps — the ``MethodRange`` is
flagged with ``includes_control_premium=True``.
"""
from __future__ import annotations

import os
import statistics
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ..config import Config, DEFAULT_CONFIG
from ..models import Company, MethodRange


@dataclass
class PrecedentResult:
    n_deals: int
    ev_revenue_multiples: list[float]
    ev_ebitda_multiples: list[float]
    median_ev_revenue: Optional[float]
    median_ev_ebitda: Optional[float]
    implied_ev_revenue: Optional[float]
    implied_ev_ebitda: Optional[float]


def load_precedents(cfg: Config = DEFAULT_CONFIG, sector: str = "enterprise_software") -> pd.DataFrame:
    from ..paths import resolve_data_file
    df = pd.read_csv(resolve_data_file(cfg.data_dir, "precedents.csv"))
    return df[df["sector"] == sector].copy()


def compute_precedents(target: Company, cfg: Config = DEFAULT_CONFIG,
                       df: Optional[pd.DataFrame] = None) -> PrecedentResult:
    if df is None:
        df = load_precedents(cfg, target.sector)

    ev_rev = [row.announced_ev / row.target_ltm_revenue
              for row in df.itertuples()
              if row.target_ltm_revenue and row.target_ltm_revenue > 0]
    ev_ebitda = [row.announced_ev / row.target_ltm_ebitda
                 for row in df.itertuples()
                 if row.target_ltm_ebitda and row.target_ltm_ebitda > 0]

    med_rev = statistics.median(ev_rev) if ev_rev else None
    med_ebitda = statistics.median(ev_ebitda) if ev_ebitda else None

    implied_rev = (med_rev * target.revenue - target.net_debt) if (med_rev and target.revenue > 0) else None
    implied_ebitda = (med_ebitda * target.ebitda - target.net_debt) if (med_ebitda and target.ebitda > 0) else None

    return PrecedentResult(
        n_deals=len(df),
        ev_revenue_multiples=ev_rev,
        ev_ebitda_multiples=ev_ebitda,
        median_ev_revenue=med_rev,
        median_ev_ebitda=med_ebitda,
        implied_ev_revenue=implied_rev,
        implied_ev_ebitda=implied_ebitda,
    )


def precedent_range(result: PrecedentResult) -> Optional[MethodRange]:
    vals = [v for v in (result.implied_ev_revenue, result.implied_ev_ebitda) if v is not None and v > 0]
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    return MethodRange(
        method="Precedent transactions",
        low_equity=lo,
        mid_equity=statistics.median(vals),
        high_equity=hi,
        includes_control_premium=True,
    )
