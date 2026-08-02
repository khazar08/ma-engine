"""Pull and parse XBRL company-facts from SEC EDGAR.

The SEC exposes structured XBRL "company facts" at
``https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json``. This module pulls
that JSON and extracts the most recent annual (FY) values for the fields in the
``Company`` model, mapping standard US-GAAP tags.

A User-Agent header is required by the SEC on every request.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import requests

from ..config import Config, DEFAULT_CONFIG
from ..models import Company, Segment
from .market_data import MarketDataProvider

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# US-GAAP tag preference lists (first hit wins).
TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
    "net_income": ["NetIncomeLoss"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating"],
    "long_term_debt_noncurrent": ["LongTermDebtNoncurrent"],
    "long_term_debt_current": ["LongTermDebtCurrent"],
    "short_term_borrowings": ["ShortTermBorrowings", "DebtCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "da": ["DepreciationDepletionAndAmortization",
           "DepreciationAmortizationAndAccretionNet",
           "DepreciationAndAmortization"],
    "shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "ebit": ["OperatingIncomeLoss"],
    "tax_expense": ["IncomeTaxExpenseBenefit"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
}


def _pad_cik(cik: str) -> str:
    return str(cik).lstrip("C").lstrip("IK").strip().zfill(10)


def fetch_company_facts(cik: str, cfg: Config = DEFAULT_CONFIG,
                        session: Optional[requests.Session] = None) -> dict:
    """Fetch raw company-facts JSON, using an on-disk cache."""
    padded = _pad_cik(cik)
    os.makedirs(cfg.cache_dir, exist_ok=True)
    cache_path = os.path.join(cfg.cache_dir, f"facts_{padded}.json")
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)

    url = COMPANY_FACTS_URL.format(cik=padded)
    sess = session or requests.Session()
    resp = sess.get(url, headers={"User-Agent": cfg.sec_user_agent}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    with open(cache_path, "w") as f:
        json.dump(data, f)
    return data


def _latest_annual_value(facts: dict, tags: list[str],
                         units: tuple[str, ...] = ("USD", "shares")) -> Optional[float]:
    """Return the most recent FY (annual, form 10-K) value for the first matching tag.

    Annual figures are identified by full-year duration facts (``fp == 'FY'`` and
    ``form`` starting with '10-K') or point-in-time instant facts for balance-sheet
    tags. The most recent fiscal year end wins.
    """
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        node = gaap.get(tag)
        if not node:
            continue
        for unit in units:
            series = node.get("units", {}).get(unit)
            if not series:
                continue
            best = None
            for pt in series:
                form = str(pt.get("form", ""))
                if not form.startswith("10-K"):
                    continue
                # For duration facts require full-year (FY); instants have no 'fp' gate
                start, end = pt.get("start"), pt.get("end")
                if start is not None and pt.get("fp") not in ("FY", None):
                    continue
                if pt.get("val") is None or end is None:
                    continue
                if best is None or end > best.get("end", ""):
                    best = pt
            if best is not None:
                return float(best["val"])
    return None


def parse_company(ticker: str, cik: str, sector: str, facts: dict,
                  market: Optional[MarketDataProvider] = None,
                  business_description: str = "",
                  segments: Optional[list[Segment]] = None) -> Company:
    """Build a normalized ``Company`` from raw company-facts JSON.

    Monetary XBRL values are reported in whole dollars; we convert to millions.
    """
    def mm(key: str) -> float:
        v = _latest_annual_value(facts, TAGS[key])
        return (v / 1e6) if v is not None else 0.0

    revenue = mm("revenue")
    ebit = mm("ebit")
    da = mm("da")
    net_income = mm("net_income")
    ebitda = ebit + da

    ltd_nc = mm("long_term_debt_noncurrent")
    ltd_c = mm("long_term_debt_current")
    stb = mm("short_term_borrowings")
    total_debt = ltd_nc + ltd_c + stb

    # Effective tax rate from tax expense / pretax income, fall back to 21%.
    tax_expense = mm("tax_expense")
    pretax = mm("pretax_income")
    tax_rate = tax_expense / pretax if pretax else 0.21
    if not (0.0 <= tax_rate <= 0.6):
        tax_rate = 0.21

    shares = 0.0
    sv = _latest_annual_value(facts, TAGS["shares"], units=("shares",))
    if sv is not None:
        shares = sv / 1e6  # -> millions

    company = Company(
        ticker=ticker.upper(),
        cik=_pad_cik(cik),
        name=facts.get("entityName", ticker.upper()),
        sector=sector,
        business_description=business_description,
        segments=segments or [],
        revenue=revenue,
        ebitda=ebitda,
        ebit=ebit,
        net_income=net_income,
        tax_rate=tax_rate,
        interest_expense=mm("interest_expense"),
        total_debt=total_debt,
        cash_and_equivalents=mm("cash"),
        capex=mm("capex"),
        depreciation_amortization=da,
        change_in_nwc=0.0,  # not directly disclosed; estimated in DCF driver
    )

    if market is not None:
        snap = market.get_snapshot(ticker)
        company.share_price = snap.price
        company.shares_diluted = snap.shares or shares
        company.beta = snap.beta
    else:
        company.shares_diluted = shares

    return company


def ingest_company(ticker: str, cik: str, sector: str,
                   cfg: Config = DEFAULT_CONFIG,
                   market: Optional[MarketDataProvider] = None) -> Company:
    facts = fetch_company_facts(cik, cfg)
    return parse_company(ticker, cik, sector, facts, market=market)
