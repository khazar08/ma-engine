"""Unlevered free cash flow DCF.

Formulas are implemented exactly as specified in the build spec:

Unlevered FCF for projection year t:
    UFCF_t = EBIT_t * (1 - tax_rate) + D&A_t - CapEx_t - ΔNWC_t

WACC:
    Ke   = Rf + beta * ERP                 (CAPM)
    Kd   = Rf + credit_spread
    WACC = (E/V)*Ke + (D/V)*Kd*(1 - tax_rate)

Terminal value (both methods reported):
    Gordon:        TV = UFCF_N * (1 + g) / (WACC - g)
    Exit multiple: TV = EV/EBITDA_exit * EBITDA_N

Enterprise value:
    EV = Σ_{t=1..N} UFCF_t / (1+WACC)^t  +  TV / (1+WACC)^N
    Equity = EV - net_debt ; per-share = Equity / shares_diluted
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import Config, DEFAULT_CONFIG
from ..models import Company


@dataclass
class DCFAssumptions:
    revenue_growth_start: float
    revenue_growth_terminal: float
    ebit_margin: float
    da_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_revenue_change: float
    projection_years: int
    terminal_growth: float
    exit_ebitda_multiple: Optional[float]  # from comps; None -> skip exit method


@dataclass
class DCFResult:
    wacc: float
    cost_of_equity: float
    cost_of_debt: float
    ufcf: list[float]
    discount_factors: list[float]
    pv_ufcf: list[float]
    pv_explicit: float
    tv_gordon: float
    tv_exit: Optional[float]
    pv_tv_gordon: float
    pv_tv_exit: Optional[float]
    ev_gordon: float
    ev_exit: Optional[float]
    equity_gordon: float
    equity_exit: Optional[float]
    per_share_gordon: float
    per_share_exit: Optional[float]
    projections: list[dict] = field(default_factory=list)


def compute_wacc(company: Company, cfg: Config = DEFAULT_CONFIG,
                 tax_rate: Optional[float] = None) -> tuple[float, float, float]:
    """Return (wacc, cost_of_equity, cost_of_debt).

    E and D come from the target's market cap and total debt; V = E + D. If the
    company carries no debt or equity, weights degrade gracefully.
    """
    tax = tax_rate if tax_rate is not None else company.tax_rate
    ke = cfg.risk_free_rate + company.beta * cfg.equity_risk_premium
    kd = cfg.risk_free_rate + cfg.credit_spread

    e = max(company.market_cap, 0.0)
    d = max(company.total_debt, 0.0)
    v = e + d
    if v <= 0:
        return ke, ke, kd
    we, wd = e / v, d / v
    wacc = we * ke + wd * kd * (1 - tax)
    return wacc, ke, kd


def build_assumptions(company: Company, cfg: Config = DEFAULT_CONFIG,
                      exit_ebitda_multiple: Optional[float] = None) -> DCFAssumptions:
    """Derive projection drivers, defaulting to the company's current ratios."""
    rev = company.revenue or 1.0
    ebit_margin = cfg.ebit_margin_target if cfg.ebit_margin_target is not None else company.ebit_margin
    da_pct = cfg.da_pct_revenue if cfg.da_pct_revenue is not None else (company.depreciation_amortization / rev)
    capex_pct = cfg.capex_pct_revenue if cfg.capex_pct_revenue is not None else (company.capex / rev)
    return DCFAssumptions(
        revenue_growth_start=cfg.revenue_growth_start,
        revenue_growth_terminal=cfg.revenue_growth_terminal,
        ebit_margin=ebit_margin,
        da_pct_revenue=da_pct,
        capex_pct_revenue=capex_pct,
        nwc_pct_revenue_change=cfg.nwc_pct_revenue_change,
        projection_years=cfg.projection_years,
        terminal_growth=cfg.terminal_growth,
        exit_ebitda_multiple=exit_ebitda_multiple,
    )


