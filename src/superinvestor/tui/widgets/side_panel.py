from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

import aiosqlite
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Collapsible, DataTable

from superinvestor.store.analysis_store import AnalysisStore
from superinvestor.store.thesis_store import ThesisStore
from superinvestor.store.watchlist_store import WatchlistStore

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SidePanel(Vertical):
    """Right side panel with watchlist, theses, and recent analyses."""

    DEFAULT_CSS = """
    SidePanel {
        width: 36;
        border-left: solid $surface-lighten-2;
        padding: 1 0;
    }
    SidePanel DataTable {
        height: auto;
        max-height: 12;
    }
    """

    def compose(self) -> ComposeResult:
        with Collapsible(title="Watchlist", collapsed=False):
            yield DataTable(id="watchlist-panel")
        with Collapsible(title="Saved Theses", collapsed=False):
            yield DataTable(id="theses-panel")
        with Collapsible(title="Recent Analyses", collapsed=False):
            yield DataTable(id="analyses-panel")

    def _table(self, selector: str) -> DataTable[Any]:
        return self.query_one(selector, DataTable)  # pyright: ignore[reportUnknownVariableType]

    def on_mount(self) -> None:
        wt = self._table("#watchlist-panel")
        wt.add_columns("Ticker", "Notes")
        wt.cursor_type = "row"
        wt.show_header = True
        wt.zebra_stripes = True

        tt = self._table("#theses-panel")
        tt.add_columns("Ticker", "Title", "Conf")
        tt.cursor_type = "row"
        tt.show_header = True
        tt.zebra_stripes = True

        at = self._table("#analyses-panel")
        at.add_columns("Date", "Ticker", "Type")
        at.cursor_type = "row"
        at.show_header = True
        at.zebra_stripes = True

    async def refresh_data(self, db: aiosqlite.Connection) -> None:
        """Reload all sections from the database."""
        await self._load_watchlist(db)
        await self._load_theses(db)
        await self._load_analyses(db)

    async def _load_watchlist(self, db: aiosqlite.Connection) -> None:
        try:
            store = WatchlistStore(db)
            items = await store.get_all()
            table = self._table("#watchlist-panel")
            table.clear()
            for item in items:
                table.add_row(item.ticker, item.notes[:20] if item.notes else "")
        except Exception:
            logger.debug("Failed to load watchlist", exc_info=True)

    async def _load_theses(self, db: aiosqlite.Connection) -> None:
        try:
            store = ThesisStore(db)
            theses = await store.get_all_active()
            table = self._table("#theses-panel")
            table.clear()
            for t in theses[:10]:
                table.add_row(t.ticker, t.title[:18], f"{t.confidence_score:.0%}")
        except Exception:
            logger.debug("Failed to load theses", exc_info=True)

    async def _load_analyses(self, db: aiosqlite.Connection) -> None:
        try:
            store = AnalysisStore(db)
            results = await store.query(order_by="created_at DESC", limit=10)
            table = self._table("#analyses-panel")
            table.clear()
            for r in results:
                table.add_row(
                    r.created_at.strftime("%m-%d %H:%M"),
                    r.ticker,
                    r.analysis_type[:10],
                )
        except Exception:
            logger.debug("Failed to load analyses", exc_info=True)
