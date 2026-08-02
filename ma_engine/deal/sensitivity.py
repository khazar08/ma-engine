"""Sensitivity grid: premium paid (rows) × synergy realization % (cols) -> accretion/dilution %.

The single most banker-legible output. Returned as a pandas DataFrame indexed by
premium, columns = synergy realization fraction, values = accretion/dilution %.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from ..config import Config, DEFAULT_CONFIG
from ..models import Company
from .accretion_dilution import compute_accretion
from .structure import build_structure


def sensitivity_grid(acquirer: Company, target: Company,
                     base_after_tax_synergies: float,
                     premiums: Optional[list[float]] = None,
                     synergy_realizations: Optional[list[float]] = None,
                     cash_pct: float | None = None,
                     stock_pct: float | None = None,
                     new_debt_pct: float | None = None,
                     cfg: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """Build the premium × synergy-realization accretion grid.

    ``base_after_tax_synergies`` is the 100%-realization run-rate; each column
    scales it by a realization fraction.
    """
    if premiums is None:
        premiums = [0.10, 0.20, 0.30, 0.40, 0.50]
    if synergy_realizations is None:
        synergy_realizations = [0.0, 0.25, 0.50, 0.75, 1.0]

    cash_pct = cfg.cash_pct if cash_pct is None else cash_pct
    stock_pct = cfg.stock_pct if stock_pct is None else stock_pct
    new_debt_pct = cfg.new_debt_pct if new_debt_pct is None else new_debt_pct

    data = {}
    for real in synergy_realizations:
        col = []
        for prem in premiums:
            structure = build_structure(acquirer, target, premium=prem,
                                        cash_pct=cash_pct, stock_pct=stock_pct,
                                        new_debt_pct=new_debt_pct, cfg=cfg)
            res = compute_accretion(acquirer, target, structure,
                                    after_tax_synergies=base_after_tax_synergies * real,
                                    cfg=cfg, solve_diagnostics=False)
            col.append(res.accretion_dilution_pct)
        data[real] = col

    df = pd.DataFrame(data, index=premiums)
    df.index.name = "premium"
    df.columns.name = "synergy_realization"
    return df
