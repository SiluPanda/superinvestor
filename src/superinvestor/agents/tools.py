from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from superinvestor.data.edgar import EdgarProvider
from superinvestor.data.fred import FredProvider
from superinvestor.data.polygon import PolygonProvider
from superinvestor.models.enums import FilingType, Timespan


class DomainTools:
    """Domain tools that wrap data providers for use by AI agents.

    Each method is a tool callable by an agent. The TOOL_SCHEMAS class var
    provides the JSON schema definitions for tool use APIs.
    """

    def __init__(
        self,
        polygon: PolygonProvider,
        edgar: EdgarProvider,
        fred: FredProvider,
        db_path: Path | None = None,
    ) -> None:
        self._polygon = polygon
        self._edgar = edgar
        self._fred = fred
        self._db_path = db_path

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> str:
        """Dispatch a tool call by name. Returns JSON string result."""
        handler = getattr(self, tool_name, None)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = await handler(**args)
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            logger.warning("Tool %s failed: %s", tool_name, e, exc_info=True)
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------
    # Market data tools
    # ------------------------------------------------------------------

    async def get_stock_quote(self, ticker: str) -> str:
        """Get the latest stock quote including price, change, and volume."""
        quote = await self._polygon.get_quote(ticker)
        return quote.model_dump_json()

    async def get_stock_details(self, ticker: str) -> str:
        """Get company details including sector, market cap, and shares outstanding."""
        stock = await self._polygon.get_stock(ticker)
        return stock.model_dump_json()

    async def get_price_history(
        self,
        ticker: str,
        timespan: str = "day",
        from_date: str = "",
        to_date: str = "",
        limit: int = 365,
    ) -> str:
        """Get historical OHLCV price bars for a stock."""
        ts = Timespan(timespan) if timespan in Timespan.__members__.values() else Timespan.DAY
        bars = await self._polygon.get_ohlcv(
            ticker,
            timespan=ts,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
        return json.dumps([b.model_dump(mode="json") for b in bars[:limit]])

    async def get_news(self, ticker: str, limit: int = 15) -> str:
        """Get recent news articles with sentiment scores for a stock."""
        news = await self._polygon.get_news(ticker, limit=limit)
        return json.dumps([n.model_dump(mode="json") for n in news])

    async def search_tickers(self, query: str) -> str:
        """Search for stock tickers by company name or ticker symbol."""
        results = await self._polygon.search_tickers(query, limit=10)
        return json.dumps([s.model_dump(mode="json") for s in results])

    # ------------------------------------------------------------------
    # SEC filing tools
    # ------------------------------------------------------------------

    async def get_sec_filings(
        self,
        ticker: str,
        filing_type: str = "",
        limit: int = 10,
    ) -> str:
        """Get recent SEC filings (10-K, 10-Q, 8-K) for a company."""
        cik = await self._edgar.lookup_cik(ticker)
        ft = None
        if filing_type:
            try:
                ft = FilingType(filing_type)
            except ValueError:
                pass
        filings = await self._edgar.get_company_filings(cik, filing_type=ft, limit=limit)
        return json.dumps([f.model_dump(mode="json") for f in filings])

    async def get_filing_text(self, url: str) -> str:
        """Download and return the text content of an SEC filing document."""
        text = await self._edgar.get_filing_text(url)
        # Truncate to avoid overwhelming the context
        if len(text) > 50000:
            return text[:50000] + "\n\n[TRUNCATED — full filing is longer]"
        return text

    async def get_company_financials(self, ticker: str) -> str:
        """Get XBRL financial facts (revenue, net income, etc.) from SEC filings."""
        cik = await self._edgar.lookup_cik(ticker)
        facts = await self._edgar.get_company_facts(cik)
        # Return a summary of key metrics
        summary: dict[str, list[dict[str, Any]]] = {}
        key_concepts = [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "NetIncomeLoss",
            "EarningsPerShareDiluted",
            "Assets",
            "Liabilities",
            "StockholdersEquity",
            "OperatingIncomeLoss",
            "CashAndCashEquivalentsAtCarryingValue",
            "LongTermDebt",
            "CommonStockSharesOutstanding",
        ]
        for concept in key_concepts:
            if concept in facts:
                entries = facts[concept][-8:]  # Last 8 periods
                summary[concept] = [
                    {
                        "value": str(e.value),
                        "end_date": e.end_date.isoformat(),
                        "fiscal_year": e.fiscal_year,
                        "period": e.fiscal_period,
                        "form": e.form,
                    }
                    for e in entries
                ]
        return json.dumps(summary)

    # ------------------------------------------------------------------
    # Superinvestor / 13F tools
    # ------------------------------------------------------------------

    async def get_superinvestor_holdings(
        self, investor_cik: str, accession_number: str, report_date: str | None = None
    ) -> str:
        """Get 13F holdings for a superinvestor from a specific filing."""
        parsed_date = date.fromisoformat(report_date) if report_date else None
        holdings = await self._edgar.get_13f_holdings(
            investor_cik, accession_number, report_date=parsed_date
        )
        return json.dumps([h.model_dump(mode="json") for h in holdings])

    async def get_recent_13f_filings(self, investor_cik: str, limit: int = 4) -> str:
        """Get the most recent 13F-HR filings for an institutional investor."""
        filings = await self._edgar.get_recent_13f_accessions(investor_cik, limit=limit)
        return json.dumps([f.model_dump(mode="json") for f in filings])

    # ------------------------------------------------------------------
    # Economic data tools
    # ------------------------------------------------------------------

    async def get_economic_indicator(self, series_id: str, limit: int = 12) -> str:
        """Get recent observations for a FRED economic indicator (e.g., GDP, UNRATE, DFF)."""
        obs = await self._fred.get_observations(series_id, limit=limit)
        return json.dumps(
            [
                {"date": o.date.isoformat(), "value": str(o.value) if o.value is not None else None}
                for o in obs
            ]
        )

    async def get_economic_snapshot(self) -> str:
        """Get latest values for key economic indicators (GDP, unemployment, fed funds rate, CPI, etc.)."""
        snapshot = await self._fred.get_economic_snapshot()
        result: dict[str, str | None] = {}
        for sid, obs in snapshot.items():
            result[sid] = str(obs.value) if obs and obs.value is not None else None
        return json.dumps(result)

    # ------------------------------------------------------------------
    # Storage tools (watchlist, thesis)
    # ------------------------------------------------------------------

    async def add_to_watchlist(
        self, ticker: str, notes: str = "", tags: list[str] | None = None
    ) -> str:
        """Add a ticker to the user's watchlist with optional notes and tags."""
        if self._db_path is None:
            return json.dumps({"error": "Database not configured"})
        from superinvestor.models.watchlist import WatchlistItem
        from superinvestor.store.db import Database
        from superinvestor.store.watchlist_store import WatchlistStore

        t = ticker.upper().strip()
        db = Database(self._db_path)
        try:
            await db.connect()
            store = WatchlistStore(db.conn)
            if await store.exists(t):
                return json.dumps({"success": False, "message": f"{t} is already on the watchlist"})
            await store.insert(WatchlistItem(ticker=t, notes=notes, tags=tags or []))
            return json.dumps({"success": True, "ticker": t, "message": f"Added {t} to watchlist"})
        finally:
            await db.close()

    async def remove_from_watchlist(self, ticker: str) -> str:
        """Remove a ticker from the user's watchlist."""
        if self._db_path is None:
            return json.dumps({"error": "Database not configured"})
        from superinvestor.store.db import Database
        from superinvestor.store.watchlist_store import WatchlistStore

        t = ticker.upper().strip()
        db = Database(self._db_path)
        try:
            await db.connect()
            store = WatchlistStore(db.conn)
            item = await store.get_by_ticker(t)
            if item is None:
                return json.dumps({"success": False, "message": f"{t} is not on the watchlist"})
            await store.delete_by_id(item.id)
            return json.dumps({"success": True, "ticker": t, "message": f"Removed {t} from watchlist"})
        finally:
            await db.close()

    async def get_watchlist(self) -> str:
        """Get all tickers currently on the user's watchlist."""
        if self._db_path is None:
            return json.dumps({"error": "Database not configured"})
        from superinvestor.store.db import Database
        from superinvestor.store.watchlist_store import WatchlistStore

        db = Database(self._db_path)
        try:
            await db.connect()
            store = WatchlistStore(db.conn)
            items = await store.get_all()
            return json.dumps([
                {"id": i.id, "ticker": i.ticker, "notes": i.notes, "tags": i.tags}
                for i in items
            ])
        finally:
            await db.close()

    async def save_thesis(
        self,
        ticker: str,
        title: str,
        bull_case: str,
        bear_case: str,
        catalysts: list[str] | None = None,
        risks: list[str] | None = None,
        target_price: str | None = None,
        time_horizon_months: int | None = None,
        confidence_score: float = 0.5,
    ) -> str:
        """Save an investment thesis for a ticker."""
        if self._db_path is None:
            return json.dumps({"error": "Database not configured"})
        from decimal import Decimal, InvalidOperation

        from superinvestor.models.thesis import InvestmentThesis
        from superinvestor.store.db import Database
        from superinvestor.store.thesis_store import ThesisStore

        db = Database(self._db_path)
        try:
            await db.connect()
            store = ThesisStore(db.conn)
            try:
                tp = Decimal(target_price) if target_price else None
            except InvalidOperation:
                return json.dumps({"error": f"Invalid target_price: {target_price!r}"})
            thesis = InvestmentThesis(
                ticker=ticker.upper().strip(),
                title=title,
                bull_case=bull_case,
                bear_case=bear_case,
                catalysts=catalysts or [],
                risks=risks or [],
                target_price=tp,
                time_horizon_months=time_horizon_months,
                confidence_score=max(0.0, min(1.0, confidence_score)),
            )
            await store.insert(thesis)
            return json.dumps({
                "success": True,
                "thesis_id": thesis.id,
                "ticker": thesis.ticker,
                "message": f"Thesis '{title}' saved for {thesis.ticker}",
            })
        finally:
            await db.close()

    async def update_thesis(
        self,
        thesis_id: str,
        status: str | None = None,
        title: str | None = None,
        bull_case: str | None = None,
        bear_case: str | None = None,
        catalysts: list[str] | None = None,
        risks: list[str] | None = None,
        target_price: str | None = None,
        confidence_score: float | None = None,
        time_horizon_months: int | None = None,
    ) -> str:
        """Update one or more fields of an existing investment thesis."""
        if self._db_path is None:
            return json.dumps({"error": "Database not configured"})
        from superinvestor.store.db import Database
        from superinvestor.store.thesis_store import ThesisStore

        updates: dict[str, object] = {}
        if status is not None:
            updates["status"] = status
        if title is not None:
            updates["title"] = title
        if bull_case is not None:
            updates["bull_case"] = bull_case
        if bear_case is not None:
            updates["bear_case"] = bear_case
        if catalysts is not None:
            updates["catalysts"] = catalysts
        if risks is not None:
            updates["risks"] = risks
        if target_price is not None:
            updates["target_price"] = target_price
        if confidence_score is not None:
            updates["confidence_score"] = max(0.0, min(1.0, confidence_score))
        if time_horizon_months is not None:
            updates["time_horizon_months"] = time_horizon_months

        if not updates:
            return json.dumps({"success": False, "message": "No fields to update were provided"})

        db = Database(self._db_path)
        try:
            await db.connect()
            store = ThesisStore(db.conn)
            ok = await store.update_by_id(thesis_id, **updates)
            if not ok:
                return json.dumps({"success": False, "message": f"Thesis {thesis_id!r} not found"})
            return json.dumps({
                "success": True,
                "thesis_id": thesis_id,
                "updated_fields": list(updates.keys()),
            })
        finally:
            await db.close()

    async def delete_thesis(self, thesis_id: str) -> str:
        """Permanently delete an investment thesis by its ID."""
        if self._db_path is None:
            return json.dumps({"error": "Database not configured"})
        from superinvestor.store.db import Database
        from superinvestor.store.thesis_store import ThesisStore

        db = Database(self._db_path)
        try:
            await db.connect()
            store = ThesisStore(db.conn)
            ok = await store.delete_by_id(thesis_id)
            if not ok:
                return json.dumps({"success": False, "message": f"Thesis {thesis_id!r} not found"})
            return json.dumps({"success": True, "thesis_id": thesis_id, "message": "Thesis deleted"})
        finally:
            await db.close()

    async def list_theses(self, ticker: str | None = None) -> str:
        """List saved investment theses, optionally filtered by ticker."""
        if self._db_path is None:
            return json.dumps({"error": "Database not configured"})
        from superinvestor.store.db import Database
        from superinvestor.store.thesis_store import ThesisStore

        db = Database(self._db_path)
        try:
            await db.connect()
            store = ThesisStore(db.conn)
            if ticker:
                items = await store.get_active(ticker.upper().strip())
            else:
                items = await store.get_all_active()
            return json.dumps([
                {
                    "id": t.id,
                    "ticker": t.ticker,
                    "title": t.title,
                    "status": t.status.value,
                    "confidence_score": t.confidence_score,
                    "target_price": str(t.target_price) if t.target_price else None,
                    "time_horizon_months": t.time_horizon_months,
                    "created_at": t.created_at.isoformat(),
                }
                for t in items
            ])
        finally:
            await db.close()


# ------------------------------------------------------------------
# Tool schemas for the Anthropic Messages API
# ------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_stock_quote",
        "description": "Get the latest stock quote including price, change, volume, and VWAP.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g., AAPL)"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_stock_details",
        "description": "Get company details including name, sector, market cap, shares outstanding, and exchange.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_price_history",
        "description": "Get historical OHLCV price bars. Use for technical analysis, trend identification, and price pattern detection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "timespan": {
                    "type": "string",
                    "enum": ["minute", "hour", "day", "week", "month"],
                    "description": "Bar timespan (default: day)",
                },
                "from_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD (default: 1 year ago)",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date YYYY-MM-DD (default: today)",
                },
                "limit": {"type": "integer", "description": "Max bars to return (default: 365)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_news",
        "description": "Get recent news articles with sentiment scores for a stock. Useful for sentiment analysis and event-driven insights.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "limit": {"type": "integer", "description": "Number of articles (default: 15)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_sec_filings",
        "description": "Get recent SEC filings (10-K, 10-Q, 8-K, etc.) for a company. Returns filing metadata with URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "filing_type": {
                    "type": "string",
                    "description": "Filter by type: 10-K, 10-Q, 8-K (optional)",
                },
                "limit": {"type": "integer", "description": "Max filings to return (default: 10)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_filing_text",
        "description": "Download the full text content of an SEC filing. Use after get_sec_filings to read a specific filing.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL of the filing document"}},
            "required": ["url"],
        },
    },
    {
        "name": "get_company_financials",
        "description": "Get key financial metrics from SEC XBRL data: revenue, net income, EPS, assets, debt, cash, equity. Returns last 8 reporting periods.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_economic_indicator",
        "description": "Get recent observations for a FRED economic indicator. Common IDs: GDP, UNRATE (unemployment), DFF (fed funds rate), CPIAUCSL (CPI), T10Y2Y (yield curve), VIXCLS (VIX), SP500.",
        "input_schema": {
            "type": "object",
            "properties": {
                "series_id": {
                    "type": "string",
                    "description": "FRED series ID (e.g., GDP, UNRATE, DFF)",
                },
                "limit": {"type": "integer", "description": "Number of observations (default: 12)"},
            },
            "required": ["series_id"],
        },
    },
    {
        "name": "get_economic_snapshot",
        "description": "Get latest values for key economic indicators: GDP, unemployment rate, fed funds rate, CPI, yield curve, VIX, S&P 500, oil price.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_recent_13f_filings",
        "description": "Get the most recent 13F-HR filings for an institutional investor (e.g., Berkshire Hathaway). Returns filing metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "investor_cik": {
                    "type": "string",
                    "description": "CIK of the institutional investor",
                },
                "limit": {"type": "integer", "description": "Number of filings (default: 4)"},
            },
            "required": ["investor_cik"],
        },
    },
    {
        "name": "get_superinvestor_holdings",
        "description": "Get the full list of holdings from a specific 13F filing. Use after get_recent_13f_filings to examine a specific quarter's portfolio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "investor_cik": {
                    "type": "string",
                    "description": "CIK of the institutional investor",
                },
                "accession_number": {
                    "type": "string",
                    "description": "SEC accession number of the 13F filing",
                },
                "report_date": {
                    "type": "string",
                    "description": "Filing period date in YYYY-MM-DD format (from period_of_report in filing metadata)",
                },
            },
            "required": ["investor_cik", "accession_number"],
        },
    },
    {
        "name": "search_tickers",
        "description": "Search for stock tickers by company name or partial ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (company name or ticker)"}
            },
            "required": ["query"],
        },
    },
    # ------------------------------------------------------------------
    # Storage tools
    # ------------------------------------------------------------------
    {
        "name": "add_to_watchlist",
        "description": "Add a stock ticker to the user's watchlist. Call this when the user asks to watch, track, or save a stock.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g., AAPL)"},
                "notes": {"type": "string", "description": "Optional notes about why this ticker is being watched"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for categorisation (e.g., ['tech', 'high-growth'])",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "remove_from_watchlist",
        "description": "Remove a stock ticker from the user's watchlist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol to remove"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_watchlist",
        "description": "Get all tickers currently on the user's watchlist, including notes and tags.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "save_thesis",
        "description": (
            "Save a new investment thesis for a stock. Use this after completing analysis when the "
            "user asks to save or record their thesis, or when you have formed a well-supported view."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "title": {"type": "string", "description": "Short descriptive title for the thesis"},
                "bull_case": {"type": "string", "description": "Arguments supporting a bullish view"},
                "bear_case": {"type": "string", "description": "Arguments supporting a bearish view or key risks"},
                "catalysts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Upcoming events or factors that could unlock value",
                },
                "risks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key risks that could invalidate the thesis",
                },
                "target_price": {
                    "type": "string",
                    "description": "Price target as a decimal string (e.g., '185.50')",
                },
                "time_horizon_months": {
                    "type": "integer",
                    "description": "Investment time horizon in months (e.g., 12 for one year)",
                },
                "confidence_score": {
                    "type": "number",
                    "description": "Conviction level from 0.0 (none) to 1.0 (maximum). Default 0.5.",
                },
            },
            "required": ["ticker", "title", "bull_case", "bear_case"],
        },
    },
    {
        "name": "update_thesis",
        "description": (
            "Update one or more fields of an existing investment thesis. "
            "Use list_theses first to get the thesis ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thesis_id": {"type": "string", "description": "ID of the thesis to update (from list_theses)"},
                "status": {
                    "type": "string",
                    "enum": ["active", "archived", "invalidated", "realized"],
                    "description": "New status for the thesis",
                },
                "title": {"type": "string", "description": "Updated title"},
                "bull_case": {"type": "string", "description": "Updated bull case"},
                "bear_case": {"type": "string", "description": "Updated bear case"},
                "catalysts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Updated list of catalysts",
                },
                "risks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Updated list of risks",
                },
                "target_price": {"type": "string", "description": "Updated price target as a decimal string"},
                "confidence_score": {
                    "type": "number",
                    "description": "Updated conviction level from 0.0 to 1.0",
                },
                "time_horizon_months": {
                    "type": "integer",
                    "description": "Updated time horizon in months",
                },
            },
            "required": ["thesis_id"],
        },
    },
    {
        "name": "delete_thesis",
        "description": "Permanently delete an investment thesis. Use list_theses to get the thesis ID first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thesis_id": {"type": "string", "description": "ID of the thesis to delete"}
            },
            "required": ["thesis_id"],
        },
    },
    {
        "name": "list_theses",
        "description": "List saved investment theses. Optionally filter by ticker to see theses for a specific stock.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Filter by ticker symbol (omit to list all active theses)",
                }
            },
            "required": [],
        },
    },
]
