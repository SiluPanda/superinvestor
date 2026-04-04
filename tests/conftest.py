from __future__ import annotations

from pathlib import Path

import pytest_asyncio

from superinvestor.store.db import Database


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database with all migrations applied."""
    database = Database(Path(":memory:"))
    conn = await database.connect()
    yield conn
    await database.close()
