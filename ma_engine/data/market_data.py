"""Market data provider abstraction.

`MarketDataProvider` is the interface the rest of the engine codes against, so
the concrete source (yfinance today, a paid feed tomorrow) can be swapped
without touching valuation logic. Results are cached to disk as parquet to avoid
hammering the API on every run.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class MarketSnapshot:
    ticker: str
    price: float          # USD
    shares: float         # millions of shares
    beta: float


class MarketDataProvider(ABC):
    @abstractmethod
    def get_price(self, ticker: str) -> float: ...

    @abstractmethod
    def get_shares(self, ticker: str) -> float: ...

    @abstractmethod
    def get_beta(self, ticker: str) -> float: ...

    def get_snapshot(self, ticker: str) -> MarketSnapshot:
        return MarketSnapshot(
            ticker=ticker,
            price=self.get_price(ticker),
            shares=self.get_shares(ticker),
            beta=self.get_beta(ticker),
        )


class StaticMarketDataProvider(MarketDataProvider):
    """Deterministic provider backed by an in-memory dict.

    Used for tests and for offline runs seeded from a curated snapshot. Keeps the
    whole pipeline runnable without network access.
    """

    def __init__(self, table: dict[str, MarketSnapshot]):
        self._table = table

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "StaticMarketDataProvider":
        table = {}
        for _, row in df.iterrows():
            t = str(row["ticker"]).upper()
            table[t] = MarketSnapshot(
                ticker=t,
                price=float(row["share_price"]),
                shares=float(row["shares_diluted"]),
                beta=float(row.get("beta", 1.0)),
            )
        return cls(table)

    def _get(self, ticker: str) -> MarketSnapshot:
        snap = self._table.get(ticker.upper())
        if snap is None:
            raise KeyError(f"No market snapshot for {ticker}")
        return snap

    def get_price(self, ticker: str) -> float:
        return self._get(ticker).price

    def get_shares(self, ticker: str) -> float:
        return self._get(ticker).shares

    def get_beta(self, ticker: str) -> float:
        return self._get(ticker).beta


class YFinanceMarketDataProvider(MarketDataProvider):
    """Live provider backed by yfinance, cached to parquet.

    yfinance is best-effort and rate-limited; shares are returned in millions to
    match the rest of the engine's units.
    """

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._cache_path = os.path.join(cache_dir, "market_snapshots.parquet")
        self._cache: dict[str, MarketSnapshot] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if os.path.exists(self._cache_path):
            try:
                df = pd.read_parquet(self._cache_path)
                self._cache = StaticMarketDataProvider.from_dataframe(df)._table
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        if not self._cache:
            return
        rows = [
            {"ticker": s.ticker, "share_price": s.price, "shares_diluted": s.shares, "beta": s.beta}
            for s in self._cache.values()
        ]
        pd.DataFrame(rows).to_parquet(self._cache_path, index=False)

    def _fetch(self, ticker: str) -> MarketSnapshot:
        if ticker.upper() in self._cache:
            return self._cache[ticker.upper()]
        import yfinance as yf  # imported lazily so the package works without it

        tk = yf.Ticker(ticker)
        info = tk.info or {}
        price = float(info.get("currentPrice") or info.get("previousClose") or 0.0)
        shares = float(info.get("sharesOutstanding") or 0.0) / 1e6  # -> millions
        beta = float(info.get("beta") or 1.0)
        snap = MarketSnapshot(ticker=ticker.upper(), price=price, shares=shares, beta=beta)
        self._cache[ticker.upper()] = snap
        self._save_cache()
        return snap

    def get_price(self, ticker: str) -> float:
        return self._fetch(ticker).price

    def get_shares(self, ticker: str) -> float:
        return self._fetch(ticker).shares

    def get_beta(self, ticker: str) -> float:
        return self._fetch(ticker).beta
