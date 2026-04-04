from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from superinvestor.data.fred import FredError, FredProvider


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code, json=json_data, request=httpx.Request("GET", "http://test")
    )


@pytest.fixture
def provider() -> FredProvider:
    return FredProvider(api_key="test-key", rate_limit=1000)


class TestGetSeries:
    @pytest.mark.asyncio
    async def test_get_series(self, provider: FredProvider) -> None:
        mock_data = {
            "seriess": [
                {
                    "id": "GDP",
                    "title": "Gross Domestic Product",
                    "frequency_short": "Q",
                    "units_short": "Bil. of $",
                    "seasonal_adjustment_short": "SAAR",
                    "last_updated": "2024-10-30",
                    "notes": "BEA Account Code: A191RC",
                }
            ]
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            series = await provider.get_series("GDP")

        assert series.series_id == "GDP"
        assert series.title == "Gross Domestic Product"
        assert series.frequency == "Q"


class TestGetObservations:
    @pytest.mark.asyncio
    async def test_get_observations(self, provider: FredProvider) -> None:
        mock_data = {
            "observations": [
                {"date": "2024-10-01", "value": "4.1"},
                {"date": "2024-09-01", "value": "4.2"},
                {"date": "2024-08-01", "value": "."},
            ]
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            obs = await provider.get_observations("UNRATE", limit=3)

        assert len(obs) == 3
        assert obs[0].value == Decimal("4.1")
        assert obs[1].value == Decimal("4.2")
        assert obs[2].value is None  # "." mapped to None


class TestGetLatestValue:
    @pytest.mark.asyncio
    async def test_get_latest(self, provider: FredProvider) -> None:
        mock_data = {"observations": [{"date": "2024-10-01", "value": "5.33"}]}
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            obs = await provider.get_latest_value("DFF")

        assert obs is not None
        assert obs.value == Decimal("5.33")
        assert obs.date == date(2024, 10, 1)

    @pytest.mark.asyncio
    async def test_get_latest_empty(self, provider: FredProvider) -> None:
        mock_data = {"observations": []}
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            obs = await provider.get_latest_value("WEIRD")
        assert obs is None


class TestSearchSeries:
    @pytest.mark.asyncio
    async def test_search(self, provider: FredProvider) -> None:
        mock_data = {
            "seriess": [
                {
                    "id": "UNRATE",
                    "title": "Unemployment Rate",
                    "frequency_short": "M",
                    "units_short": "%",
                    "seasonal_adjustment_short": "SA",
                },
                {
                    "id": "U6RATE",
                    "title": "Total Unemployed",
                    "frequency_short": "M",
                    "units_short": "%",
                    "seasonal_adjustment_short": "SA",
                },
            ]
        }
        with patch.object(
            provider._client,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_response(mock_data),
        ):
            results = await provider.search_series("unemployment")
        assert len(results) == 2
        assert results[0].series_id == "UNRATE"


class TestErrors:
    @pytest.mark.asyncio
    async def test_api_error(self, provider: FredProvider) -> None:
        error_resp = httpx.Response(
            400, json={"error_message": "Bad Request"}, request=httpx.Request("GET", "http://test")
        )
        with patch.object(
            provider._client, "request", new_callable=AsyncMock, return_value=error_resp
        ):
            with pytest.raises(FredError) as exc_info:
                await provider.get_series("BAD")
            assert exc_info.value.status_code == 400
