"""CLI orchestration.

    python -m ma_engine.main --acquirer CRM --top 5 --premium 0.30 --cash 0.5 --stock 0.5

Loads the universe fundamentals (Phase 1 output, or the seed build), screens the
acquirer against the universe, runs a full deal analysis per shortlisted target,
writes one teaser PDF each, and prints + saves a ranked summary index.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from .config import DEFAULT_CONFIG
from .data import fundamentals
from .pipeline import run_engine, summary_frame


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ma_engine", description="Automated M&A origination & deal analysis")
    p.add_argument("--acquirer", required=True, help="Acquirer ticker, e.g. CRM")
    p.add_argument("--top", type=int, default=DEFAULT_CONFIG.top_n, help="Shortlist size")
    p.add_argument("--premium", type=float, default=DEFAULT_CONFIG.default_premium, help="Offer premium (e.g. 0.30)")
    p.add_argument("--cash", type=float, default=DEFAULT_CONFIG.cash_pct, help="Cash %% of consideration")
    p.add_argument("--stock", type=float, default=DEFAULT_CONFIG.stock_pct, help="Stock %% of consideration")
    p.add_argument("--new-debt", type=float, default=DEFAULT_CONFIG.new_debt_pct, help="New-debt %% of consideration")
    p.add_argument("--no-teasers", action="store_true", help="Skip PDF generation")
    p.add_argument("--source", choices=["seed", "parquet", "edgar"], default="parquet",
                   help="Fundamentals source (default: parquet, falling back to seed)")
    p.add_argument("--out", default=DEFAULT_CONFIG.out_dir, help="Output directory")
    return p


def load_universe(source: str) -> list:
    if source == "seed":
        return fundamentals.build_from_seed()
    if source == "edgar":
        from .data.market_data import YFinanceMarketDataProvider
        return fundamentals.build_from_edgar(market=YFinanceMarketDataProvider(DEFAULT_CONFIG.cache_dir))
    return fundamentals.load_universe_fundamentals()  # parquet w/ seed fallback


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = DEFAULT_CONFIG.with_updates(default_premium=args.premium, cash_pct=args.cash,
                                      stock_pct=args.stock, new_debt_pct=args.new_debt,
                                      top_n=args.top, out_dir=args.out)

    universe = load_universe(args.source)
    tickers = {c.ticker for c in universe}
    if args.acquirer.upper() not in tickers:
        print(f"Acquirer {args.acquirer!r} not in universe. Available: {', '.join(sorted(tickers))}",
              file=sys.stderr)
        return 2

    shortlist, analyses = run_engine(
        args.acquirer.upper(), universe, cfg=cfg, top_n=args.top,
        premium=args.premium, cash_pct=args.cash, stock_pct=args.stock,
        new_debt_pct=args.new_debt, make_teasers=not args.no_teasers)

    summary = summary_frame(shortlist, analyses)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    print(f"\n=== M&A shortlist for {args.acquirer.upper()} "
          f"(premium {args.premium:.0%}, {args.cash:.0%} cash / {args.stock:.0%} stock) ===\n")
    print(summary.to_string(index=False))

    os.makedirs(cfg.out_dir, exist_ok=True)
    csv_path = os.path.join(cfg.out_dir, f"shortlist_{args.acquirer.upper()}.csv")
    summary.to_csv(csv_path, index=False)
    print(f"\nSummary written to {csv_path}")
    if not args.no_teasers:
        print(f"Teasers written to {cfg.out_dir}/teaser_{args.acquirer.upper()}_*.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
