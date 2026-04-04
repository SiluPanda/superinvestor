from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite


class CacheStore:
    """Direct-SQL cache store for provider API responses.

    Not a BaseStore subclass -- the provider_cache table has no Pydantic model
    and uses a plain cache_key TEXT primary key instead of a UUID id column.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get(self, key: str) -> str | None:
        """Return cached response_data if the key exists and hasn't expired."""
        cursor = await self._db.execute(
            "SELECT response_data FROM provider_cache WHERE cache_key = ? AND expires_at > ?",
            (key, _utc_now_iso()),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set(
        self,
        key: str,
        provider: str,
        data: str,
        ttl: int,
    ) -> None:
        """Upsert a cache entry with the given TTL in seconds."""
        now = _utc_now()
        fetched_at = now.isoformat()
        expires_at = _add_seconds(now, ttl).isoformat()

        await self._db.execute(
            "INSERT INTO provider_cache "
            "(cache_key, provider, response_data, fetched_at, ttl_seconds, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(cache_key) DO UPDATE SET "
            "provider = excluded.provider, "
            "response_data = excluded.response_data, "
            "fetched_at = excluded.fetched_at, "
            "ttl_seconds = excluded.ttl_seconds, "
            "expires_at = excluded.expires_at",
            (key, provider, data, fetched_at, ttl, expires_at),
        )
        await self._db.commit()

    async def clear_expired(self) -> int:
        """Delete all expired entries. Returns the number of rows removed."""
        cursor = await self._db.execute(
            "DELETE FROM provider_cache WHERE expires_at <= ?",
            (_utc_now_iso(),),
        )
        await self._db.commit()
        return cursor.rowcount

    async def clear_all(self) -> int:
        """Delete every cache entry. Returns the number of rows removed."""
        cursor = await self._db.execute("DELETE FROM provider_cache")
        await self._db.commit()
        return cursor.rowcount


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _add_seconds(dt: datetime, seconds: int) -> datetime:
    from datetime import timedelta

    return dt + timedelta(seconds=seconds)
