from __future__ import annotations

import time

import pytest

from superinvestor.data.base import RateLimiter


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_no_burst_after_wait(self) -> None:
        """After a wait-induced acquire, the next acquire should also wait."""
        limiter = RateLimiter(calls_per_period=1, period_seconds=1.0)

        # First: consumes the initial token instantly.
        await limiter.acquire()

        # Second: must wait ~1s.
        start = time.monotonic()
        await limiter.acquire()
        assert time.monotonic() - start >= 0.8

        # Third: should ALSO wait ~1s, not burst.
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.8, f"Expected ~1s wait but got {elapsed:.2f}s (burst after wait)"

    @pytest.mark.asyncio
    async def test_initial_burst_up_to_max(self) -> None:
        """Initial tokens allow a burst up to max_tokens without waiting."""
        limiter = RateLimiter(calls_per_period=5, period_seconds=1.0)
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, "Initial burst should not wait"
