"""Financial-fit scoring: margin accretion potential and balance-sheet capacity.

- margin_accretion: is the target's EBITDA margin above the acquirer's (accretive
  to combined margins)? Signed, then squashed to [0, 1].
- fundability:      pro forma net leverage if the deal were 100% debt-financed:
      pro_forma_leverage = (acq_net_debt + tgt_net_debt + equity_purchase) / combined_EBITDA
  Scored higher when leverage stays under the configured ceiling. Ties screening
  to whether the acquirer can actually pay — a real banker constraint.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..config import Config, DEFAULT_CONFIG
from ..models import Company


@dataclass
class FinancialScore:
    ticker: str
    margin_accretion: float
    fundability: float
    financial_score: float
    pro_forma_leverage: float


def _sigmoid(x: float) -> float:
    # overflow-safe logistic
    x = max(-60.0, min(60.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def margin_accretion_score(acquirer: Company, target: Company) -> float:
    """Signed margin delta squashed to [0, 1]; 0.5 = margin-neutral."""
    delta = target.ebitda_margin - acquirer.ebitda_margin
    # scale so a ±20pt margin gap maps to roughly the tails
    return _sigmoid(delta / 0.10)


def pro_forma_leverage(acquirer: Company, target: Company,
                       premium: float, cfg: Config = DEFAULT_CONFIG) -> float:
    """Pro forma net leverage assuming a 100%-debt-financed acquisition."""
    equity_purchase = target.share_price * (1 + premium) * target.shares_diluted
    combined_ebitda = acquirer.ebitda + target.ebitda
    total_net_debt = acquirer.net_debt + target.net_debt + equity_purchase
    if combined_ebitda <= 0:
        return float("inf")
    return total_net_debt / combined_ebitda


def fundability_score(acquirer: Company, target: Company,
                      cfg: Config = DEFAULT_CONFIG) -> tuple[float, float]:
    """Return (fundability_score, pro_forma_leverage).

    Score is 1.0 at zero leverage, crosses ~0.5 at the ceiling, and decays toward
    0 as leverage blows past it. Infinite leverage (non-positive combined EBITDA)
    scores 0.
    """
    lev = pro_forma_leverage(acquirer, target, cfg.default_premium, cfg)
    if not math.isfinite(lev):
        return 0.0, lev
    ceiling = cfg.leverage_ceiling
    # logistic centered at the ceiling; higher leverage -> lower score
    score = _sigmoid((ceiling - lev) / (0.35 * ceiling))
    return score, lev


def score_candidates(acquirer: Company, candidates: list[Company],
                     cfg: Config = DEFAULT_CONFIG) -> list[FinancialScore]:
    scores = []
    for c in candidates:
        margin = margin_accretion_score(acquirer, c)
        fund, lev = fundability_score(acquirer, c, cfg)
        financial = 0.5 * margin + 0.5 * fund
        scores.append(FinancialScore(
            ticker=c.ticker, margin_accretion=margin, fundability=fund,
            financial_score=financial, pro_forma_leverage=lev,
        ))
    return scores
