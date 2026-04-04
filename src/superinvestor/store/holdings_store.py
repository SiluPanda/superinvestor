from __future__ import annotations

from datetime import date, timedelta

import aiosqlite

from superinvestor.models import (
    Holding13F,
    HoldingChange,
    InsiderTrade,
    SuperInvestorProfile,
)
from superinvestor.store.base import BaseStore


class SuperInvestorStore(BaseStore[SuperInvestorProfile]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, SuperInvestorProfile, "super_investor_profiles")

    async def get_by_cik(self, cik: str) -> SuperInvestorProfile | None:
        results = await self.query(where="cik = ?", params=(cik,), limit=1)
        return results[0] if results else None


class Holdings13FStore(BaseStore[Holding13F]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Holding13F, "holdings_13f")

    async def get_by_investor_and_date(
        self, investor_id: str, report_date: date
    ) -> list[Holding13F]:
        return await self.query(
            where="investor_id = ? AND report_date = ?",
            params=(investor_id, report_date.isoformat()),
            order_by="value_usd DESC",
            limit=10000,
        )

    async def get_latest_for_investor(self, investor_id: str) -> list[Holding13F]:
        """Return all holdings from the investor's most recent report date."""
        # First find the most recent report date for this investor.
        cursor = await self._db.execute(
            "SELECT MAX(report_date) FROM holdings_13f WHERE investor_id = ?",
            (investor_id,),
        )
        row = await cursor.fetchone()
        if not row or row[0] is None:
            return []
        latest_date = row[0]
        return await self.query(
            where="investor_id = ? AND report_date = ?",
            params=(investor_id, latest_date),
            order_by="value_usd DESC",
            limit=10000,
        )


class HoldingChangeStore(BaseStore[HoldingChange]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, HoldingChange, "holding_changes")

    async def get_recent_changes(self, investor_id: str, limit: int = 50) -> list[HoldingChange]:
        return await self.query(
            where="investor_id = ?",
            params=(investor_id,),
            order_by="report_date DESC",
            limit=limit,
        )

    async def get_by_ticker(self, ticker: str) -> list[HoldingChange]:
        return await self.query(
            where="ticker = ?",
            params=(ticker.upper(),),
            order_by="report_date DESC",
        )


class InsiderTradeStore(BaseStore[InsiderTrade]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, InsiderTrade, "insider_trades")

    async def get_by_ticker(self, ticker: str, months: int = 12) -> list[InsiderTrade]:
        cutoff = (date.today() - timedelta(days=months * 30)).isoformat()
        return await self.query(
            where="ticker = ? AND trade_date >= ?",
            params=(ticker.upper(), cutoff),
            order_by="trade_date DESC",
        )
