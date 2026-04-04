from __future__ import annotations

import aiosqlite

from superinvestor.models import InvestmentThesis, ThesisUpdate
from superinvestor.models.enums import ThesisStatus
from superinvestor.store.base import BaseStore


class ThesisStore(BaseStore[InvestmentThesis]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, InvestmentThesis, "investment_theses")

    async def get_active(self, ticker: str) -> list[InvestmentThesis]:
        return await self.query(
            where="ticker = ? AND status = ?",
            params=(ticker.upper(), ThesisStatus.ACTIVE.value),
            order_by="created_at DESC",
        )

    async def get_all_active(self) -> list[InvestmentThesis]:
        return await self.query(
            where="status = ?",
            params=(ThesisStatus.ACTIVE.value,),
            order_by="created_at DESC",
            limit=1000,
        )


class ThesisUpdateStore(BaseStore[ThesisUpdate]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, ThesisUpdate, "thesis_updates")

    async def get_for_thesis(self, thesis_id: str) -> list[ThesisUpdate]:
        return await self.query(
            where="thesis_id = ?",
            params=(thesis_id,),
            order_by="created_at DESC",
        )
