from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .base import SuperInvestorBase
from .enums import AlertPriority, SignalSource, SignalStrength


class Signal(SuperInvestorBase):
    ticker: str
    source: SignalSource
    strength: SignalStrength
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    data_refs: list[str] = Field(default_factory=list)
    confidence: float
    expires_at: datetime | None = None


class Alert(SuperInvestorBase):
    signal_id: str | None = None
    ticker: str
    priority: AlertPriority
    title: str
    message: str
    read: bool = False
    dismissed: bool = False
