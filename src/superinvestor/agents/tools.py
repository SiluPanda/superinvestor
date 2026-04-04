from __future__ import annotations

import json
from datetime import date
from typing import Any

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
    ) -> None:
        self._polygon = polygon
        self._edgar = edgar
        self._fred = fred

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> str:
        """Dispatch a tool call by name. Returns JSON string result."""
        handler = getattr(self, tool_name, None)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = await handler(**args)
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
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
]
