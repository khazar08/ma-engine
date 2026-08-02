"""Phase 1 tests: models, fundamentals build, EDGAR parsing, persistence."""
import json

import pytest

from ma_engine.data import fundamentals
from ma_engine.data.ingest_edgar import _latest_annual_value, _pad_cik, parse_company
from ma_engine.data.market_data import MarketSnapshot, StaticMarketDataProvider
from ma_engine.models import Company


def test_derived_properties():
    c = Company(ticker="X", share_price=100.0, shares_diluted=10.0,
                total_debt=200.0, cash_and_equivalents=50.0,
                ebit=30.0, ebitda=40.0, depreciation_amortization=10.0, revenue=300.0,
                net_income=50.0)
    assert c.market_cap == pytest.approx(1000.0)
    assert c.net_debt == pytest.approx(150.0)
    # enterprise_value == market_cap + net_debt
    assert c.enterprise_value == pytest.approx(c.market_cap + c.net_debt)
    assert c.enterprise_value == pytest.approx(1150.0)
    assert c.eps == pytest.approx(5.0)
    assert c.pe == pytest.approx(20.0)
    assert c.ebitda_margin == pytest.approx(40.0 / 300.0)  # not used here but sanity


def test_seed_universe_builds_clean():
    companies = fundamentals.build_from_seed()
    assert len(companies) >= 20
    for c in companies:
        assert c.ticker
        assert c.revenue > 0
        assert c.shares_diluted > 0
        assert c.share_price > 0
        # EBITDA defined as EBIT + D&A
        assert c.ebitda == pytest.approx(c.ebit + c.depreciation_amortization)
        # EV identity holds
        assert c.enterprise_value == pytest.approx(c.market_cap + c.net_debt)


def test_persistence_roundtrip(tmp_path):
    from ma_engine.config import DEFAULT_CONFIG

    cfg = DEFAULT_CONFIG.with_updates(data_dir=str(tmp_path))
    companies = fundamentals.build_from_seed()
    path = fundamentals.save_universe(companies, cfg)
    loaded = fundamentals.load_universe_fundamentals(cfg)
    assert len(loaded) == len(companies)
    a = {c.ticker: c for c in companies}
    b = {c.ticker: c for c in loaded}
    for t in a:
        assert b[t].revenue == pytest.approx(a[t].revenue)
        assert b[t].net_income == pytest.approx(a[t].net_income)
        assert [s.name for s in b[t].segments] == [s.name for s in a[t].segments]


def test_pad_cik():
    assert _pad_cik("320193") == "0000320193"
    assert _pad_cik("CIK0000320193") == "0000320193"
    assert _pad_cik("0000320193") == "0000320193"


def _fake_facts():
    """Minimal company-facts JSON with two fiscal years; latest FY should win."""
    def dur(val, start, end, fy=True):
        return {"val": val, "start": start, "end": end, "form": "10-K",
                "fp": "FY" if fy else "Q1"}

    def inst(val, end):
        return {"val": val, "end": end, "form": "10-K", "fp": "FY"}

    return {
        "entityName": "Test Co",
        "facts": {"us-gaap": {
            "Revenues": {"units": {"USD": [
                dur(1000e6, "2022-01-01", "2022-12-31"),
                dur(1200e6, "2023-01-01", "2023-12-31"),
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                dur(100e6, "2022-01-01", "2022-12-31"),
                dur(150e6, "2023-01-01", "2023-12-31"),
            ]}},
            "OperatingIncomeLoss": {"units": {"USD": [
                dur(200e6, "2023-01-01", "2023-12-31"),
            ]}},
            "DepreciationDepletionAndAmortization": {"units": {"USD": [
                dur(50e6, "2023-01-01", "2023-12-31"),
            ]}},
            "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [
                inst(300e6, "2022-12-31"), inst(400e6, "2023-12-31"),
            ]}},
            "LongTermDebtNoncurrent": {"units": {"USD": [inst(500e6, "2023-12-31")]}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
                dur(90e6, "2023-01-01", "2023-12-31"),
            ]}},
            "IncomeTaxExpenseBenefit": {"units": {"USD": [dur(40e6, "2023-01-01", "2023-12-31")]}},
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest":
                {"units": {"USD": [dur(190e6, "2023-01-01", "2023-12-31")]}},
        }}
    }


def test_latest_annual_value_picks_most_recent_fy():
    facts = _fake_facts()
    from ma_engine.data.ingest_edgar import TAGS
    assert _latest_annual_value(facts, TAGS["revenue"]) == pytest.approx(1200e6)
    assert _latest_annual_value(facts, TAGS["net_income"]) == pytest.approx(150e6)


def test_parse_company_units_and_ebitda():
    facts = _fake_facts()
    market = StaticMarketDataProvider({
        "TST": MarketSnapshot("TST", price=20.0, shares=90.0, beta=1.1)
    })
    c = parse_company("TST", "0000000001", "enterprise_software", facts, market=market)
    # values converted to millions
    assert c.revenue == pytest.approx(1200.0)
    assert c.net_income == pytest.approx(150.0)
    assert c.ebit == pytest.approx(200.0)
    assert c.depreciation_amortization == pytest.approx(50.0)
    assert c.ebitda == pytest.approx(250.0)
    assert c.total_debt == pytest.approx(500.0)
    assert c.cash_and_equivalents == pytest.approx(400.0)
    # effective tax rate = 40 / 190
    assert c.tax_rate == pytest.approx(40.0 / 190.0)
    assert c.share_price == 20.0
    assert c.shares_diluted == 90.0
