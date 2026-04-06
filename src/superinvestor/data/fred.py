from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from .base import RateLimiter, create_http_client

_BASE_URL = "https://api.stlouisfed.org/fred"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FredError(Exception):
    """Raised when a FRED API request fails."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"FRED API error {status_code}: {message}")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class FredSeries(BaseModel):
    series_id: str
    title: str
    frequency: str
    units: str
    seasonal_adjustment: str = ""
    last_updated: str = ""
    notes: str = ""


class FredObservation(BaseModel):
    date: date
    value: Decimal | None = None


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class FredProvider:
    """Async client for the FRED (Federal Reserve Economic Data) API."""

    COMMON_SERIES: list[str] = [
        "GDP",
        "UNRATE",
        "DFF",
        "CPIAUCSL",
        "T10Y2Y",
        "VIXCLS",
        "SP500",
        "DCOILWTICO",
    ]

    def __init__(self, api_key: str, rate_limit: int = 120) -> None:
        self._api_key = api_key
        self._limiter = RateLimiter(calls_per_period=rate_limit, period_seconds=60.0)
        self._client = create_http_client(base_url=_BASE_URL)

    # -- public API ---------------------------------------------------------

    async def get_series(self, series_id: str) -> FredSeries:
        """Get metadata for a FRED series."""
        data = await self._request(
            "/series",
            params={"series_id": series_id},
        )
        seriess = data.get("seriess", [])
        if not seriess:
            raise FredError(404, f"Series not found: {series_id!r}")
        raw = seriess[0]
        return FredSeries(
            series_id=raw["id"],
            title=raw["title"],
            frequency=raw["frequency_short"],
            units=raw["units_short"],
            seasonal_adjustment=raw.get("seasonal_adjustment_short", ""),
            last_updated=raw.get("last_updated", ""),
            notes=raw.get("notes", ""),
        )

    async def get_observations(
        self,
        series_id: str,
        start_date: str = "",
        end_date: str = "",
        limit: int = 100,
    ) -> list[FredObservation]:
        """Get observations for a FRED series.

        Missing values (reported as ``"."`` by FRED) are stored as
        ``value=None`` on the returned observations.
        """
        params: dict[str, str | int] = {
            "series_id": series_id,
            "sort_order": "desc",
            "limit": limit,
        }
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date

        data = await self._request("/series/observations", params=params)
        return [self._parse_observation(obs) for obs in data["observations"]]

    async def search_series(self, query: str, limit: int = 10) -> list[FredSeries]:
        """Search for FRED series by keyword."""
        data = await self._request(
            "/series/search",
            params={"search_text": query, "limit": limit},
        )
        return [
            FredSeries(
                series_id=raw["id"],
                title=raw["title"],
                frequency=raw["frequency_short"],
                units=raw["units_short"],
                seasonal_adjustment=raw.get("seasonal_adjustment_short", ""),
                last_updated=raw.get("last_updated", ""),
                notes=raw.get("notes", ""),
            )
            for raw in data["seriess"]
        ]

    async def get_latest_value(self, series_id: str) -> FredObservation | None:
        """Get the most recent observation for a series."""
        observations = await self.get_observations(series_id, limit=1)
        return observations[0] if observations else None

    async def get_economic_snapshot(self) -> dict[str, FredObservation | None]:
        """Get latest values for all ``COMMON_SERIES``.

        Returns a mapping of ``{series_id: observation}``.  Fetches are
        executed in parallel; the rate limiter throttles as needed.
        """
        results = await asyncio.gather(
            *(self.get_latest_value(sid) for sid in self.COMMON_SERIES),
            return_exceptions=True,
        )
        snapshot: dict[str, FredObservation | None] = {}
        for series_id, result in zip(self.COMMON_SERIES, results):
            if isinstance(result, BaseException):
                snapshot[series_id] = None
            else:
                snapshot[series_id] = result
        return snapshot

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # -- internals ----------------------------------------------------------

    async def _request(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
    ) -> dict:
        """Execute a rate-limited GET against the FRED API."""
        await self._limiter.acquire()

        merged: dict[str, str | int] = {
            "api_key": self._api_key,
            "file_type": "json",
        }
        if params:
            merged.update(params)

        response = await self._client.get(path, params=merged)
        if response.status_code != 200:
            try:
                body = response.json()
                message = body.get("error_message", response.text)
            except Exception:
                message = response.text
            raise FredError(response.status_code, message)

        return response.json()

    @staticmethod
    def _parse_observation(raw: dict) -> FredObservation:
        """Convert a raw FRED observation dict into a model instance.

        FRED encodes missing data as the string ``"."``.
        """
        raw_value = raw.get("value", ".")
        value: Decimal | None = None
        if raw_value != ".":
            try:
                value = Decimal(raw_value)
            except InvalidOperation:
                value = None

        return FredObservation(
            date=date.fromisoformat(raw["date"]),
            value=value,
        )
