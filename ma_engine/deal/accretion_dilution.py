"""THE CORE — pro forma EPS accretion/dilution.

The pro forma EPS bridge, implemented exactly as specified:

    acquirer_standalone_EPS = acquirer_net_income / acquirer_shares_diluted

    after_tax_new_interest      = new_debt  * interest_rate_new_debt   * (1 - acq_tax_rate)
    after_tax_foregone_interest = cash_used * foregone_yield_on_cash   * (1 - acq_tax_rate)

    pro_forma_net_income = acquirer_NI + target_NI + after_tax_synergies
                           - after_tax_new_interest - after_tax_foregone_interest
    pro_forma_shares     = acquirer_shares_diluted + new_shares_issued
    pro_forma_EPS        = pro_forma_net_income / pro_forma_shares

    accretion_dilution_% = pro_forma_EPS / acquirer_standalone_EPS - 1
    # positive = accretive, negative = dilutive

Also solves for the breakeven premium (accretion == 0, structure held to the same
mix) and the after-tax synergies required for an EPS-neutral deal at a given
premium.
"""
from __future__ import annotations

from typing import Optional

from ..config import Config, DEFAULT_CONFIG
from ..models import AccretionResult, Company, DealStructure
from .structure import build_structure


def compute_accretion(acquirer: Company, target: Company,
                      structure: DealStructure,
                      after_tax_synergies: float = 0.0,
                      cfg: Config = DEFAULT_CONFIG,
                      solve_diagnostics: bool = True,
                      cash_pct: float | None = None,
                      stock_pct: float | None = None,
                      new_debt_pct: float | None = None) -> AccretionResult:
    """Compute pro forma EPS accretion/dilution for a fully-specified structure.

    ``after_tax_synergies`` is the after-tax synergy dollar amount to fold in
    (use the phased or run-rate figure from ``synergies``).
    """
    tax = acquirer.tax_rate

    after_tax_new_interest = structure.new_debt * cfg.interest_rate_new_debt * (1 - tax)
    after_tax_foregone_interest = structure.acquirer_cash_used * cfg.foregone_yield_on_cash * (1 - tax)

    standalone_eps = acquirer.eps

    pro_forma_ni = (acquirer.net_income + target.net_income + after_tax_synergies
                    - after_tax_new_interest - after_tax_foregone_interest)
    pro_forma_shares = acquirer.shares_diluted + structure.new_shares_issued
    pro_forma_eps = pro_forma_ni / pro_forma_shares if pro_forma_shares else 0.0

    accretion = (pro_forma_eps / standalone_eps - 1) if standalone_eps else float("nan")

    result = AccretionResult(
        acquirer_standalone_eps=standalone_eps,
        pro_forma_eps=pro_forma_eps,
        accretion_dilution_pct=accretion,
        pro_forma_net_income=pro_forma_ni,
        pro_forma_shares=pro_forma_shares,
        acquirer_net_income=acquirer.net_income,
        target_net_income=target.net_income,
        after_tax_synergies=after_tax_synergies,
        after_tax_new_interest=after_tax_new_interest,
        after_tax_foregone_interest=after_tax_foregone_interest,
    )

    if solve_diagnostics:
        result.synergies_to_neutral = synergies_for_neutral(
            acquirer, target, structure, cfg)
        result.breakeven_premium = solve_breakeven_premium(
            acquirer, target, after_tax_synergies, cfg,
            cash_pct=cash_pct if cash_pct is not None else structure.cash_pct,
            stock_pct=stock_pct if stock_pct is not None else structure.stock_pct,
            new_debt_pct=new_debt_pct if new_debt_pct is not None else structure.new_debt_pct,
        )
    return result


def synergies_for_neutral(acquirer: Company, target: Company,
                          structure: DealStructure,
                          cfg: Config = DEFAULT_CONFIG) -> float:
    """After-tax synergies that make the deal EPS-neutral, structure held fixed.

    Neutral <=> pro_forma_EPS == standalone_EPS <=> pro_forma_NI == standalone_EPS * pro_forma_shares.
    Solved in closed form (synergies enter net income linearly).
    """
    tax = acquirer.tax_rate
    after_tax_new_interest = structure.new_debt * cfg.interest_rate_new_debt * (1 - tax)
    after_tax_foregone_interest = structure.acquirer_cash_used * cfg.foregone_yield_on_cash * (1 - tax)
    pro_forma_shares = acquirer.shares_diluted + structure.new_shares_issued
    standalone_eps = acquirer.eps

    required_pro_forma_ni = standalone_eps * pro_forma_shares
    synergies = (required_pro_forma_ni - acquirer.net_income - target.net_income
                 + after_tax_new_interest + after_tax_foregone_interest)
    return synergies


def _accretion_at_premium(acquirer: Company, target: Company, premium: float,
                          after_tax_synergies: float, cfg: Config,
                          cash_pct: float, stock_pct: float, new_debt_pct: float) -> float:
    structure = build_structure(acquirer, target, premium=premium,
                                cash_pct=cash_pct, stock_pct=stock_pct,
                                new_debt_pct=new_debt_pct, cfg=cfg)
    res = compute_accretion(acquirer, target, structure, after_tax_synergies,
                            cfg, solve_diagnostics=False)
    return res.accretion_dilution_pct


def solve_breakeven_premium(acquirer: Company, target: Company,
                            after_tax_synergies: float = 0.0,
                            cfg: Config = DEFAULT_CONFIG,
                            cash_pct: float | None = None,
                            stock_pct: float | None = None,
                            new_debt_pct: float | None = None,
                            lo: float = -0.99, hi: float = 5.0,
                            tol: float = 1e-7, max_iter: int = 200) -> Optional[float]:
    """Solve the premium at which accretion == 0, holding the consideration mix fixed.

    Bisection over premium. Returns None if no sign change is bracketed in
    [lo, hi] (e.g. a cash deal that is accretive at every premium in range).
    """
    cash_pct = cfg.cash_pct if cash_pct is None else cash_pct
    stock_pct = cfg.stock_pct if stock_pct is None else stock_pct
    new_debt_pct = cfg.new_debt_pct if new_debt_pct is None else new_debt_pct

    def f(p: float) -> float:
        return _accretion_at_premium(acquirer, target, p, after_tax_synergies, cfg,
                                     cash_pct, stock_pct, new_debt_pct)

    f_lo, f_hi = f(lo), f(hi)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        return None  # no bracketed root in range

    a, b = lo, hi
    for _ in range(max_iter):
        mid = 0.5 * (a + b)
        fm = f(mid)
        if abs(fm) < tol or (b - a) < tol:
            return mid
        if (fm > 0) == (f_lo > 0):
            a, f_lo = mid, fm
        else:
            b = mid
    return 0.5 * (a + b)


def analyze_deal(acquirer: Company, target: Company,
                 after_tax_synergies: float = 0.0,
                 premium: float | None = None,
                 cash_pct: float | None = None,
                 stock_pct: float | None = None,
                 new_debt_pct: float | None = None,
                 cfg: Config = DEFAULT_CONFIG) -> tuple[DealStructure, AccretionResult]:
    """Convenience: build the structure and compute accretion in one call."""
    structure = build_structure(acquirer, target, premium=premium,
                                cash_pct=cash_pct, stock_pct=stock_pct,
                                new_debt_pct=new_debt_pct, cfg=cfg)
    result = compute_accretion(acquirer, target, structure, after_tax_synergies, cfg,
                               cash_pct=cash_pct, stock_pct=stock_pct, new_debt_pct=new_debt_pct)
    return structure, result
