"""Assemble the valuation range across methods into a single ``Valuation``.

Trading comps and DCF give *standalone* value; precedents give *acquisition*
value (they embed a control premium). The DCF contributes two bars — Gordon
growth and exit multiple — so the football field shows the full spread of
standalone value against where an offer would sit.
"""
from __future__ import annotations

from typing import Optional

from ..config import Config, DEFAULT_CONFIG
from ..embeddings import Embedder
from ..models import Company, MethodRange, Valuation
from . import comps as comps_mod
from . import dcf as dcf_mod
from . import precedents as prec_mod


def build_valuation(target: Company, universe: list[Company],
                    cfg: Config = DEFAULT_CONFIG,
                    embedder: Optional[Embedder] = None,
                    dcf_range_pct: float = 0.10) -> Valuation:
    """Run all three methods and assemble the football field.

    ``dcf_range_pct`` widens each DCF point estimate into a low/high band
    (±pct) so the DCF shows as a bar rather than a line.
    """
    methods: list[MethodRange] = []

    # --- Trading comps ---
    comps_res = comps_mod.compute_comps(target, universe, embedder=embedder)
    comps_mr = comps_mod.comps_range(comps_res)
    if comps_mr is not None:
        methods.append(comps_mr)

    # exit multiple for the DCF: median peer EV/EBITDA if available
    exit_multiple = comps_res.median_ev_ebitda

    # --- Precedent transactions ---
    prec_res = prec_mod.compute_precedents(target, cfg)
    prec_mr = prec_mod.precedent_range(prec_res)
    if prec_mr is not None:
        methods.append(prec_mr)

    # --- DCF ---
    dcf_detail: dict = {}
    try:
        dcf_res = dcf_mod.value_target(target, cfg, exit_ebitda_multiple=exit_multiple)
        if dcf_res.equity_gordon > 0:
            methods.append(MethodRange(
                method="DCF (Gordon)",
                low_equity=dcf_res.equity_gordon * (1 - dcf_range_pct),
                mid_equity=dcf_res.equity_gordon,
                high_equity=dcf_res.equity_gordon * (1 + dcf_range_pct),
            ))
        if dcf_res.equity_exit is not None and dcf_res.equity_exit > 0:
            methods.append(MethodRange(
                method="DCF (exit)",
                low_equity=dcf_res.equity_exit * (1 - dcf_range_pct),
                mid_equity=dcf_res.equity_exit,
                high_equity=dcf_res.equity_exit * (1 + dcf_range_pct),
            ))
        dcf_detail = {
            "wacc": dcf_res.wacc,
            "cost_of_equity": dcf_res.cost_of_equity,
            "cost_of_debt": dcf_res.cost_of_debt,
            "ev_gordon": dcf_res.ev_gordon,
            "ev_exit": dcf_res.ev_exit,
            "per_share_gordon": dcf_res.per_share_gordon,
            "per_share_exit": dcf_res.per_share_exit,
            "projections": dcf_res.projections,
        }
    except ValueError as e:
        dcf_detail = {"error": str(e)}

    return Valuation(
        ticker=target.ticker,
        shares_diluted=target.shares_diluted,
        net_debt=target.net_debt,
        methods=methods,
        dcf_detail=dcf_detail,
        peers_used=comps_res.peers,
    )
