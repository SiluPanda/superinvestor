from __future__ import annotations

import asyncio
import time

import httpx


class RateLimiter:
    """Token-bucket rate limiter for API calls."""

    def __init__(self, calls_per_period: int, period_seconds: float) -> None:
        self._max_tokens = calls_per_period
        self._tokens = float(calls_per_period)
        self._period = period_seconds
        self._refill_rate = calls_per_period / period_seconds
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        wait_time = 0.0
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
            self._last_refill = now

            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._refill_rate
            else:
                self._tokens -= 1.0

        # Sleep outside the lock so other callers are not blocked.
        if wait_time:
            await asyncio.sleep(wait_time)
            async with self._lock:
                self._last_refill = time.monotonic()
                self._tokens = 0.0


def create_http_client(
    base_url: str = "",
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Create a configured async HTTP client."""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout),
        headers=headers or {},
        follow_redirects=True,
    )
