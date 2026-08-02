"""Pydantic data models for the M&A engine.

All monetary values are in millions USD unless otherwise noted. Share counts are
in millions of shares; per-share values are in USD.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Segment(BaseModel):
    name: str
    revenue: float = 0.0  # millions USD


class Company(BaseModel):
    ticker: str
    cik: str = ""
    name: str = ""
    sector: str = ""
    business_description: str = ""
    segments: list[Segment] = Field(default_factory=list)

    # Income statement (millions USD)
    revenue: float = 0.0
    ebitda: float = 0.0
    ebit: float = 0.0
    net_income: float = 0.0
    tax_rate: float = 0.21           # effective; fall back to 21% statutory
    interest_expense: float = 0.0

    # Balance sheet
    total_debt: float = 0.0
    cash_and_equivalents: float = 0.0

    # Cash flow
    capex: float = 0.0
    depreciation_amortization: float = 0.0
    change_in_nwc: float = 0.0

    # Market
    share_price: float = 0.0         # USD
    shares_diluted: float = 0.0      # millions of shares
    beta: float = 1.0

    # ----- Derived -----
    @property
    def market_cap(self) -> float:
        return self.share_price * self.shares_diluted

    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash_and_equivalents

    @property
    def enterprise_value(self) -> float:
        return self.market_cap + self.net_debt

    @property
    def ebitda_margin(self) -> float:
        return self.ebitda / self.revenue if self.revenue else 0.0

    @property
    def ebit_margin(self) -> float:
        return self.ebit / self.revenue if self.revenue else 0.0

    @property
    def eps(self) -> float:
        return self.net_income / self.shares_diluted if self.shares_diluted else 0.0

    @property
    def pe(self) -> float:
        return self.share_price / self.eps if self.eps else float("nan")

    @property
    def segment_names(self) -> set[str]:
        return {s.name.strip().lower() for s in self.segments if s.name.strip()}


class MethodRange(BaseModel):
    """Implied value range from a single valuation method."""

    method: str
    low_equity: float           # implied equity value (millions)
    mid_equity: float
    high_equity: float
    includes_control_premium: bool = False

    def per_share(self, shares: float) -> tuple[float, float, float]:
        if not shares:
            return (0.0, 0.0, 0.0)
        return (self.low_equity / shares, self.mid_equity / shares, self.high_equity / shares)


class Valuation(BaseModel):
    ticker: str
    shares_diluted: float
    net_debt: float
    methods: list[MethodRange] = Field(default_factory=list)
    # extra detail for DCF
    dcf_detail: dict = Field(default_factory=dict)
    peers_used: list[str] = Field(default_factory=list)

    def method(self, name: str) -> Optional[MethodRange]:
        for m in self.methods:
            if m.method == name:
                return m
        return None


class DealStructure(BaseModel):
    # Purchase price
    offer_price_per_share: float
    premium: float
    equity_purchase_price: float
    target_net_debt: float
    enterprise_purchase_price: float

    # Sources & uses (millions)
    transaction_fees: float
    refinanced_debt: float
    total_uses: float
    new_debt: float
    acquirer_cash_used: float
    new_equity_issued: float
    new_shares_issued: float

    # mix echoed back
    cash_pct: float
    stock_pct: float
    new_debt_pct: float


class AccretionResult(BaseModel):
    acquirer_standalone_eps: float
    pro_forma_eps: float
    accretion_dilution_pct: float           # positive = accretive

    pro_forma_net_income: float
    pro_forma_shares: float

    # bridge components (millions)
    acquirer_net_income: float
    target_net_income: float
    after_tax_synergies: float
    after_tax_new_interest: float
    after_tax_foregone_interest: float

    # diagnostics
    breakeven_premium: Optional[float] = None
    synergies_to_neutral: Optional[float] = None  # after-tax synergies for EPS-neutral

    @property
    def is_accretive(self) -> bool:
        return self.accretion_dilution_pct > 0


class SynergyEstimate(BaseModel):
    cost_synergies_pretax: float
    revenue_synergies_pretax: float
    total_pretax: float
    after_tax_run_rate: float
    phase_in: list[float]
    cost_synergy_pct_used: float


class DealAnalysis(BaseModel):
    acquirer: str
    target: str
    valuation: Valuation
    synergies: SynergyEstimate
    structure: DealStructure
    accretion: AccretionResult
    sensitivity: dict = Field(default_factory=dict)  # serialized grid
    screening_scores: dict = Field(default_factory=dict)
