"""Normalized fundamentals: build the universe of ``Company`` objects and persist
it to parquet.

Two build paths:
  * ``build_from_seed`` — deterministic, offline, uses the curated seed snapshot.
  * ``build_from_edgar`` — live SEC XBRL pull + market data provider.

Both yield the same normalized ``Company`` list, which is what every downstream
phase consumes.
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from ..config import Config, DEFAULT_CONFIG
from ..models import Company, Segment
from . import ingest_edgar
from .market_data import MarketDataProvider
from .seed_fundamentals import SEED
from .universe import UniverseEntry, load_universe


def _company_from_seed(entry: UniverseEntry, s: dict) -> Company:
    ebitda = s["ebit"] + s["da"]
    return Company(
        ticker=entry.ticker,
        cik=entry.cik,
        name=entry.name,
        sector="enterprise_software",
        business_description=entry.description,
        segments=[Segment(name=n) for n in entry.segments],
        revenue=s["revenue"],
        ebitda=ebitda,
        ebit=s["ebit"],
        net_income=s["net_income"],
        tax_rate=s.get("tax_rate", 0.21),
        interest_expense=s.get("interest_expense", 0.0),
        total_debt=s["total_debt"],
        cash_and_equivalents=s["cash"],
        capex=s["capex"],
        depreciation_amortization=s["da"],
        change_in_nwc=0.0,
        share_price=s["share_price"],
        shares_diluted=s["shares_diluted"],
        beta=s.get("beta", 1.0),
    )


def build_from_seed(sector: str = "enterprise_software") -> list[Company]:
    companies = []
    for entry in load_universe(sector):
        s = SEED.get(entry.ticker)
        if s is None:
            continue
        companies.append(_company_from_seed(entry, s))
    return companies


def build_from_edgar(sector: str = "enterprise_software",
                     cfg: Config = DEFAULT_CONFIG,
                     market: Optional[MarketDataProvider] = None) -> list[Company]:
    companies = []
    for entry in load_universe(sector):
        c = ingest_edgar.ingest_company(entry.ticker, entry.cik, sector, cfg=cfg, market=market)
        c.name = entry.name
        c.business_description = entry.description
        c.segments = [Segment(name=n) for n in entry.segments]
        companies.append(c)
    return companies


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_COLUMNS = [
    "ticker", "cik", "name", "sector", "business_description",
    "revenue", "ebitda", "ebit", "net_income", "tax_rate", "interest_expense",
    "total_debt", "cash_and_equivalents", "capex", "depreciation_amortization",
    "change_in_nwc", "share_price", "shares_diluted", "beta", "segments",
]


def to_dataframe(companies: list[Company]) -> pd.DataFrame:
    rows = []
    for c in companies:
        d = c.model_dump()
        d["segments"] = "|".join(s.name for s in c.segments)
        rows.append({k: d.get(k) for k in _COLUMNS})
    return pd.DataFrame(rows, columns=_COLUMNS)


def from_dataframe(df: pd.DataFrame) -> list[Company]:
    companies = []
    for _, row in df.iterrows():
        seg = str(row.get("segments") or "")
        segments = [Segment(name=n) for n in seg.split("|") if n]
        data = {k: row[k] for k in _COLUMNS if k in row and k != "segments"}
        companies.append(Company(segments=segments, **data))
    return companies


def save_universe(companies: list[Company], cfg: Config = DEFAULT_CONFIG) -> str:
    os.makedirs(cfg.data_dir, exist_ok=True)
    path = os.path.join(cfg.data_dir, "universe_fundamentals.parquet")
    to_dataframe(companies).to_parquet(path, index=False)
    return path


def load_universe_fundamentals(cfg: Config = DEFAULT_CONFIG) -> list[Company]:
    path = os.path.join(cfg.data_dir, "universe_fundamentals.parquet")
    if not os.path.exists(path):
        # fall back to the deterministic seed build
        return build_from_seed()
    return from_dataframe(pd.read_parquet(path))


def get_company(companies: list[Company], ticker: str) -> Company:
    for c in companies:
        if c.ticker == ticker.upper():
            return c
    raise KeyError(f"{ticker} not found in universe")
