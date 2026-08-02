"""Phase 7 — validation harness.

Two checks that turn the project from "toy" into "defensible":

1. ``backtest_screener`` — hit-rate@K. For each held-out (acquirer, target) pair,
   run the screener for the acquirer and record whether the actual target appears
   in the engine's top-K shortlist. Reports hit-rate@5/10/20.

2. ``calibrate_precedent_multiples`` — for each real precedent deal, compare the
   engine's median precedent EV/EBITDA (the multiple it would apply) against the
   deal's own realized multiple, so the valuation multiples are shown to be in a
   sane range.

CAVEAT (documented): the shipped holdout uses strategically-motivated pairs among
*current* public universe members, and screening uses current fundamentals. This
is NOT a leak-free point-in-time backtest — historical targets are delisted post-
close and not in a current universe. The harness is generic: drop in a point-in-
time universe + a real announced-deal holdout (stretch goal) and the same
hit-rate@K numbers become fully out-of-sample.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .data import fundamentals
from .embeddings import Embedder, get_embedder
from .models import Company
from .screening import rank as rank_mod
from .valuation import precedents as prec_mod


@dataclass
class BacktestResult:
    n_deals: int
    ranks: list[tuple[str, str, Optional[int]]]  # (acquirer, target, rank or None)
    hit_rate: dict[int, float] = field(default_factory=dict)

    def summary_line(self) -> str:
        parts = [f"top-{k}: {v:.0%}" for k, v in sorted(self.hit_rate.items())]
        best_k = min(self.hit_rate) if self.hit_rate else 10
        return (f"Across {self.n_deals} held-out deals the screen surfaced the real "
                f"target in its {' / '.join(parts)}.")


def load_holdout(cfg: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    path = os.path.join(cfg.data_dir, "holdout_deals.csv")
    return pd.read_csv(path)


def backtest_screener(universe: list[Company], holdout: Optional[pd.DataFrame] = None,
                      cfg: Config = DEFAULT_CONFIG, ks: tuple[int, ...] = (5, 10, 20),
                      embedder: Optional[Embedder] = None) -> BacktestResult:
    if holdout is None:
        holdout = load_holdout(cfg)
    embedder = embedder or get_embedder()
    tickers = {c.ticker for c in universe}

    ranks: list[tuple[str, str, Optional[int]]] = []
    for row in holdout.itertuples():
        acq_t, tgt_t = row.acquirer_ticker, row.target_ticker
        if acq_t not in tickers or tgt_t not in tickers:
            continue
        acquirer = fundamentals.get_company(universe, acq_t)
        ranked = rank_mod.rank_targets(acquirer, universe, cfg, embedder=embedder)
        match = ranked[ranked["ticker"] == tgt_t]
        rank = int(match["rank"].iloc[0]) if not match.empty else None
        ranks.append((acq_t, tgt_t, rank))

    n = len(ranks)
    hit_rate = {}
    for k in ks:
        hits = sum(1 for _, _, r in ranks if r is not None and r <= k)
        hit_rate[k] = (hits / n) if n else 0.0
    return BacktestResult(n_deals=n, ranks=ranks, hit_rate=hit_rate)


@dataclass
class MultipleCalibration:
    engine_median_ev_ebitda: Optional[float]
    engine_median_ev_revenue: Optional[float]
    deal_ev_ebitda: list[float]
    deal_ev_revenue: list[float]


def calibrate_precedent_multiples(cfg: Config = DEFAULT_CONFIG,
                                  sector: str = "enterprise_software") -> MultipleCalibration:
    df = prec_mod.load_precedents(cfg, sector)
    ev_ebitda = [r.announced_ev / r.target_ltm_ebitda for r in df.itertuples()
                 if r.target_ltm_ebitda and r.target_ltm_ebitda > 0]
    ev_rev = [r.announced_ev / r.target_ltm_revenue for r in df.itertuples()
              if r.target_ltm_revenue and r.target_ltm_revenue > 0]
    import statistics
    return MultipleCalibration(
        engine_median_ev_ebitda=statistics.median(ev_ebitda) if ev_ebitda else None,
        engine_median_ev_revenue=statistics.median(ev_rev) if ev_rev else None,
        deal_ev_ebitda=ev_ebitda,
        deal_ev_revenue=ev_rev,
    )


def run_validation(universe: Optional[list[Company]] = None,
                   cfg: Config = DEFAULT_CONFIG) -> BacktestResult:
    if universe is None:
        universe = fundamentals.load_universe_fundamentals(cfg)
    result = backtest_screener(universe, cfg=cfg)
    calib = calibrate_precedent_multiples(cfg)

    print("=== Screener backtest (hit-rate@K) ===")
    print(result.summary_line())
    print("\nPer-deal target ranks:")
    for acq, tgt, rank in result.ranks:
        pos = f"#{rank}" if rank is not None else "unranked"
        print(f"  {acq:<5} -> {tgt:<5}  actual target ranked {pos}")

    print("\n=== Precedent-multiple calibration ===")
    if calib.engine_median_ev_ebitda is not None:
        print(f"  Engine median precedent EV/EBITDA: {calib.engine_median_ev_ebitda:.1f}x "
              f"(deal range {min(calib.deal_ev_ebitda):.1f}x–{max(calib.deal_ev_ebitda):.1f}x)")
    print(f"  Engine median precedent EV/Revenue: {calib.engine_median_ev_revenue:.1f}x "
          f"(deal range {min(calib.deal_ev_revenue):.1f}x–{max(calib.deal_ev_revenue):.1f}x)")
    return result


if __name__ == "__main__":
    run_validation()
