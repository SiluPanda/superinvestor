from __future__ import annotations

import aiosqlite

from superinvestor.models import AnalysisResult, ReasoningStep
from superinvestor.store.base import BaseStore


class AnalysisStore(BaseStore[AnalysisResult]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, AnalysisResult, "analysis_results")

    async def get_recent(self, ticker: str, limit: int = 10) -> list[AnalysisResult]:
        return await self.query(
            where="ticker = ?",
            params=(ticker.upper(),),
            order_by="created_at DESC",
            limit=limit,
        )


class ReasoningStepStore(BaseStore[ReasoningStep]):
    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__(db, ReasoningStep, "reasoning_steps")

    async def get_for_analysis(self, analysis_id: str) -> list[ReasoningStep]:
        return await self.query(
            where="analysis_id = ?",
            params=(analysis_id,),
            order_by="step_number ASC",
            limit=10000,
        )
