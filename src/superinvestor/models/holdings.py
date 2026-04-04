from __future__ import annotations

from datetime import date
from decimal import Decimal

from .base import SuperInvestorBase
from .enums import HoldingChangeType, InsiderTradeType


class SuperInvestorProfile(SuperInvestorBase):
    cik: str
    name: str
    short_name: str = ""
    manager_name: str = ""
    aum: Decimal = Decimal("0")
    active: bool = True
    notes: str = ""


class Holding13F(SuperInvestorBase):
    investor_id: str
    filing_accession: str
    report_date: date
    ticker: str
    company_name: str
    cusip: str
    value_usd: Decimal
    shares: int
    share_type: str = "SH"
    investment_discretion: str = "SOLE"


class HoldingChange(SuperInvestorBase):
    investor_id: str
    ticker: str
    report_date: date
    prev_report_date: date | None = None
    change_type: HoldingChangeType
    shares_before: int = 0
    shares_after: int = 0
    shares_change: int = 0
    shares_change_pct: Decimal = Decimal("0")
    value_before: Decimal = Decimal("0")
    value_after: Decimal = Decimal("0")
    portfolio_pct: Decimal = Decimal("0")


class InsiderTrade(SuperInvestorBase):
    ticker: str
    cik: str
    insider_cik: str
    insider_name: str
    insider_title: str
    trade_type: InsiderTradeType
    trade_date: date
    shares: int
    price_per_share: Decimal
    total_value: Decimal
    shares_owned_after: int = 0
