"""Deal structure: purchase price + sources & uses.

Purchase price:
    offer_price_per_share   = target_share_price * (1 + premium)
    equity_purchase_price   = offer_price_per_share * target_shares_diluted
    enterprise_purchase_price = equity_purchase_price + target_net_debt

Sources & uses (consideration mix is config: %cash, %stock, %new_debt):
    Uses    = equity_purchase_price + [refinanced target debt] + transaction_fees
    new_debt          = %new_debt * total_uses
    acquirer_cash     = %cash     * total_uses
    new_equity_issued = %stock    * total_uses
    new_shares        = new_equity_issued / acquirer_share_price

Sources must equal uses (asserted).
"""
from __future__ import annotations

from ..config import Config, DEFAULT_CONFIG
from ..models import Company, DealStructure


def build_structure(acquirer: Company, target: Company,
                    premium: float | None = None,
                    cash_pct: float | None = None,
                    stock_pct: float | None = None,
                    new_debt_pct: float | None = None,
                    cfg: Config = DEFAULT_CONFIG) -> DealStructure:
    premium = cfg.default_premium if premium is None else premium
    cash_pct = cfg.cash_pct if cash_pct is None else cash_pct
    stock_pct = cfg.stock_pct if stock_pct is None else stock_pct
    new_debt_pct = cfg.new_debt_pct if new_debt_pct is None else new_debt_pct

    mix_sum = cash_pct + stock_pct + new_debt_pct
    if abs(mix_sum - 1.0) > 1e-6:
        raise ValueError(f"Consideration mix must sum to 1.0, got {mix_sum:.4f}")

    offer_price_per_share = target.share_price * (1 + premium)
    equity_purchase_price = offer_price_per_share * target.shares_diluted
    enterprise_purchase_price = equity_purchase_price + target.net_debt

    transaction_fees = cfg.fee_pct * equity_purchase_price
    refinanced_debt = target.total_debt if cfg.refinance_target_debt else 0.0
    total_uses = equity_purchase_price + refinanced_debt + transaction_fees

    new_debt = new_debt_pct * total_uses
    acquirer_cash_used = cash_pct * total_uses
    new_equity_issued = stock_pct * total_uses

    total_sources = new_debt + acquirer_cash_used + new_equity_issued
    assert abs(total_sources - total_uses) < 1e-6, "Sources must equal uses"

    new_shares_issued = (new_equity_issued / acquirer.share_price) if acquirer.share_price else 0.0

    return DealStructure(
        offer_price_per_share=offer_price_per_share,
        premium=premium,
        equity_purchase_price=equity_purchase_price,
        target_net_debt=target.net_debt,
        enterprise_purchase_price=enterprise_purchase_price,
        transaction_fees=transaction_fees,
        refinanced_debt=refinanced_debt,
        total_uses=total_uses,
        new_debt=new_debt,
        acquirer_cash_used=acquirer_cash_used,
        new_equity_issued=new_equity_issued,
        new_shares_issued=new_shares_issued,
        cash_pct=cash_pct,
        stock_pct=stock_pct,
        new_debt_pct=new_debt_pct,
    )
