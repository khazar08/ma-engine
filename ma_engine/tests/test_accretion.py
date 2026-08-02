"""Phase 5 tests (CRITICAL): accretion/dilution signs, sources=uses, breakeven.

The sign conventions are the load-bearing part of the whole project, so these
use hand-constructed textbook examples with the exact expected direction.
"""
import pytest

from ma_engine.config import DEFAULT_CONFIG
from ma_engine.deal import accretion_dilution as ad
from ma_engine.deal.sensitivity import sensitivity_grid
from ma_engine.deal.structure import build_structure
from ma_engine.models import Company


def _acq(ni, shares, price, tax=0.21, net_debt=0.0):
    return Company(ticker="ACQ", net_income=ni, shares_diluted=shares, share_price=price,
                   tax_rate=tax, total_debt=max(net_debt, 0.0),
                   cash_and_equivalents=max(-net_debt, 0.0))


def _tgt(ni, shares, price, net_debt=0.0):
    return Company(ticker="TGT", net_income=ni, shares_diluted=shares, share_price=price,
                   total_debt=max(net_debt, 0.0), cash_and_equivalents=max(-net_debt, 0.0))


# Config that isolates the pure P/E arithmetic: no fees, no cash/debt carry cost.
NOFEE = DEFAULT_CONFIG.with_updates(fee_pct=0.0, foregone_yield_on_cash=0.0,
                                    interest_rate_new_debt=0.0)


def test_all_stock_accretive_when_acquirer_pe_above_target():
    # Acquirer P/E 25 buys target at implied P/E 10, all-stock, 0% premium -> accretive
    acq = _acq(ni=1000.0, shares=1000.0, price=25.0)   # EPS 1.0, P/E 25
    tgt = _tgt(ni=100.0, shares=100.0, price=10.0)      # P/E paid = 1000/100 = 10
    struct, res = ad.analyze_deal(acq, tgt, after_tax_synergies=0.0, premium=0.0,
                                  cash_pct=0.0, stock_pct=1.0, new_debt_pct=0.0, cfg=NOFEE)
    # new shares = 1000 / 25 = 40 ; PF NI = 1100 ; PF shares = 1040 ; EPS 1.05769
    assert struct.new_shares_issued == pytest.approx(40.0)
    assert res.pro_forma_eps == pytest.approx(1100.0 / 1040.0)
    assert res.accretion_dilution_pct > 0
    assert res.is_accretive


def test_all_stock_dilutive_when_acquirer_pe_below_target():
    # Low-P/E acquirer (10) buys high-P/E target (25) all-stock -> dilutive
    acq = _acq(ni=1000.0, shares=1000.0, price=10.0)    # P/E 10
    tgt = _tgt(ni=100.0, shares=100.0, price=25.0)       # P/E paid = 2500/100 = 25
    struct, res = ad.analyze_deal(acq, tgt, after_tax_synergies=0.0, premium=0.0,
                                  cash_pct=0.0, stock_pct=1.0, new_debt_pct=0.0, cfg=NOFEE)
    assert struct.new_shares_issued == pytest.approx(250.0)  # 2500/10
    assert res.accretion_dilution_pct < 0
    assert not res.is_accretive


def test_cash_deal_accretive_when_cost_of_cash_below_earnings_yield():
    # All-cash from balance sheet. Target earnings yield on price = 100/1000 = 10%.
    # After-tax foregone yield 4.5%*(1-.21) ~ 3.6% < 10% -> accretive.
    acq = _acq(ni=1000.0, shares=1000.0, price=25.0)
    tgt = _tgt(ni=100.0, shares=100.0, price=10.0)
    cfg = DEFAULT_CONFIG.with_updates(fee_pct=0.0, foregone_yield_on_cash=0.045,
                                      interest_rate_new_debt=0.0)
    struct, res = ad.analyze_deal(acq, tgt, after_tax_synergies=0.0, premium=0.0,
                                  cash_pct=1.0, stock_pct=0.0, new_debt_pct=0.0, cfg=cfg)
    assert struct.new_shares_issued == pytest.approx(0.0)   # no shares issued in a cash deal
    assert res.accretion_dilution_pct > 0


