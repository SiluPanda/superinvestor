from __future__ import annotations

import aiosqlite

from superinvestor.models import Filing, FilingDiff, FilingSection
from superinvestor.store.base import BaseStore


class FilingStore(BaseStore[Filing]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, Filing, "filings")

    async def get_by_ticker(self, ticker: str, filing_type: str | None = None) -> list[Filing]:
        if filing_type:
            return await self.query(
                where="ticker = ? AND filing_type = ?",
                params=(ticker.upper(), filing_type),
                order_by="filed_date DESC",
            )
        return await self.query(
            where="ticker = ?",
            params=(ticker.upper(),),
            order_by="filed_date DESC",
        )

    async def get_by_accession(self, accession: str) -> Filing | None:
        results = await self.query(where="accession_number = ?", params=(accession,), limit=1)
        return results[0] if results else None


class FilingSectionStore(BaseStore[FilingSection]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, FilingSection, "filing_sections")

    async def get_for_filing(self, filing_id: str) -> list[FilingSection]:
        return await self.query(
            where="filing_id = ?",
            params=(filing_id,),
            order_by="order_index ASC",
        )


class FilingDiffStore(BaseStore[FilingDiff]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, FilingDiff, "filing_diffs")

    async def get_for_filing(self, filing_id_new: str) -> list[FilingDiff]:
        return await self.query(
            where="filing_id_new = ?",
            params=(filing_id_new,),
            order_by="section_name ASC",
        )
