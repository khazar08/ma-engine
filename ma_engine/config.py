"""Centralized configuration for the M&A engine.

Every financial assumption lives here so that nothing is hardcoded inside the
logic modules. Values are typed via pydantic and can be overridden at runtime.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScreeningWeights(BaseModel):
    """Weights for the strategic-fit sub-scores (should sum to ~1.0)."""

    adjacency: float = 0.45
    segment_fit: float = 0.30
    digestibility: float = 0.25

    # complementarity vs pure-overlap weighting inside segment_fit (0 = pure
    # overlap, 1 = pure complementarity reward)
    complementarity_weight: float = 0.35

    # digestibility "sweet spot" band as fraction of acquirer market cap
    digestible_low: float = 0.05
    digestible_high: float = 0.40


class Config(BaseModel):
    """Global engine configuration."""

    # --- SEC / data ---
    sec_user_agent: str = "ma-engine research khazar.myp@gmail.com"
    cache_dir: str = "cache"
    data_dir: str = "data"
    out_dir: str = "out"

    # --- DCF / WACC ---
    risk_free_rate: float = 0.043          # current ~10Y Treasury (as of 2026-07, hardcoded)
    equity_risk_premium: float = 0.050     # ERP
    credit_spread: float = 0.020           # over risk-free for cost of debt
    terminal_growth: float = 0.025         # Gordon growth g
    projection_years: int = 5
    tax_rate_default: float = 0.21         # US statutory fallback

    # --- DCF projection drivers (defaults; can be overridden per-target) ---
    revenue_growth_start: float = 0.12     # year-1 revenue growth
    revenue_growth_terminal: float = 0.03  # faded terminal growth
    ebit_margin_target: float | None = None  # None -> use company's current margin
    da_pct_revenue: float | None = None      # None -> use current ratio
    capex_pct_revenue: float | None = None   # None -> use current ratio
    nwc_pct_revenue_change: float = 0.10     # ΔNWC as % of the change in revenue

    # --- Deal defaults ---
    default_premium: float = 0.30
    # consideration mix (must sum to 1.0)
    cash_pct: float = 0.50
    stock_pct: float = 0.50
    new_debt_pct: float = 0.00
    refinance_target_debt: bool = False
    fee_pct: float = 0.02                   # transaction fees as % of equity purchase price
    interest_rate_new_debt: float = 0.063   # rf + credit_spread by default
    foregone_yield_on_cash: float = 0.045   # opportunity yield on cash used

    # --- Synergies ---
    cost_synergy_pct_low: float = 0.05      # % of target opex at low overlap
    cost_synergy_pct_high: float = 0.15     # % of target opex at high overlap
    revenue_synergy_pct: float = 0.0        # optional, lower-confidence
    synergy_phase_in: list[float] = Field(default_factory=lambda: [0.5, 1.0])  # Y1, Y2+

    # --- Screening ---
    leverage_ceiling: float = 4.0           # pro forma net leverage threshold (x EBITDA)
    screening_weights: ScreeningWeights = Field(default_factory=ScreeningWeights)
    strategic_vs_financial_alpha: float = 0.6  # alpha in total = alpha*strat + (1-alpha)*fin
    top_n: int = 5

    def with_updates(self, **kwargs) -> "Config":
        return self.model_copy(update=kwargs)


DEFAULT_CONFIG = Config()
