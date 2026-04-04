from __future__ import annotations

from pydantic import Field

from .base import SuperInvestorBase


class WatchlistItem(SuperInvestorBase):
    ticker: str
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    thesis_id: str | None = None
