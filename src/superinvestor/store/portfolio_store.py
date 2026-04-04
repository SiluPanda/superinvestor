from __future__ import annotations

import aiosqlite

from superinvestor.models import PnLSnapshot, Portfolio, Position, Trade
from superinvestor.store.base import BaseStore


class PortfolioStore(BaseStore[Portfolio]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Portfolio, "portfolios")


class PositionStore(BaseStore[Position]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Position, "positions")

    async def get_for_portfolio(self, portfolio_id: str) -> list[Position]:
        return await self.query(
            where="portfolio_id = ?",
            params=(portfolio_id,),
            order_by="market_value DESC",
            limit=10000,
        )

    async def get_by_ticker(self, portfolio_id: str, ticker: str) -> Position | None:
        results = await self.query(
            where="portfolio_id = ? AND ticker = ?",
            params=(portfolio_id, ticker.upper()),
            limit=1,
        )
        return results[0] if results else None


class TradeStore(BaseStore[Trade]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Trade, "trades")

    async def get_for_portfolio(self, portfolio_id: str, limit: int = 100) -> list[Trade]:
        return await self.query(
            where="portfolio_id = ?",
            params=(portfolio_id,),
            order_by="created_at DESC",
            limit=limit,
        )


class PnLSnapshotStore(BaseStore[PnLSnapshot]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, PnLSnapshot, "pnl_snapshots")

    async def get_for_portfolio(self, portfolio_id: str, limit: int = 365) -> list[PnLSnapshot]:
        return await self.query(
            where="portfolio_id = ?",
            params=(portfolio_id,),
            order_by="snapshot_date DESC",
            limit=limit,
        )