def run_dcf(company: Company, assumptions: DCFAssumptions,
            cfg: Config = DEFAULT_CONFIG, wacc: Optional[float] = None) -> DCFResult:
    tax = company.tax_rate
    if wacc is None:
        wacc, ke, kd = compute_wacc(company, cfg, tax_rate=tax)
    else:
        _, ke, kd = compute_wacc(company, cfg, tax_rate=tax)

    n = assumptions.projection_years
    if assumptions.terminal_growth >= wacc:
        raise ValueError(
            f"Terminal growth g={assumptions.terminal_growth} must be < WACC={wacc:.4f}; "
            "Gordon-growth terminal value diverges."
        )

    # Linearly fade revenue growth from start -> terminal across the horizon.
    growths = []
    for t in range(1, n + 1):
        if n == 1:
            g = assumptions.revenue_growth_start
        else:
            frac = (t - 1) / (n - 1)
            g = assumptions.revenue_growth_start + frac * (
                assumptions.revenue_growth_terminal - assumptions.revenue_growth_start
            )
        growths.append(g)

    ufcf: list[float] = []
    projections: list[dict] = []
    prev_rev = company.revenue
    ebitda_n = 0.0
    for t in range(1, n + 1):
        rev_t = prev_rev * (1 + growths[t - 1])
        ebit_t = rev_t * assumptions.ebit_margin
        da_t = rev_t * assumptions.da_pct_revenue
        capex_t = rev_t * assumptions.capex_pct_revenue
        delta_rev = rev_t - prev_rev
        dnwc_t = delta_rev * assumptions.nwc_pct_revenue_change

        fcf = ebit_t * (1 - tax) + da_t - capex_t - dnwc_t
        ufcf.append(fcf)
        ebitda_n = ebit_t + da_t  # EBITDA in the terminal (final) year
        projections.append({
            "year": t, "revenue": rev_t, "growth": growths[t - 1], "ebit": ebit_t,
            "da": da_t, "capex": capex_t, "dnwc": dnwc_t, "ufcf": fcf, "ebitda": ebitda_n,
        })
        prev_rev = rev_t

    discount_factors = [1.0 / (1 + wacc) ** t for t in range(1, n + 1)]
    pv_ufcf = [f * df for f, df in zip(ufcf, discount_factors)]
    pv_explicit = sum(pv_ufcf)

    g = assumptions.terminal_growth
    tv_gordon = ufcf[-1] * (1 + g) / (wacc - g)
    df_n = discount_factors[-1]
    pv_tv_gordon = tv_gordon * df_n
    ev_gordon = pv_explicit + pv_tv_gordon
    equity_gordon = ev_gordon - company.net_debt
    per_share_gordon = equity_gordon / company.shares_diluted if company.shares_diluted else 0.0

    tv_exit = pv_tv_exit = ev_exit = equity_exit = per_share_exit = None
    if assumptions.exit_ebitda_multiple is not None:
        tv_exit = assumptions.exit_ebitda_multiple * ebitda_n
        pv_tv_exit = tv_exit * df_n
        ev_exit = pv_explicit + pv_tv_exit
        equity_exit = ev_exit - company.net_debt
        per_share_exit = equity_exit / company.shares_diluted if company.shares_diluted else 0.0

    return DCFResult(
        wacc=wacc, cost_of_equity=ke, cost_of_debt=kd,
        ufcf=ufcf, discount_factors=discount_factors, pv_ufcf=pv_ufcf,
        pv_explicit=pv_explicit,
        tv_gordon=tv_gordon, tv_exit=tv_exit,
        pv_tv_gordon=pv_tv_gordon, pv_tv_exit=pv_tv_exit,
        ev_gordon=ev_gordon, ev_exit=ev_exit,
        equity_gordon=equity_gordon, equity_exit=equity_exit,
        per_share_gordon=per_share_gordon, per_share_exit=per_share_exit,
        projections=projections,
    )


def value_target(company: Company, cfg: Config = DEFAULT_CONFIG,
                 exit_ebitda_multiple: Optional[float] = None) -> DCFResult:
    assumptions = build_assumptions(company, cfg, exit_ebitda_multiple)
    return run_dcf(company, assumptions, cfg)