def test_cash_more_accretive_than_stock_same_deal():
    # For a high-P/E acquirer, cash (cheap carry) beats stock (issuing cheap-cost equity here still dilutes less)
    acq = _acq(ni=1000.0, shares=1000.0, price=25.0)
    tgt = _tgt(ni=100.0, shares=100.0, price=10.0)
    cfg = DEFAULT_CONFIG.with_updates(fee_pct=0.0, foregone_yield_on_cash=0.045,
                                      interest_rate_new_debt=0.0)
    _, cash_res = ad.analyze_deal(acq, tgt, premium=0.30, cash_pct=1.0, stock_pct=0.0,
                                  new_debt_pct=0.0, cfg=cfg)
    _, stock_res = ad.analyze_deal(acq, tgt, premium=0.30, cash_pct=0.0, stock_pct=1.0,
                                   new_debt_pct=0.0, cfg=cfg)
    assert cash_res.accretion_dilution_pct > stock_res.accretion_dilution_pct


def test_sources_equal_uses_always():
    acq = _acq(ni=1000.0, shares=1000.0, price=25.0)
    tgt = _tgt(ni=100.0, shares=100.0, price=10.0, net_debt=200.0)
    for mix in [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.4, 0.4, 0.2)]:
        s = build_structure(acq, tgt, premium=0.35, cash_pct=mix[0], stock_pct=mix[1],
                            new_debt_pct=mix[2], cfg=DEFAULT_CONFIG)
        total_sources = s.new_debt + s.acquirer_cash_used + s.new_equity_issued
        assert total_sources == pytest.approx(s.total_uses)


def test_mix_must_sum_to_one():
    acq = _acq(1000.0, 1000.0, 25.0)
    tgt = _tgt(100.0, 100.0, 10.0)
    with pytest.raises(ValueError):
        build_structure(acq, tgt, premium=0.3, cash_pct=0.5, stock_pct=0.4, new_debt_pct=0.0)


def test_breakeven_premium_recovers_neutral_deal():
    # Dilutive-leaning stock deal so a finite breakeven premium exists.
    acq = _acq(ni=1000.0, shares=1000.0, price=15.0)   # P/E 15
    tgt = _tgt(ni=100.0, shares=100.0, price=12.0)
    be = ad.solve_breakeven_premium(acq, tgt, after_tax_synergies=0.0, cfg=NOFEE,
                                    cash_pct=0.0, stock_pct=1.0, new_debt_pct=0.0)
    assert be is not None
    # Plug the breakeven premium back in -> accretion ~ 0
    _, res = ad.analyze_deal(acq, tgt, premium=be, cash_pct=0.0, stock_pct=1.0,
                             new_debt_pct=0.0, cfg=NOFEE)
    assert res.accretion_dilution_pct == pytest.approx(0.0, abs=1e-5)


def test_synergies_to_neutral_makes_deal_neutral():
    acq = _acq(ni=1000.0, shares=1000.0, price=15.0)
    tgt = _tgt(ni=100.0, shares=100.0, price=12.0)
    struct = build_structure(acq, tgt, premium=0.30, cash_pct=0.0, stock_pct=1.0,
                             new_debt_pct=0.0, cfg=NOFEE)
    syn = ad.synergies_for_neutral(acq, tgt, struct, cfg=NOFEE)
    res = ad.compute_accretion(acq, tgt, struct, after_tax_synergies=syn, cfg=NOFEE,
                               solve_diagnostics=False)
    assert res.accretion_dilution_pct == pytest.approx(0.0, abs=1e-9)


def test_sensitivity_grid_shape_and_monotonicity():
    acq = _acq(ni=1000.0, shares=1000.0, price=15.0)
    tgt = _tgt(ni=100.0, shares=100.0, price=12.0)
    grid = sensitivity_grid(acq, tgt, base_after_tax_synergies=50.0,
                            premiums=[0.1, 0.3, 0.5], synergy_realizations=[0.0, 0.5, 1.0],
                            cash_pct=0.0, stock_pct=1.0, new_debt_pct=0.0, cfg=NOFEE)
    assert grid.shape == (3, 3)
    # More synergies -> more accretive (row-wise increasing across columns)
    for _, row in grid.iterrows():
        vals = list(row.values)
        assert vals == sorted(vals)
    # Higher premium -> less accretive (column-wise decreasing down rows)
    for col in grid.columns:
        vals = list(grid[col].values)
        assert vals == sorted(vals, reverse=True)
