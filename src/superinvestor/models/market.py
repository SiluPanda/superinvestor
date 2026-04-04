from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal


from .base import SuperInvestorBase
from .enums import Exchange, Timespan


class Stock(SuperInvestorBase):
    ticker: str
    name: str
    exchange: Exchange
    sector: str = ""
    industry: str = ""
    market_cap: Decimal = Decimal("0")
    shares_outstanding: Decimal = Decimal("0")
    cik: str = ""
    active: bool = True


class Quote(SuperInvestorBase):
    ticker: str
    price: Decimal
    change: Decimal
    change_percent: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    previous_close: Decimal
    volume: int
    timestamp: datetime


class OHLCV(SuperInvestorBase):
    ticker: str
    timestamp: datetime
    timespan: Timespan
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap: Decimal = Decimal("0")
    num_trades: int = 0


class CompanyNews(SuperInvestorBase):
    ticker: str
    headline: str
    summary: str
    source: str
    url: str
    published_at: datetime
    category: str
    sentiment_score: Decimal | None = None


class EarningsEvent(SuperInvestorBase):
    ticker: str
    report_date: date
    fiscal_year: int
    fiscal_quarter: int
    eps_estimate: Decimal | None = None
    eps_actual: Decimal | None = None
    revenue_estimate: Decimal | None = None
    revenue_actual: Decimal | None = None
