"""Phase 3 tests: DCF (hand-computed toy), WACC, comps, precedents, football field."""
import pytest

from ma_engine.config import DEFAULT_CONFIG
from ma_engine.data import fundamentals
from ma_engine.models import Company
from ma_engine.valuation import comps as comps_mod
from ma_engine.valuation import dcf as dcf_mod
from ma_engine.valuation import football_field, precedents as prec_mod


# ---------------------------------------------------------------------------
# DCF — hand-computed toy example, asserted to the cent.
# ---------------------------------------------------------------------------

def test_two_year_toy_dcf_exact():
    """A 2-year DCF with a fixed WACC and flat drivers, computed by hand.

    Setup: revenue 100 (yr0), 0% growth so revenue stays 100 each year.
      EBIT margin 20% -> EBIT 20 ; tax 25% -> EBIT*(1-t) = 15
      D&A = 10, CapEx = 5, ΔNWC = 0 (no revenue change)
      UFCF each year = 15 + 10 - 5 - 0 = 20
    WACC forced to 10%, terminal growth g = 0% (Gordon).
      PV yr1 = 20 / 1.1        = 18.181818...
      PV yr2 = 20 / 1.21       = 16.528925...
      PV explicit              = 34.710743...
      TV Gordon = 20*(1+0)/(0.10-0) = 200
      PV TV = 200 / 1.21       = 165.289256...
      EV = 34.710743 + 165.289256 = 200.0 exactly
      Equity = EV - net_debt(0) = 200 ; per-share = 200/10 = 20
    """
    c = Company(ticker="TOY", revenue=100.0, ebit=20.0, ebitda=30.0,
                depreciation_amortization=10.0, capex=5.0, net_income=15.0,
                tax_rate=0.25, total_debt=0.0, cash_and_equivalents=0.0,
                share_price=1.0, shares_diluted=10.0, beta=1.0)
    assumptions = dcf_mod.DCFAssumptions(
        revenue_growth_start=0.0, revenue_growth_terminal=0.0,
        ebit_margin=0.20, da_pct_revenue=0.10, capex_pct_revenue=0.05,
        nwc_pct_revenue_change=0.10, projection_years=2,
        terminal_growth=0.0, exit_ebitda_multiple=None,
    )
    res = dcf_mod.run_dcf(c, assumptions, DEFAULT_CONFIG, wacc=0.10)

    assert res.ufcf[0] == pytest.approx(20.0)
    assert res.ufcf[1] == pytest.approx(20.0)
    assert res.pv_explicit == pytest.approx(34.7107438, abs=1e-6)
    assert res.tv_gordon == pytest.approx(200.0)
    assert res.pv_tv_gordon == pytest.approx(165.2892562, abs=1e-6)
    assert res.ev_gordon == pytest.approx(200.0, abs=1e-6)
    assert res.equity_gordon == pytest.approx(200.0, abs=1e-6)
    assert res.per_share_gordon == pytest.approx(20.0, abs=1e-6)


def test_exit_multiple_terminal_value():
    c = Company(ticker="TOY", revenue=100.0, ebit=20.0, ebitda=30.0,
                depreciation_amortization=10.0, capex=5.0, net_income=15.0,
                tax_rate=0.25, total_debt=0.0, cash_and_equivalents=0.0,
                share_price=1.0, shares_diluted=10.0, beta=1.0)
    assumptions = dcf_mod.DCFAssumptions(
        revenue_growth_start=0.0, revenue_growth_terminal=0.0,
        ebit_margin=0.20, da_pct_revenue=0.10, capex_pct_revenue=0.05,
        nwc_pct_revenue_change=0.10, projection_years=2,
        terminal_growth=0.0, exit_ebitda_multiple=10.0,
    )
    res = dcf_mod.run_dcf(c, assumptions, DEFAULT_CONFIG, wacc=0.10)
    # terminal-year EBITDA = EBIT(20) + D&A(10) = 30 ; TV = 10 * 30 = 300
    assert res.tv_exit == pytest.approx(300.0)
    # PV TV = 300 / 1.21 ; EV = pv_explicit + that
    assert res.pv_tv_exit == pytest.approx(300.0 / 1.21, abs=1e-6)
    assert res.ev_exit == pytest.approx(res.pv_explicit + 300.0 / 1.21, abs=1e-6)


