from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, TypeVar, Union, get_args, get_origin

import aiosqlite
from pydantic import BaseModel

from superinvestor.models.base import utc_now

T = TypeVar("T", bound=BaseModel)


class BaseStore(Generic[T]):
    """Generic store providing CRUD helpers for a single Pydantic model / table."""

    def __init__(self, db: aiosqlite.Connection, model_type: type[T], table: str) -> None:
        self._db = db
        self._model_type = model_type
        self._table = table

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_value(value: object) -> object:
        """Convert a Python value into a SQLite-compatible type."""
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return json.dumps(value)
        return value

    def _to_row(self, model: T) -> dict[str, object]:
        """Convert a Pydantic model instance to a dict of SQLite-ready values."""
        raw = model.model_dump()
        return {key: self._serialize_value(val) for key, val in raw.items()}

    @staticmethod
    def _is_list_type(annotation: Any) -> bool:
        """Return True if the annotation resolves to list[...]."""
        origin = get_origin(annotation)
        if origin is list:
            return True
        # Handle Optional[list[...]] -> Union[list[...], None]
        if origin is Union:
            for arg in get_args(annotation):
                if arg is type(None):
                    continue
                if get_origin(arg) is list:
                    return True
        return False

    @staticmethod
    def _is_bool_type(annotation: Any) -> bool:
        """Return True if the annotation resolves to bool."""
        if annotation is bool:
            return True
        origin = get_origin(annotation)
        if origin is Union:
            for arg in get_args(annotation):
                if arg is type(None):
                    continue
                if arg is bool:
                    return True
        return False

    def _from_row(self, row: aiosqlite.Row) -> T:
        """Deserialise a database Row into the Pydantic model.

        Pydantic v2 handles str -> Decimal and str -> datetime coercion, but
        we must pre-process JSON list fields and SQLite integer booleans.
        """
        data = dict(row)
        fields = self._model_type.model_fields

        for field_name, field_info in fields.items():
            if field_name not in data:
                continue
            val = data[field_name]
            if val is None:
                continue

            annotation = field_info.annotation
            if self._is_list_type(annotation) and isinstance(val, str):
                data[field_name] = json.loads(val)
            elif self._is_bool_type(annotation) and isinstance(val, int):
                data[field_name] = bool(val)

        return self._model_type.model_validate(data)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def insert(self, model: T) -> None:
        """Insert a single row. Raises on conflict."""
        row = self._to_row(model)
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        sql = f"INSERT INTO {self._table} ({cols}) VALUES ({placeholders})"  # noqa: S608
        await self._db.execute(sql, tuple(row.values()))
        await self._db.commit()

    async def insert_many(self, models: list[T]) -> None:
        """Bulk insert with INSERT OR IGNORE semantics."""
        if not models:
            return
        row = self._to_row(models[0])
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        sql = f"INSERT OR IGNORE INTO {self._table} ({cols}) VALUES ({placeholders})"  # noqa: S608
        rows = [tuple(self._to_row(m).values()) for m in models]
        await self._db.executemany(sql, rows)
        await self._db.commit()

    async def get_by_id(self, id: str) -> T | None:
        """Fetch a single row by primary key."""
        sql = f"SELECT * FROM {self._table} WHERE id = ?"  # noqa: S608
        cursor = await self._db.execute(sql, (id,))
        row = await cursor.fetchone()
        return self._from_row(row) if row else None

    async def delete_by_id(self, id: str) -> bool:
        """Delete a row by primary key. Returns True if a row was deleted."""
        sql = f"DELETE FROM {self._table} WHERE id = ?"  # noqa: S608
        cursor = await self._db.execute(sql, (id,))
        await self._db.commit()
        return cursor.rowcount > 0

    async def update_by_id(self, id: str, **fields: object) -> bool:
        """Update specific columns for a row. Returns True if a row was updated."""
        if not fields:
            return False
        fields["updated_at"] = utc_now()
        serialized = {k: self._serialize_value(v) for k, v in fields.items()}
        set_clause = ", ".join(f"{k} = ?" for k in serialized)
        sql = f"UPDATE {self._table} SET {set_clause} WHERE id = ?"  # noqa: S608
        params = (*serialized.values(), id)
        cursor = await self._db.execute(sql, params)
        await self._db.commit()
        return cursor.rowcount > 0

    async def query(
        self,
        where: str = "",
        params: tuple[object, ...] = (),
        order_by: str = "created_at DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]:
        """Run a parameterised SELECT with optional WHERE, ORDER BY, and paging."""
        sql = f"SELECT * FROM {self._table}"  # noqa: S608
        if where:
            sql += f" WHERE {where}"
        sql += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
        cursor = await self._db.execute(sql, (*params, limit, offset))
        rows = await cursor.fetchall()
        return [self._from_row(r) for r in rows]

    async def count(self, where: str = "", params: tuple[object, ...] = ()) -> int:
        """Return the number of rows matching the optional WHERE clause."""
        sql = f"SELECT COUNT(*) FROM {self._table}"  # noqa: S608
        if where:
            sql += f" WHERE {where}"
        cursor = await self._db.execute(sql, params)
        row = await cursor.fetchone()
        return row[0] if row else 0
