from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from .base import SuperInvestorBase
from .enums import ThesisStatus


class InvestmentThesis(SuperInvestorBase):
    ticker: str
    title: str
    status: ThesisStatus = ThesisStatus.ACTIVE
    bull_case: str
    bear_case: str
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    target_price: Decimal | None = None
    entry_price: Decimal | None = None
    time_horizon_months: int | None = None
    confidence_score: float = 0.5


class ThesisUpdate(SuperInvestorBase):
    thesis_id: str
    trigger: str
    observation: str
    impact: str
    confidence_delta: float = 0.0
    new_status: ThesisStatus | None = None
