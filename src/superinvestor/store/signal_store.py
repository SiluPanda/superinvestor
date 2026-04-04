from __future__ import annotations

import aiosqlite

from superinvestor.models import Alert, Signal
from superinvestor.store.base import BaseStore


class SignalStore(BaseStore[Signal]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Signal, "signals")

    async def get_recent(self, ticker: str, limit: int = 50) -> list[Signal]:
        return await self.query(
            where="ticker = ?",
            params=(ticker.upper(),),
            order_by="created_at DESC",
            limit=limit,
        )

    async def get_by_source(self, source: str) -> list[Signal]:
        return await self.query(
            where="source = ?",
            params=(source,),
            order_by="created_at DESC",
        )


class AlertStore(BaseStore[Alert]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Alert, "alerts")

    async def get_unread(self) -> list[Alert]:
        return await self.query(
            where="read = 0 AND dismissed = 0",
            order_by="created_at DESC",
            limit=1000,
        )

    async def mark_read(self, id: str) -> bool:
        return await self.update_by_id(id, read=True)

    async def mark_dismissed(self, id: str) -> bool:
        return await self.update_by_id(id, dismissed=True)
