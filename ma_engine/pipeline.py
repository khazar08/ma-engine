"""Orchestration: acquirer -> shortlist -> per-target full deal analysis.

Ties the phases together into ``DealAnalysis`` objects and (optionally) teaser
PDFs. Kept separate from the CLI so it is importable and testable.
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .deal import accretion_dilution as ad
from .deal import synergies as syn_mod
from .deal.sensitivity import sensitivity_grid
from .embeddings import Embedder, get_embedder
from .models import Company, DealAnalysis
from .screening import rank as rank_mod
from .valuation import football_field


def analyze_target(acquirer: Company, target: Company, universe: list[Company],
                   screening_row: Optional[pd.Series] = None,
                   cfg: Config = DEFAULT_CONFIG,
                   embedder: Optional[Embedder] = None,
                   premium: float | None = None,
                   cash_pct: float | None = None,
                   stock_pct: float | None = None,
                   new_debt_pct: float | None = None) -> DealAnalysis:
    """Full first-pass analysis for a single acquirer/target pair."""
    premium = cfg.default_premium if premium is None else premium

    # 1. Valuation
    valuation = football_field.build_valuation(target, universe, cfg, embedder=embedder)

    # 2. Synergies (scaled by strategic overlap from screening, if available)
    overlap = float(screening_row["overlap"]) if screening_row is not None else 0.5
    synergies = syn_mod.estimate_synergies(acquirer, target, overlap_score=overlap, cfg=cfg)

    # 3. Structure + accretion/dilution (use Year-1 phased synergies for the headline)
    y1_synergies = syn_mod.phased_after_tax(synergies, 1)
    structure, accretion = ad.analyze_deal(
        acquirer, target, after_tax_synergies=y1_synergies, premium=premium,
        cash_pct=cash_pct, stock_pct=stock_pct, new_debt_pct=new_debt_pct, cfg=cfg)

    # 4. Sensitivity grid (uses full run-rate synergies scaled by realization)
    grid = sensitivity_grid(acquirer, target, base_after_tax_synergies=synergies.after_tax_run_rate,
                            cash_pct=cash_pct, stock_pct=stock_pct, new_debt_pct=new_debt_pct, cfg=cfg)
    sensitivity = {
        "premiums": list(grid.index),
        "realizations": list(grid.columns),
        "values": grid.values.tolist(),
    }

    # 5. Screening scores + rationale for the teaser
    screening_scores: dict = {}
    if screening_row is not None:
        screening_scores = {k: (float(v) if isinstance(v, (int, float)) else v)
                            for k, v in screening_row.to_dict().items()}
        screening_scores["rationale"] = rank_mod.rationale_bullets(screening_row)

    return DealAnalysis(
        acquirer=acquirer.ticker, target=target.ticker,
        valuation=valuation, synergies=synergies, structure=structure,
        accretion=accretion, sensitivity=sensitivity, screening_scores=screening_scores,
    )


def run_engine(acquirer_ticker: str, universe: list[Company],
               cfg: Config = DEFAULT_CONFIG, top_n: int | None = None,
               premium: float | None = None,
               cash_pct: float | None = None, stock_pct: float | None = None,
               new_debt_pct: float | None = None,
               make_teasers: bool = True,
               embedder: Optional[Embedder] = None) -> tuple[pd.DataFrame, list[DealAnalysis]]:
    """Screen, analyze the shortlist, and (optionally) emit teaser PDFs.

    Returns (shortlist_df, [DealAnalysis...]).
    """
    from .data import fundamentals

    top_n = top_n if top_n is not None else cfg.top_n
    acquirer = fundamentals.get_company(universe, acquirer_ticker)
    embedder = embedder or get_embedder()

    shortlist = rank_mod.rank_targets(acquirer, universe, cfg, embedder=embedder, top_n=top_n)

    analyses: list[DealAnalysis] = []
    for _, row in shortlist.iterrows():
        target = fundamentals.get_company(universe, row["ticker"])
        analysis = analyze_target(acquirer, target, universe, screening_row=row, cfg=cfg,
                                  embedder=embedder, premium=premium, cash_pct=cash_pct,
                                  stock_pct=stock_pct, new_debt_pct=new_debt_pct)
        analyses.append(analysis)

    if make_teasers:
        from .report.teaser import render_teaser
        for analysis in analyses:
            target = fundamentals.get_company(universe, analysis.target)
            render_teaser(analysis, acquirer, target, out_dir=cfg.out_dir)

    return shortlist, analyses


def summary_frame(shortlist: pd.DataFrame, analyses: list[DealAnalysis]) -> pd.DataFrame:
    """Compact index: ranked targets + headline accretion + offer terms."""
    acc_by_t = {a.target: a for a in analyses}
    rows = []
    for _, r in shortlist.iterrows():
        a = acc_by_t.get(r["ticker"])
        if a is None:
            continue
        rows.append({
            "rank": int(r["rank"]),
            "ticker": r["ticker"],
            "name": r["name"],
            "total_score": round(float(r["total_score"]), 3),
            "offer_per_share": round(a.structure.offer_price_per_share, 2),
            "premium": a.structure.premium,
            "equity_purchase_$m": round(a.structure.equity_purchase_price, 0),
            "yr1_accretion": round(a.accretion.accretion_dilution_pct, 4),
            "breakeven_premium": (round(a.accretion.breakeven_premium, 4)
                                  if a.accretion.breakeven_premium is not None else None),
        })
    return pd.DataFrame(rows)
