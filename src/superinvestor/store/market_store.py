from __future__ import annotations

from datetime import date

import aiosqlite

from superinvestor.models import CompanyNews, EarningsEvent, OHLCV, Quote, Stock
from superinvestor.store.base import BaseStore


class StockStore(BaseStore[Stock]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Stock, "stocks")

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        results = await self.query(where="ticker = ?", params=(ticker.upper(),), limit=1)
        return results[0] if results else None

    async def search(self, query: str) -> list[Stock]:
        pattern = f"%{query}%"
        return await self.query(
            where="ticker LIKE ? OR name LIKE ?",
            params=(pattern, pattern),
            order_by="ticker ASC",
        )


class QuoteStore(BaseStore[Quote]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Quote, "quotes")

    async def get_latest(self, ticker: str) -> Quote | None:
        results = await self.query(
            where="ticker = ?",
            params=(ticker.upper(),),
            order_by="timestamp DESC",
            limit=1,
        )
        return results[0] if results else None


class OHLCVStore(BaseStore[OHLCV]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, OHLCV, "ohlcv")

    async def get_range(
        self,
        ticker: str,
        start: date,
        end: date,
        timespan: str,
    ) -> list[OHLCV]:
        return await self.query(
            where="ticker = ? AND timespan = ? AND timestamp >= ? AND timestamp <= ?",
            params=(ticker.upper(), timespan, start.isoformat(), f"{end.isoformat()}T23:59:59"),
            order_by="timestamp ASC",
            limit=10000,
        )


class EarningsEventStore(BaseStore[EarningsEvent]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, EarningsEvent, "earnings_events")

    async def get_by_ticker(self, ticker: str) -> list[EarningsEvent]:
        return await self.query(
            where="ticker = ?",
            params=(ticker.upper(),),
            order_by="report_date DESC",
        )


class NewsStore(BaseStore[CompanyNews]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, CompanyNews, "company_news")

    async def get_recent(self, ticker: str, limit: int = 20) -> list[CompanyNews]:
        return await self.query(
            where="ticker = ?",
            params=(ticker.upper(),),
            order_by="published_at DESC",
            limit=limit,
        )