def test_gordon_guard_raises_when_g_ge_wacc():
    c = Company(ticker="X", revenue=100.0, ebit=20.0, ebitda=30.0,
                depreciation_amortization=10.0, capex=5.0, net_income=15.0,
                tax_rate=0.25, share_price=1.0, shares_diluted=10.0, beta=1.0)
    assumptions = dcf_mod.DCFAssumptions(
        revenue_growth_start=0.0, revenue_growth_terminal=0.0,
        ebit_margin=0.20, da_pct_revenue=0.10, capex_pct_revenue=0.05,
        nwc_pct_revenue_change=0.10, projection_years=2,
        terminal_growth=0.10, exit_ebitda_multiple=None,
    )
    with pytest.raises(ValueError):
        dcf_mod.run_dcf(c, assumptions, DEFAULT_CONFIG, wacc=0.10)  # g == WACC


def test_wacc_capm_and_weights():
    # all-equity company: WACC == cost of equity == Rf + beta*ERP
    c = Company(ticker="E", share_price=10.0, shares_diluted=100.0, total_debt=0.0,
                cash_and_equivalents=0.0, beta=1.2, tax_rate=0.21)
    wacc, ke, kd = dcf_mod.compute_wacc(c, DEFAULT_CONFIG)
    assert ke == pytest.approx(DEFAULT_CONFIG.risk_free_rate + 1.2 * DEFAULT_CONFIG.equity_risk_premium)
    assert wacc == pytest.approx(ke)

    # 50/50 cap structure
    c2 = Company(ticker="M", share_price=10.0, shares_diluted=100.0, total_debt=1000.0,
                 cash_and_equivalents=0.0, beta=1.0, tax_rate=0.20)
    wacc2, ke2, kd2 = dcf_mod.compute_wacc(c2, DEFAULT_CONFIG)
    expected = 0.5 * ke2 + 0.5 * kd2 * (1 - 0.20)
    assert wacc2 == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Comps & precedents
# ---------------------------------------------------------------------------

def test_comps_uses_median_multiple():
    # target + 3 peers with known EV/EBITDA -> median applied
    target = Company(ticker="T", sector="s", business_description="data platform analytics",
                     revenue=100.0, ebitda=20.0, net_income=10.0, share_price=10.0,
                     shares_diluted=10.0, total_debt=0.0, cash_and_equivalents=0.0)
    peers = []
    for i, mult in enumerate([8.0, 10.0, 12.0]):
        # construct a peer with EV/EBITDA == mult, no debt so EV == market cap
        ebitda = 50.0
        ev = mult * ebitda
        peers.append(Company(ticker=f"P{i}", sector="s",
                             business_description="data platform analytics",
                             revenue=200.0, ebitda=ebitda, net_income=25.0,
                             share_price=ev / 100.0, shares_diluted=100.0,
                             total_debt=0.0, cash_and_equivalents=0.0))
    res = comps_mod.compute_comps(target, [target] + peers, n_peers=3)
    assert res.median_ev_ebitda == pytest.approx(10.0)
    # implied EV = 10 * 20 = 200 ; equity = 200 - net_debt(0) = 200
    assert res.implied_equity_by_method["EV/EBITDA"] == pytest.approx(200.0)


def test_precedents_include_control_premium_flag():
    target = Company(ticker="T", sector="enterprise_software", revenue=1000.0,
                     ebitda=200.0, net_income=100.0, share_price=10.0,
                     shares_diluted=100.0, total_debt=0.0, cash_and_equivalents=0.0)
    res = prec_mod.compute_precedents(target, DEFAULT_CONFIG)
    assert res.n_deals > 0
    mr = prec_mod.precedent_range(res)
    assert mr is not None
    assert mr.includes_control_premium is True


def test_football_field_on_real_universe():
    companies = fundamentals.build_from_seed()
    universe = companies
    target = fundamentals.get_company(companies, "DDOG")
    val = football_field.build_valuation(target, universe, DEFAULT_CONFIG)
    method_names = {m.method for m in val.methods}
    # comps + precedents at minimum; DDOG is EBITDA-positive so DCF should appear
    assert "Trading comps" in method_names
    assert "Precedent transactions" in method_names
    assert len(val.peers_used) > 0
