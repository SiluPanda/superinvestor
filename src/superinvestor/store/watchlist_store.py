from __future__ import annotations

import aiosqlite

from superinvestor.models import WatchlistItem
from superinvestor.store.base import BaseStore


class WatchlistStore(BaseStore[WatchlistItem]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, WatchlistItem, "watchlist_items")

    async def get_all(self) -> list[WatchlistItem]:
        return await self.query(order_by="created_at DESC", limit=10000)

    async def get_by_ticker(self, ticker: str) -> WatchlistItem | None:
        results = await self.query(where="ticker = ?", params=(ticker.upper(),), limit=1)
        return results[0] if results else None

    async def exists(self, ticker: str) -> bool:
        cnt = await self.count(where="ticker = ?", params=(ticker.upper(),))
        return cnt > 0
