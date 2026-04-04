from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import ConfigDict

from .base import SuperInvestorBase
from .enums import TradeAction, TradeStatus


class Portfolio(SuperInvestorBase):
    model_config = ConfigDict(
        frozen=False,
        str_strip_whitespace=True,
    )

    name: str
    initial_cash: Decimal
    cash: Decimal
    description: str = ""


class Position(SuperInvestorBase):
    portfolio_id: str
    ticker: str
    shares: Decimal
    avg_cost_basis: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal


class Trade(SuperInvestorBase):
    portfolio_id: str
    ticker: str
    action: TradeAction
    status: TradeStatus = TradeStatus.FILLED
    shares: Decimal
    price: Decimal
    total_value: Decimal
    thesis_id: str | None = None
    notes: str = ""


class PnLSnapshot(SuperInvestorBase):
    portfolio_id: str
    snapshot_date: date
    total_value: Decimal
    cash: Decimal
    invested_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    daily_return_pct: Decimal
