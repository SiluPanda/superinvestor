from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from superinvestor.data.base import RateLimiter, create_http_client
from superinvestor.models.enums import Exchange, Timespan
from superinvestor.models.market import CompanyNews, OHLCV, Quote, Stock

_EXCHANGE_MAP: dict[str, Exchange] = {
    "XNYS": Exchange.NYSE,
    "XNAS": Exchange.NASDAQ,
}

_SENTIMENT_MAP: dict[str, Decimal] = {
    "positive": Decimal("1.0"),
    "negative": Decimal("-1.0"),
    "neutral": Decimal("0.0"),
}


class PolygonError(Exception):
    """Raised when the Polygon.io API returns a non-200 response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Polygon API error {status_code}: {message}")


class PolygonProvider:
    """Polygon.io REST API data provider for market data, news, and quotes."""

    def __init__(self, api_key: str, rate_limit: int = 5) -> None:
        self._api_key = api_key
        self._client = create_http_client(base_url="https://api.polygon.io")
        self._limiter = RateLimiter(
            calls_per_period=rate_limit,
            period_seconds=60.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **params: Any) -> dict[str, Any]:
        """Make a rate-limited request to the Polygon API."""
        await self._limiter.acquire()
        params["apiKey"] = self._api_key
        response = await self._client.request(method, path, params=params)
        if response.status_code != 200:
            body = response.text
            raise PolygonError(response.status_code, body)
        return response.json()

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        return await self._request("GET", path, **params)

    @staticmethod
    def _parse_exchange(mic: str) -> Exchange:
        return _EXCHANGE_MAP.get(mic, Exchange.NASDAQ)

    @staticmethod
    def _ms_to_datetime(ms_timestamp: int) -> datetime:
        return datetime.fromtimestamp(ms_timestamp / 1000.0, tz=timezone.utc)

    @staticmethod
    def _default_from_date() -> str:
        """Return a date string for 1 year ago from today."""
        now = datetime.now(timezone.utc)
        try:
            one_year_ago = now.replace(year=now.year - 1)
        except ValueError:
            # Handle Feb 29 -> Feb 28 for leap year edge case
            one_year_ago = now.replace(year=now.year - 1, day=28)
        return one_year_ago.strftime("%Y-%m-%d")

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_stock(self, ticker: str) -> Stock:
        """Get stock details from /v3/reference/tickers/{ticker}."""
        data = await self._get(f"/v3/reference/tickers/{ticker.upper()}")
        result: dict[str, Any] = data.get("results", {})
        return Stock(
            ticker=result.get("ticker", ticker.upper()),
            name=result.get("name", ""),
            exchange=self._parse_exchange(result.get("primary_exchange", "")),
            sector=result.get("sic_description", ""),
            market_cap=Decimal(str(result.get("market_cap", 0))),
            shares_outstanding=Decimal(str(result.get("share_class_shares_outstanding", 0))),
            active=result.get("active", True),
        )

    async def search_tickers(self, query: str, limit: int = 10) -> list[Stock]:
        """Search for tickers from /v3/reference/tickers?search=..."""
        data = await self._get(
            "/v3/reference/tickers",
            search=query,
            active="true",
            market="stocks",
            limit=limit,
        )
        results: list[dict[str, Any]] = data.get("results", [])
        return [
            Stock(
                ticker=item.get("ticker", ""),
                name=item.get("name", ""),
                exchange=self._parse_exchange(item.get("primary_exchange", "")),
                active=item.get("active", True),
            )
            for item in results
        ]

    async def get_quote(self, ticker: str) -> Quote:
        """Get latest quote from /v2/aggs/ticker/{ticker}/prev."""
        data = await self._get(
            f"/v2/aggs/ticker/{ticker.upper()}/prev",
            adjusted="true",
        )
        results: list[dict[str, Any]] = data.get("results", [])
        if not results:
            raise PolygonError(404, f"No previous close data for {ticker}")

        bar = results[0]
        close = Decimal(str(bar.get("c", 0)))
        open_price = Decimal(str(bar.get("o", 0)))
        change = close - open_price
        change_percent = (change / open_price * 100) if open_price else Decimal("0")

        return Quote(
            ticker=bar.get("T", ticker.upper()),
            price=close,
            change=change,
            change_percent=change_percent,
            open=open_price,
            high=Decimal(str(bar.get("h", 0))),
            low=Decimal(str(bar.get("l", 0))),
            previous_close=open_price,
            volume=int(bar.get("v", 0)),
            timestamp=self._ms_to_datetime(int(bar.get("t", 0))),
        )

    async def get_ohlcv(
        self,
        ticker: str,
        timespan: Timespan = Timespan.DAY,
        from_date: str = "",
        to_date: str = "",
        limit: int = 365,
    ) -> list[OHLCV]:
        """Get historical bars from /v2/aggs/ticker/.../range/..."""
        start = from_date or self._default_from_date()
        end = to_date or self._today()

        data = await self._get(
            f"/v2/aggs/ticker/{ticker.upper()}/range/1/{timespan.value}/{start}/{end}",
            adjusted="true",
            sort="asc",
            limit=limit,
        )
        results: list[dict[str, Any]] = data.get("results", [])
        bars = [
            OHLCV(
                ticker=ticker.upper(),
                timestamp=self._ms_to_datetime(int(bar.get("t", 0))),
                timespan=timespan,
                open=Decimal(str(bar.get("o", 0))),
                high=Decimal(str(bar.get("h", 0))),
                low=Decimal(str(bar.get("l", 0))),
                close=Decimal(str(bar.get("c", 0))),
                volume=int(bar.get("v", 0)),
                vwap=Decimal(str(bar.get("vw", 0))),
                num_trades=int(bar.get("n", 0)),
            )
            for bar in results
        ]
        bars.sort(key=lambda b: b.timestamp)
        return bars

    async def get_news(self, ticker: str, limit: int = 20) -> list[CompanyNews]:
        """Get news from /v2/reference/news?ticker=..."""
        data = await self._get(
            "/v2/reference/news",
            ticker=ticker.upper(),
            limit=limit,
            order="desc",
            sort="published_utc",
        )
        results: list[dict[str, Any]] = data.get("results", [])
        articles: list[CompanyNews] = []
        for item in results:
            sentiment = self._extract_sentiment(item.get("insights", []), ticker)
            published = item.get("published_utc", "")
            articles.append(
                CompanyNews(
                    ticker=ticker.upper(),
                    headline=item.get("title", ""),
                    summary=item.get("description", ""),
                    source=item.get("source", {}).get("name", "")
                    if isinstance(item.get("source"), dict)
                    else str(item.get("source", "")),
                    url=item.get("article_url", ""),
                    published_at=datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if published
                    else datetime.now(timezone.utc),
                    category="news",
                    sentiment_score=sentiment,
                )
            )
        return articles

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_sentiment(insights: list[dict[str, Any]], ticker: str) -> Decimal | None:
        """Extract sentiment score for the given ticker from Polygon insights."""
        upper_ticker = ticker.upper()
        for insight in insights:
            if insight.get("ticker", "").upper() == upper_ticker:
                sentiment_label = insight.get("sentiment", "").lower()
                if sentiment_label in _SENTIMENT_MAP:
                    return _SENTIMENT_MAP[sentiment_label]
        return None
