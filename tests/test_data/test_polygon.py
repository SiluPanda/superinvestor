from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from superinvestor.data.polygon import PolygonError, PolygonProvider
from superinvestor.models.enums import Exchange, Timespan


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code, json=json_data, request=httpx.Request("GET", "http://test")
    )


@pytest.fixture
def provider() -> PolygonProvider:
    return PolygonProvider(api_key="test-key", rate_limit=1000)


class TestGetStock:
    @pytest.mark.asyncio
    async def test_get_stock(self, provider: PolygonProvider) -> None:
        mock_data = {
            "results": {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "primary_exchange": "XNAS",
                "sic_description": "Electronic Computers",
                "market_cap": 3000000000000,
                "share_class_shares_outstanding": 15000000000,
                "active": True,
            }
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            stock = await provider.get_stock("AAPL")

        assert stock.ticker == "AAPL"
        assert stock.name == "Apple Inc."
        assert stock.exchange == Exchange.NASDAQ
        assert stock.market_cap == Decimal("3000000000000")
        assert stock.active is True

    @pytest.mark.asyncio
    async def test_get_stock_nyse(self, provider: PolygonProvider) -> None:
        mock_data = {"results": {"ticker": "IBM", "name": "IBM", "primary_exchange": "XNYS"}}
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            stock = await provider.get_stock("IBM")
        assert stock.exchange == Exchange.NYSE


class TestSearchTickers:
    @pytest.mark.asyncio
    async def test_search(self, provider: PolygonProvider) -> None:
        mock_data = {
            "results": [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "primary_exchange": "XNAS",
                    "active": True,
                },
                {
                    "ticker": "APLE",
                    "name": "Apple Hospitality REIT",
                    "primary_exchange": "XNYS",
                    "active": True,
                },
            ]
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            results = await provider.search_tickers("apple")
        assert len(results) == 2
        assert results[0].ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_search_empty(self, provider: PolygonProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response({"results": []}),
        ):
            results = await provider.search_tickers("zzzzzzz")
        assert results == []


class TestGetQuote:
    @pytest.mark.asyncio
    async def test_get_quote(self, provider: PolygonProvider) -> None:
        mock_data = {
            "results": [
                {
                    "T": "AAPL",
                    "o": 173.0,
                    "h": 176.5,
                    "l": 172.0,
                    "c": 175.5,
                    "v": 55000000,
                    "vw": 174.8,
                    "t": 1700000000000,
                }
            ]
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            quote = await provider.get_quote("AAPL")

        assert quote.ticker == "AAPL"
        assert quote.price == Decimal("175.5")
        assert quote.open == Decimal("173.0")
        assert quote.high == Decimal("176.5")
        assert quote.volume == 55000000
        assert quote.previous_close == Decimal("0")
        assert quote.change == Decimal("0")
        assert quote.change_percent == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_quote_not_found(self, provider: PolygonProvider) -> None:
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response({"results": []}),
        ):
            with pytest.raises(PolygonError):
                await provider.get_quote("ZZZZ")


class TestGetOHLCV:
    @pytest.mark.asyncio
    async def test_get_ohlcv(self, provider: PolygonProvider) -> None:
        mock_data = {
            "results": [
                {
                    "o": 170,
                    "h": 172,
                    "l": 169,
                    "c": 171,
                    "v": 40000000,
                    "vw": 170.5,
                    "t": 1700000000000,
                    "n": 500000,
                },
                {
                    "o": 171,
                    "h": 175,
                    "l": 170,
                    "c": 174,
                    "v": 50000000,
                    "vw": 173.0,
                    "t": 1700086400000,
                    "n": 600000,
                },
            ]
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            bars = await provider.get_ohlcv("AAPL", timespan=Timespan.DAY)

        assert len(bars) == 2
        assert bars[0].open == Decimal("170")
        assert bars[1].close == Decimal("174")
        assert bars[0].volume == 40000000


class TestGetNews:
    @pytest.mark.asyncio
    async def test_get_news(self, provider: PolygonProvider) -> None:
        mock_data = {
            "results": [
                {
                    "title": "Apple Reports Q4 Earnings",
                    "description": "Strong revenue growth...",
                    "article_url": "https://example.com/news1",
                    "published_utc": "2024-11-01T18:00:00Z",
                    "source": {"name": "Reuters"},
                    "image_url": "https://example.com/img.jpg",
                    "insights": [{"ticker": "AAPL", "sentiment": "positive"}],
                },
                {
                    "title": "Market Roundup",
                    "description": "Mixed signals...",
                    "article_url": "https://example.com/news2",
                    "published_utc": "2024-11-01T16:00:00Z",
                    "source": "Bloomberg",
                    "insights": [{"ticker": "AAPL", "sentiment": "neutral"}],
                },
            ]
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            news = await provider.get_news("AAPL")

        assert len(news) == 2
        assert news[0].headline == "Apple Reports Q4 Earnings"
        assert news[0].sentiment_score == Decimal("1.0")
        assert news[1].sentiment_score == Decimal("0.0")


class TestErrors:
    @pytest.mark.asyncio
    async def test_api_error(self, provider: PolygonProvider) -> None:
        error_resp = httpx.Response(
            403, text="Forbidden", request=httpx.Request("GET", "http://test")
        )
        with patch.object(
            provider._client, "request", new_callable=AsyncMock, return_value=error_resp
        ):
            with pytest.raises(PolygonError) as exc_info:
                await provider.get_stock("AAPL")
            assert exc_info.value.status_code == 403
